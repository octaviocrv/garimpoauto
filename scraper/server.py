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
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturoTimeout
from datetime import datetime, timezone
from typing import Any, Iterator, Optional

from fastapi import Depends, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import ValidationError

import config
import localidades
from busca import aviso_filtro_aproximado, chave_busca, filtros_locais, montar_resultado, texto_informacao
from config import LimitesBusca
from schemas import Anuncio, Aviso, Busca, PaginaBusca, ResultadoBusca
from sources import olx
from sources.base import Fonte

MSG_ERRO = "Não achei esse carro agora, tenta de novo?"
MSG_MAIS_FALHOU = "Não consegui buscar mais agora, tenta de novo daqui a pouco?"
MSG_PEDIDO = "Esse pedido de busca não está certo, confere os filtros?"
MSG_REGIAO = "Não achei essa região nesse estado, escolhe uma da lista?"
MSG_ZONA = "Não achei essa zona, escolhe uma da lista?"
MSG_ZONA_SEM_REGIAO = "Pra escolher a zona, escolhe a região primeiro."
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


class PedidoInvalido(Exception):
    """Pedido que a pessoa pode corrigir. A mensagem já está pronta para a tela."""


class SessaoBusca:
    """Uma busca guardada por chave: as páginas já lidas e o cursor da fonte para ler a próxima.
    Quem pede a mesma busca divide a sessão, e página lida nunca é baixada de novo. A trava deixa
    uma leitura por vez por busca, então pedidos iguais e simultâneos esperam em vez de repetir."""

    def __init__(self, chave: str, fonte: Fonte, busca: Busca, limites: LimitesBusca, teto: int, semaforo: threading.Semaphore) -> None:
        self.chave, self.fonte, self.busca, self.limites, self.teto = chave, fonte, busca, limites, teto
        self.semaforo = semaforo
        self.trava = threading.Lock()
        self.cursor: Any = None
        self.paginas: list[PaginaBusca] = []
        self.tempos: list[float] = []  # segundos que cada página levou (pausa e leitura)
        self.quando: list[datetime] = []  # hora em que cada página foi lida
        self.valida_ate: Optional[float] = None  # começa a contar quando a 1ª página chega

    @property
    def terminou(self) -> bool:
        return bool(self.paginas) and self.paginas[-1].parou_por is not None

    def vigente(self, agora: float) -> bool:
        return self.valida_ate is None or agora < self.valida_ate

    def pagina(self, n: int, ttl: float, pausa: Optional[tuple[float, float]] = None) -> tuple[PaginaBusca, bool]:
        """Página `n` (a partir de 1) e se veio do cache. Lê da fonte só o que falta, na ordem. Se
        a fonte falhar devolve uma página com parou_por "bloqueio" que NÃO é guardada (pedir de novo
        tenta ler essa mesma página). Se a busca acabou antes de `n`, devolve a última página."""
        with self.trava:
            do_cache = n <= len(self.paginas)
            while len(self.paginas) < n and not self.terminou:
                inicio = time.monotonic()
                try:
                    if self.cursor is None:
                        self.cursor = self.fonte.abrir(self.busca, self.limites, teto=self.teto)
                    self.cursor.esperar(pausa)  # pausa fora do semáforo, para não travar a busca dos outros
                    with self.semaforo:  # só uma leitura real por vez
                        pag = self.cursor.proxima()
                except Exception as e:  # resposta estranha, falha de rede fora do retry, etc.
                    ultima = self.paginas[-1] if self.paginas else None
                    pag = PaginaBusca(
                        fonte=self.fonte.FONTE, numero=len(self.paginas) + 1, anuncios=[],
                        acumulado=ultima.acumulado if ultima else 0, total_ads=ultima.total_ads if ultima else None,
                        parou_por=olx.BLOQUEIO,
                        aviso=f"erro inesperado na pagina {len(self.paginas) + 1} ({type(e).__name__}: {e})",
                    )
                if pag.parou_por == olx.BLOQUEIO:
                    return pag, False
                self.paginas.append(pag)
                self.tempos.append(time.monotonic() - inicio)
                self.quando.append(datetime.now(timezone.utc))
                if len(self.paginas) == 1:
                    self.valida_ate = time.monotonic() + ttl
            return self.paginas[min(n, len(self.paginas)) - 1], do_cache


