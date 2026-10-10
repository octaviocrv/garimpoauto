"""API do Garimpo Auto. Sobe com:  .venv/bin/uvicorn server:app --port 8000

GET /saude          confere que subiu
GET /buscar         ResultadoBusca completo em JSON
GET /buscar/stream  o mesmo por SSE: um evento "pagina" por página, "fim" com funil, motivo_parada
                    e avisos, e "erro" (em tom humano) se algo quebrar

Parâmetros: texto (obrigatório), marca, modelo, versao, ano_min, ano_max, preco_min, preco_max,
km_min, km_max, cambio, combustivel, anunciante (particular ou profissional), ordenar (recentes,
menor_preco ou relevancia, padrão recentes), estado, regiao, cidade, dev, atualizar (1 ignora o
cache e coleta de novo). Estado ausente usa config.ESTADO_PADRAO, "todos" busca no Brasil
todo. Com dev=1 os avisos trazem o detalhe_tecnico, senão ele nem aparece.

Cache só em memória, com a chave de busca.chave_busca e TTL de config.CACHE_TTL_SEGUNDOS. A mesma
busca em andamento é compartilhada e só roda uma coleta real por vez (as outras esperam na fila).
A resposta nunca leva o item cru da fonte nem dado de anunciante.
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any, Iterator, Optional

from fastapi import Depends, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import ValidationError

import config
from busca import chave_busca, filtros_locais, montar_resultado
from config import LimitesBusca
from schemas import Anuncio, Busca, PaginaBusca, ResultadoBusca
from sources import olx
from sources.base import Fonte

MSG_ERRO = "Não achei esse carro agora, tenta de novo?"
MSG_PEDIDO = "Esse pedido de busca não está certo, confere os filtros?"
ESPERA_PING = 15.0  # segundos sem novidade até mandar um sinal de vida no stream


def _anuncio_json(a: Anuncio) -> dict[str, Any]:
    return a.to_dict(com_raw=False)  # sem o item cru da fonte


def _avisos_json(avisos: list, dev: bool) -> list[dict]:
    saida = [a.model_dump(mode="json") for a in avisos]
    if not dev:
        for a in saida:
            a.pop("detalhe_tecnico", None)
    return saida


def resultado_json(r: ResultadoBusca, dev: bool, do_cache: bool = False) -> dict[str, Any]:
    corpo = r.model_dump(mode="json", exclude={"anuncios", "avisos"})
    corpo["estado_aplicado"] = (r.busca.estado if r.busca else None) or "todos"  # a tela mostra onde buscou
    corpo["do_cache"] = do_cache  # True quando veio guardado, sem coletar de novo
    corpo["anuncios"] = [_anuncio_json(a) for a in r.anuncios]
    corpo["avisos"] = _avisos_json(r.avisos, dev)
    return corpo


def pagina_json(p: PaginaBusca, max_paginas: int) -> dict[str, Any]:
    return {
        "numero": p.numero,
        "max_paginas": max_paginas,  # teto de páginas da coleta, para a tela mostrar o progresso
        "anuncios": [_anuncio_json(a) for a in p.anuncios],
        "coletados": p.coletados,
        "cortados_por_filtro": p.cortados_por_filtro,
        "acumulado": p.acumulado,
        "total_na_fonte": p.total_ads,
    }


def sse(evento: str, dados: Any) -> str:
    return f"event: {evento}\ndata: {json.dumps(dados, ensure_ascii=False)}\n\n"


class Coleta:
    """Uma coleta em andamento ou pronta. Quem pede a mesma busca divide a mesma Coleta."""

    def __init__(self) -> None:
        self.cond = threading.Condition()
        self.paginas: list[PaginaBusca] = []
        self.resultado: Optional[ResultadoBusca] = None
        self.quebrou = False
        self.valida_ate = 0.0  # preenchido quando termina

    @property
    def terminou(self) -> bool:
        return self.resultado is not None or self.quebrou

    def vigente(self, agora: float) -> bool:
        return not self.terminou or agora < self.valida_ate

    def proxima(self, indice: int, espera: float) -> Optional[PaginaBusca]:
        """Página `indice`, esperando até `espera` segundos. None se acabou ou se o tempo estourou
        (confira `terminou` e o tamanho de `paginas` para distinguir)."""
        with self.cond:
            self.cond.wait_for(lambda: indice < len(self.paginas) or self.terminou, timeout=espera)
            return self.paginas[indice] if indice < len(self.paginas) else None


class Servico:
    """Cache em memória, coleta única por busca e uma coleta real por vez."""

    def __init__(self, fonte: Fonte, ttl: float, limites: Optional[LimitesBusca] = None) -> None:
        self.fonte, self.ttl, self.limites = fonte, ttl, limites
        self.trava = threading.Lock()
        self.semaforo = threading.Semaphore(1)
        self.cache: dict[str, Coleta] = {}

    def max_paginas(self) -> int:
        return (self.limites or LimitesBusca()).max_paginas

    def obter(self, busca: Busca, atualizar: bool = False) -> tuple[Coleta, bool]:
        """(coleta, veio_do_cache). `atualizar` ignora uma coleta pronta e busca de novo. Se a mesma
        busca ainda está sendo coletada, divide essa coleta em vez de começar outra."""
        chave, agora = chave_busca(busca), time.monotonic()
        with self.trava:
            self.cache = {k: c for k, c in self.cache.items() if c.vigente(agora)}
            coleta = self.cache.get(chave)
            if coleta is not None and atualizar and coleta.terminou:
                coleta = None
            if coleta is None:
                coleta = self.cache[chave] = Coleta()
                threading.Thread(target=self._rodar, args=(chave, coleta, busca), daemon=True).start()
                return coleta, False
            return coleta, coleta.terminou

    def _rodar(self, chave: str, coleta: Coleta, busca: Busca) -> None:
        try:
            with self.semaforo:  # busca diferente espera aqui
                resultado = self._coletar(coleta, busca)
            with coleta.cond:
                coleta.resultado = resultado
                coleta.valida_ate = time.monotonic() + self.ttl
                coleta.cond.notify_all()
            if resultado.motivo_parada == "falha_fonte":
                self._esquecer(chave, coleta)  # falha não fica no cache
        except Exception:
            with coleta.cond:
                coleta.quebrou = True
                coleta.cond.notify_all()
            self._esquecer(chave, coleta)

    def _esquecer(self, chave: str, coleta: Coleta) -> None:
        with self.trava:
            if self.cache.get(chave) is coleta:
                del self.cache[chave]

    def _coletar(self, coleta: Coleta, busca: Busca) -> ResultadoBusca:
        limites = self.limites or LimitesBusca()
        inicio = time.monotonic()
        anuncios: list[Anuncio] = []
        cortados: dict[str, int] = {}
        paginas = coletados = 0
        total: Optional[int] = None
        na_origem: list[str] = []
        nao_resolvidos: list[str] = []
        motivo, detalhe = "falha_fonte", "a busca terminou sem motivo registrado"
        try:
            for pag in self.fonte.buscar_paginas(busca, limites):
                if pag.parou_por != olx.BLOQUEIO:
                    paginas += 1
                anuncios.extend(pag.anuncios)
                coletados += pag.coletados
                for nome, qtd in pag.cortados_por_filtro.items():
                    cortados[nome] = cortados.get(nome, 0) + qtd
                if pag.total_ads is not None:
                    total = pag.total_ads
                na_origem, nao_resolvidos = pag.na_origem, pag.nao_resolvidos
                if pag.parou_por is not None:
                    motivo, detalhe = olx._MOTIVOS[pag.parou_por], pag.aviso
                with coleta.cond:
                    coleta.paginas.append(pag)
                    coleta.cond.notify_all()
        except Exception as e:  # falha no meio: devolve o que já tem
            motivo = "falha_fonte"
            detalhe = f"erro inesperado na pagina {paginas + 1} ({type(e).__name__}: {e})"
        return montar_resultado(
            self.fonte.FONTE, anuncios, paginas, time.monotonic() - inicio, total, coletados,
            cortados, motivo, limites, detalhe, na_origem, nao_resolvidos, filtros_locais(busca, na_origem),
            busca=busca,
        )


def criar_app(
    fonte: Fonte = olx,  # type: ignore[assignment]  # o módulo olx segue a interface Fonte
    ttl: float = config.CACHE_TTL_SEGUNDOS,
    estado_padrao: str = config.ESTADO_PADRAO,
    limites: Optional[LimitesBusca] = None,
    cors_origens: Optional[list[str]] = None,
) -> FastAPI:
    app = FastAPI(title="Garimpo Auto")
    app.add_middleware(
        CORSMiddleware, allow_origins=cors_origens if cors_origens is not None else config.CORS_ORIGENS,
        allow_methods=["GET"], allow_headers=["*"],
    )
    servico = Servico(fonte, ttl, limites)
    app.state.servico = servico

    @app.exception_handler(RequestValidationError)
    async def _pedido_ruim(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse({"erro": MSG_PEDIDO}, status_code=422)

    @app.exception_handler(Exception)
    async def _quebrou(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse({"erro": MSG_ERRO}, status_code=500)

    def pedido(
        texto: str = Query(...),
        marca: Optional[str] = None,
        modelo: Optional[str] = None,
        versao: Optional[str] = None,
        ano_min: Optional[int] = None,
        ano_max: Optional[int] = None,
        preco_min: Optional[int] = None,
        preco_max: Optional[int] = None,
        km_min: Optional[int] = None,
        km_max: Optional[int] = None,
        cambio: Optional[str] = None,
        combustivel: Optional[str] = None,
        anunciante: Optional[str] = None,
        ordenar: Optional[str] = None,
        estado: Optional[str] = None,
        regiao: Optional[str] = None,
        cidade: Optional[str] = None,
    ) -> Busca:
        estado = (estado or "").strip() or estado_padrao
        if estado.lower() == "todos":
            estado = None
        try:
            return Busca(
                texto=texto, marca=marca, modelo=modelo, versao=versao, ano_min=ano_min, ano_max=ano_max,
                preco_min=preco_min, preco_max=preco_max, km_min=km_min, km_max=km_max,
                cambio=cambio, combustivel=combustivel, anunciante=anunciante, ordenar=ordenar,
                estado=estado, regiao=regiao, cidade=cidade,
            )
        except ValidationError:
            raise RequestValidationError([])

    @app.get("/saude")
    def saude() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/buscar")
    def buscar(busca: Busca = Depends(pedido), dev: int = 0, atualizar: int = 0) -> JSONResponse:
        coleta, do_cache = servico.obter(busca, atualizar == 1)
        with coleta.cond:
            coleta.cond.wait_for(lambda: coleta.terminou)
        if coleta.resultado is None:
            return JSONResponse({"erro": MSG_ERRO}, status_code=500)
        return JSONResponse(resultado_json(coleta.resultado, dev == 1, do_cache))

    @app.get("/buscar/stream")
    def stream(busca: Busca = Depends(pedido), dev: int = 0, atualizar: int = 0) -> StreamingResponse:
        coleta, do_cache = servico.obter(busca, atualizar == 1)

        def eventos() -> Iterator[str]:
            i = 0
            while True:
                pag = coleta.proxima(i, ESPERA_PING)
                if pag is not None:
                    yield sse("pagina", pagina_json(pag, servico.max_paginas()))
                    i += 1
                elif coleta.terminou and i >= len(coleta.paginas):
                    break
                else:
                    yield ": aguardando\n\n"  # sinal de vida enquanto espera na fila
            r = coleta.resultado
            if r is None:
                yield sse("erro", {"mensagem": MSG_ERRO})
                return
            fim = resultado_json(r, dev == 1, do_cache)
            fim.pop("anuncios")  # já foram nos eventos "pagina"
            yield sse("fim", fim)

        return StreamingResponse(
            eventos(), media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app


app = criar_app()