class Servico:
    """Sessões de busca em memória, com a chave de busca e o TTL, e uma leitura real por vez."""

    def __init__(self, fonte: Fonte, ttl: float, limites: Optional[LimitesBusca] = None, teto: int = config.MAX_PAGINAS_SOB_DEMANDA) -> None:
        self.fonte, self.ttl, self.limites, self.teto = fonte, ttl, limites or LimitesBusca(), teto
        self.trava = threading.Lock()
        self.semaforo = threading.Semaphore(1)
        self.cache: dict[str, SessaoBusca] = {}

    def obter(self, busca: Busca, atualizar: bool = False) -> SessaoBusca:
        """A sessão da busca. `atualizar` joga fora a sessão guardada e começa outra, a menos que
        ela esteja lendo uma página agora (aí divide essa leitura)."""
        chave, agora = chave_busca(busca), time.monotonic()
        with self.trava:
            self.cache = {k: s for k, s in self.cache.items() if s.vigente(agora)}
            sessao = self.cache.get(chave)
            if sessao is not None and atualizar and not sessao.trava.locked():
                sessao = None
            if sessao is None:
                sessao = self.cache[chave] = SessaoBusca(chave, self.fonte, busca, self.limites, self.teto, self.semaforo)
            return sessao

    def pagina(self, sessao: SessaoBusca, n: int, pausa: Optional[tuple[float, float]] = None) -> tuple[PaginaBusca, bool]:
        pag, do_cache = sessao.pagina(n, self.ttl, pausa)
        if pag.parou_por == olx.BLOQUEIO and not sessao.paginas:
            with self.trava:  # falha na 1ª página não fica no cache
                if self.cache.get(sessao.chave) is sessao:
                    del self.cache[sessao.chave]
        return pag, do_cache


def resultado_da_sessao(
    sessao: SessaoBusca, n: int, limites: LimitesBusca, forcado: Optional[str] = None, falha: Optional[PaginaBusca] = None,
) -> ResultadoBusca:
    """Fecha o resultado das `n` primeiras páginas da sessão (funil, motivo e avisos)."""
    paginas = sessao.paginas[:n]
    cortados: dict[str, int] = {}
    for p in paginas:
        for nome, qtd in p.cortados_por_filtro.items():
            cortados[nome] = cortados.get(nome, 0) + qtd
    referencia = falha or (paginas[-1] if paginas else None)
    if falha is not None:
        motivo, detalhe = "falha_fonte", falha.aviso
    elif forcado is not None:
        motivo, detalhe = forcado, None
    elif paginas and paginas[-1].parou_por is not None:
        motivo, detalhe = olx._MOTIVOS[paginas[-1].parou_por], paginas[-1].aviso
    else:
        motivo, detalhe = "falha_fonte", "a busca terminou sem motivo registrado"
    na_origem = referencia.na_origem if referencia else []
    resultado = montar_resultado(
        sessao.fonte.FONTE, [a for p in paginas for a in p.anuncios], len(paginas), sum(sessao.tempos[:n]),
        referencia.total_ads if referencia else None, sum(p.coletados for p in paginas), cortados, motivo,
        limites, detalhe, na_origem, referencia.nao_resolvidos if referencia else [],
        filtros_locais(sessao.busca, na_origem), busca=sessao.busca,
    )
    if paginas:
        resultado.coletado_em = sessao.quando[len(paginas) - 1]  # hora em que foi coletado, não a de agora
    return resultado


def percorrer(servico: Servico, sessao: SessaoBusca, limites: LimitesBusca, com_ping: bool) -> Iterator[tuple]:
    """Lê as páginas da sessão em ordem, até acabar, falhar ou bater os tetos de `limites` (o
    de páginas e o de tempo). Gera ("espera",) enquanto aguarda (se `com_ping`), ("pagina", PaginaBusca)
    a cada página e por fim ("fim", ResultadoBusca, veio_so_do_cache)."""
    inicio, n, do_cache_tudo = time.monotonic(), 0, True
    forcado: Optional[str] = None
    falha: Optional[PaginaBusca] = None
    executor = ThreadPoolExecutor(max_workers=1) if com_ping else None
    try:
        while True:
            if executor is None:
                pag, do_cache = servico.pagina(sessao, n + 1)
            else:
                futuro = executor.submit(servico.pagina, sessao, n + 1)
                while True:
                    try:
                        pag, do_cache = futuro.result(timeout=ESPERA_PING)
                        break
                    except FuturoTimeout:
                        yield ("espera",)
            if pag.parou_por == olx.BLOQUEIO:
                falha = pag
                break
            do_cache_tudo = do_cache_tudo and do_cache
            n += 1
            yield ("pagina", pag)
            if pag.parou_por is not None:
                break
            if n >= limites.max_paginas:
                forcado = "teto_paginas"
                break
            if time.monotonic() - inicio >= limites.tempo_max_segundos:
                forcado = "teto_tempo"
                break
    finally:
        if executor is not None:
            executor.shutdown(wait=False)
    yield ("fim", resultado_da_sessao(sessao, n, limites, forcado, falha), do_cache_tudo)


def pagina_resposta(sessao: SessaoBusca, n: int, pag: PaginaBusca, do_cache: bool, dev: bool) -> dict[str, Any]:
    """Resposta do "Ver mais": uma página, o total da fonte, quanto já foi entregue e se tem mais."""
    falhou = pag.parou_por == olx.BLOQUEIO
    alem_do_fim = not falhou and pag.numero != n  # pediu uma página depois da última
    ate = len(sessao.paginas) if alem_do_fim else (n - 1 if falhou else n)
    lidas = sessao.paginas[:ate]
    entregues = sum(len(p.anuncios) for p in lidas)
    cortados = sum(sum(p.cortados_por_filtro.values()) for p in lidas)
    terminou = not falhou and pag.parou_por is not None
    tem_mais = not terminou
    no_teto = terminou and pag.parou_por == olx.MAX_PAGINAS
    avisos = []
    if pag.nao_resolvidos:
        avisos.append(aviso_filtro_aproximado(sessao.fonte.FONTE, pag.nao_resolvidos, len(lidas), sessao.teto))
    if falhou:
        avisos.append(Aviso(
            codigo="fonte_parcial",
            mensagem=MSG_ERRO if not lidas else MSG_MAIS_FALHOU,
            detalhe_tecnico=pag.aviso or "sem detalhe",
        ))
    corpo: dict[str, Any] = {
        "pagina": n,
        "anuncios": [] if (falhou or alem_do_fim) else [_anuncio_json(a) for a in pag.anuncios],
        "tem_mais": tem_mais,
        "proxima_pagina": None if terminou else (n if falhou else n + 1),
        "entregues": entregues,
        "coletados": pag.acumulado,
        "total_na_fonte": pag.total_ads,
        "cortados_por_filtro": dict(pag.cortados_por_filtro) if not (falhou or alem_do_fim) else {},
        "motivo_parada": olx._MOTIVOS[pag.parou_por] if terminou else None,
        "falhou": falhou,
        "informacao": (
            (MSG_ERRO if not lidas else MSG_MAIS_FALHOU) if falhou
            else texto_informacao(entregues, pag.total_ads, tem_mais, cortados, no_teto, pag.acumulado)
        ),
        "avisos": _avisos_json(avisos, dev),
        "filtros_na_origem": pag.na_origem,
        "filtros_locais": filtros_locais(sessao.busca, pag.na_origem),
        "busca": sessao.busca.model_dump(mode="json"),
        "estado_aplicado": sessao.busca.estado or "todos",
        "coletado_em": sessao.quando[min(n, len(sessao.quando)) - 1].isoformat() if sessao.quando else None,
        "do_cache": do_cache,
    }
    return corpo


def criar_app(
    fonte: Fonte = olx,  # type: ignore[assignment]  # o módulo olx segue a interface Fonte
    ttl: float = config.CACHE_TTL_SEGUNDOS,
    estado_padrao: str = config.ESTADO_PADRAO,
    limites: Optional[LimitesBusca] = None,
    cors_origens: Optional[list[str]] = None,
    max_paginas_demanda: int = config.MAX_PAGINAS_SOB_DEMANDA,
) -> FastAPI:
    app = FastAPI(title="Garimpo Auto")
    app.add_middleware(
        CORSMiddleware, allow_origins=cors_origens if cors_origens is not None else config.CORS_ORIGENS,
        allow_methods=["GET"], allow_headers=["*"],
    )
    servico = Servico(fonte, ttl, limites, max_paginas_demanda)
    app.state.servico = servico

    @app.exception_handler(RequestValidationError)
    async def _pedido_ruim(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse({"erro": MSG_PEDIDO}, status_code=422)

    @app.exception_handler(PedidoInvalido)
    async def _pedido_invalido(request: Request, exc: PedidoInvalido) -> JSONResponse:
        return JSONResponse({"erro": str(exc)}, status_code=422)

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
        zona: Optional[str] = None,
        cidade: Optional[str] = None,
    ) -> Busca:
        estado = (estado or "").strip() or estado_padrao
        if estado.lower() == "todos":
            estado = None
        if regiao and regiao.strip() and estado and localidades.tem_dados(estado):
            # Só entra região que a OLX tem. Nome errado faria a OLX buscar no Brasil todo sem avisar.
            slug = localidades.achar_regiao(estado, regiao)
            if slug is None:
                raise PedidoInvalido(MSG_REGIAO)
            regiao = slug  # o endereço da OLX: escrever de jeitos diferentes não muda o cache
        if zona and zona.strip():
            if not (regiao and regiao.strip()):
                raise PedidoInvalido(MSG_ZONA_SEM_REGIAO)
            if estado and localidades.tem_dados(estado):
                achada = localidades.achar_zona(estado, regiao, zona)
                if achada is None:
                    raise PedidoInvalido(MSG_ZONA)
                zona = achada
        try:
            return Busca(
                texto=texto, marca=marca, modelo=modelo, versao=versao, ano_min=ano_min, ano_max=ano_max,
                preco_min=preco_min, preco_max=preco_max, km_min=km_min, km_max=km_max,
                cambio=cambio, combustivel=combustivel, anunciante=anunciante, ordenar=ordenar,
                estado=estado, regiao=regiao, zona=zona, cidade=cidade,
            )
        except ValidationError:
            raise RequestValidationError([])

    @app.get("/saude")
    def saude() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/regioes")
    def regioes(estado: Optional[str] = None) -> dict[str, Any]:
        """As regiões que a OLX tem em um estado, para o seletor da tela. Estado ausente usa o padrão."""
        uf = ((estado or "").strip() or estado_padrao).upper()
        if not localidades.tem_dados(uf):
            raise PedidoInvalido(MSG_PEDIDO)
        return {"estado": uf, "regioes": localidades.regioes(uf)}

    @app.get("/zonas")
    def zonas(regiao: Optional[str] = None, estado: Optional[str] = None) -> dict[str, Any]:
        """As zonas de uma região, para o seletor da tela (escolhe o estado, depois a região, depois a zona)."""
        uf = ((estado or "").strip() or estado_padrao).upper()
        if not localidades.tem_dados(uf):
            raise PedidoInvalido(MSG_PEDIDO)
        if not (regiao and regiao.strip()):
            raise PedidoInvalido(MSG_ZONA_SEM_REGIAO)
        slug = localidades.achar_regiao(uf, regiao)
        if slug is None:
            raise PedidoInvalido(MSG_REGIAO)
        return {"estado": uf, "regiao": slug, "zonas": localidades.zonas(uf, slug)}

    @app.get("/buscar/pagina")
    def pagina(
        busca: Busca = Depends(pedido), pagina: int = Query(1, ge=1, le=1000), dev: int = 0, atualizar: int = 0,
    ) -> JSONResponse:
        """Uma página por vez, para o "Ver mais". Pede a 1 e depois a `proxima_pagina` que vier na
        resposta. Página já lida volta do cache na hora. Use atualizar=1 só na página 1."""
        sessao = servico.obter(busca, atualizar == 1)
        pag, do_cache = servico.pagina(sessao, pagina, config.PAUSA_VER_MAIS_SEGUNDOS)  # o clique já espaça os pedidos
        return JSONResponse(pagina_resposta(sessao, pagina, pag, do_cache, dev == 1))

    @app.get("/buscar")
    def buscar(busca: Busca = Depends(pedido), dev: int = 0, atualizar: int = 0) -> JSONResponse:
        sessao = servico.obter(busca, atualizar == 1)
        resultado, do_cache = None, False
        try:
            for evento in percorrer(servico, sessao, servico.limites, com_ping=False):
                if evento[0] == "fim":
                    resultado, do_cache = evento[1], evento[2]
        except Exception:
            resultado = None
        if resultado is None:
            return JSONResponse({"erro": MSG_ERRO}, status_code=500)
        return JSONResponse(resultado_json(resultado, dev == 1, do_cache))

    @app.get("/buscar/stream")
    def stream(busca: Busca = Depends(pedido), dev: int = 0, atualizar: int = 0) -> StreamingResponse:
        sessao = servico.obter(busca, atualizar == 1)

        def eventos() -> Iterator[str]:
            try:
                for evento in percorrer(servico, sessao, servico.limites, com_ping=True):
                    if evento[0] == "espera":
                        yield ": aguardando\n\n"  # sinal de vida enquanto espera a vez ou a OLX
                    elif evento[0] == "pagina":
                        yield sse("pagina", pagina_json(evento[1], servico.limites.max_paginas))
                    else:
                        fim = resultado_json(evento[1], dev == 1, evento[2])
                        fim.pop("anuncios")  # já foram nos eventos "pagina"
                        yield sse("fim", fim)
            except Exception:
                yield sse("erro", {"mensagem": MSG_ERRO})

        return StreamingResponse(
            eventos(), media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app


app = criar_app()
