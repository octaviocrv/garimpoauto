"""API do Garimpo Auto. Sobe com:  .venv/bin/uvicorn server:app --port 8000

GET /saude          confere que subiu
GET /buscar         ResultadoBusca completo em JSON
GET /buscar/stream  o mesmo por SSE: um evento "pagina" por página, "fim" com funil, motivo_parada
                    e avisos, e "erro" (em tom humano) se algo quebrar

Parâmetros: texto (obrigatório, mas pode vir vazio: aí é a vitrine do estado), marca, modelo, versao, ano_min, ano_max, preco_min, preco_max,
km_min, km_max, cambio, combustivel, anunciante (particular ou profissional), ordenar (recentes,
menor_preco ou relevancia, padrão recentes), estado, regiao, cidade, dev, atualizar (1 ignora o
cache e coleta de novo). Estado ausente usa config.ESTADO_PADRAO, "todos" busca no Brasil
todo. Com dev=1 os avisos trazem o detalhe_tecnico, senão ele nem aparece.

Cache com a chave de busca.chave_busca e TTL de config.CACHE_TTL_SEGUNDOS. Com GARIMPO_DATABASE_URL
ele fica no banco (MariaDB ou MySQL) e é compartilhado entre os usuários e sobrevive a reinício. Sem
o banco, ou com o banco fora do ar, fica só em memória. A mesma busca em andamento é compartilhada e
só roda uma coleta real por vez (as outras esperam na fila).
A resposta nunca leva o item cru da fonte nem dado de anunciante.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturoTimeout
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator, Optional

from fastapi import Depends, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import ValidationError

import config
import localidades
from armazem import Armazem, BancoFora, hash_da_chave
from busca import aviso_filtro_aproximado, chave_busca, filtros_locais, montar_resultado, texto_informacao
from config import LimitesBusca
from schemas import Anuncio, Aviso, Busca, PaginaBusca, ResultadoBusca
from sources import olx
from sources.base import Fonte

log = logging.getLogger("garimpo.banco")  # o mesmo do banco, para as mensagens saírem juntas

MSG_ERRO = "Não achei esse carro agora, tenta de novo?"
MSG_MAIS_FALHOU = "Não consegui buscar mais agora, tenta de novo daqui a pouco?"
MSG_PEDIDO = "Esse pedido de busca não está certo, confere os filtros?"
MSG_REGIAO = "Não achei essa região nesse estado, escolhe uma da lista?"
MSG_ZONA = "Não achei essa zona, escolhe uma da lista?"
MSG_ZONA_SEM_REGIAO = "Pra escolher a zona, escolhe a região primeiro."
ESPERA_PING = 15.0  # segundos sem novidade até mandar um sinal de vida no stream


def _anuncio_json(a: Anuncio) -> dict[str, Any]:
    d = a.to_dict(com_raw=False)  # sem o item cru da fonte
    d["anunciado_em"] = a.anunciado_em.isoformat() if a.anunciado_em else None  # renovação, senão publicação
    return d


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
        "novos": sum(1 for a in p.anuncios if a.novo),
    }


def com_novidades(corpo: dict[str, Any], r: ResultadoBusca, sessao: SessaoBusca) -> dict[str, Any]:
    """Junta no resultado quantos carros são novos desde a última busca igual."""
    corpo["novos"] = sum(1 for a in r.anuncios if a.novo)
    corpo["primeira_busca"] = sessao.primeira_busca
    return corpo


def sse(evento: str, dados: Any) -> str:
    return f"event: {evento}\ndata: {json.dumps(dados, ensure_ascii=False)}\n\n"


class PedidoInvalido(Exception):
    """Pedido que a pessoa pode corrigir. A mensagem já está pronta para a tela."""


class SessaoBusca:
    """Uma busca guardada por chave: as páginas já lidas e o cursor da fonte para ler a próxima.
    Quem pede a mesma busca divide a sessão, e página lida nunca é baixada de novo. A trava deixa
    uma leitura por vez por busca, então pedidos iguais e simultâneos esperam em vez de repetir.

    Com o banco ligado (`armazem`), cada página lida é gravada nele junto com o ponto onde a busca
    continua. Assim a sessão sobrevive a reinício e outro servidor continua dela. Se o banco falhar,
    a sessão segue só na memória até vencer."""

    def __init__(
        self, chave: str, fonte: Fonte, busca: Busca, limites: LimitesBusca, teto: int, semaforo: threading.Semaphore,
        armazem: Optional[Armazem] = None, ttl: float = config.CACHE_TTL_SEGUNDOS, usuario: str = "",
    ) -> None:
        self.chave, self.fonte, self.busca, self.limites, self.teto = chave, fonte, busca, limites, teto
        self.semaforo = semaforo
        self.armazem, self.ttl, self.usuario = armazem, ttl, usuario
        self.trava = threading.Lock()
        self.cursor: Any = None
        self.paginas: list[PaginaBusca] = []
        self.tempos: list[float] = []  # segundos que cada página levou (pausa e leitura)
        self.quando: list[datetime] = []  # hora em que cada página foi lida
        self.valida_ate: Optional[float] = None  # começa a contar quando a 1ª página chega
        # Banco: db_id vazio com persistir ligado quer dizer "ainda não registrada" (o banco estava fora)
        self.db_id: Optional[int] = None
        self.persistir = armazem is not None
        self.execucao_id: Optional[int] = None
        self.anterior_em: Optional[datetime] = None
        self.estado_cursor: Optional[dict[str, Any]] = None  # onde a busca continua, vindo do banco

    @property
    def terminou(self) -> bool:
        return bool(self.paginas) and self.paginas[-1].parou_por is not None

    @property
    def primeira_busca(self) -> Optional[bool]:
        """True se não existe busca igual anterior. None quando não dá para saber (sem banco)."""
        return None if (self.db_id is None or self.execucao_id is None) else self.anterior_em is None

    def vigente(self, agora: float) -> bool:
        return self.valida_ate is None or agora < self.valida_ate

    def _sem_banco(self, motivo: str) -> None:
        if self.persistir:
            log.warning("Sessão de busca segue só na memória (%s): %s", motivo, self.chave)
        self.persistir = False

    def _sincronizar(self) -> None:
        """Traz as páginas que outro servidor já leu e guardou no banco."""
        if not (self.persistir and self.db_id is not None and self.armazem):
            return
        try:
            guardada = self.armazem.carregar_sessao(hash_da_chave(self.chave), len(self.paginas))
        except BancoFora:
            return
        if guardada is None or guardada.id != self.db_id or not guardada.paginas:
            return
        for pag, tempo, quando in guardada.paginas:
            self.paginas.append(pag)
            self.tempos.append(tempo)
            self.quando.append(quando.replace(tzinfo=timezone.utc))
        self.estado_cursor, self.cursor = guardada.estado_cursor, None  # o cursor continua do ponto novo
        if self.valida_ate is None and guardada.valida_ate is not None:
            self.valida_ate = time.monotonic() + max(0.0, (guardada.valida_ate - self.armazem.agora()).total_seconds())

    def _abrir_cursor(self) -> Any:
        cursor = self.fonte.abrir(self.busca, self.limites, teto=self.teto)
        if self.estado_cursor is not None and hasattr(cursor, "restaurar"):
            cursor.restaurar(self.estado_cursor)
        return cursor

    def _guardar(self, pag: PaginaBusca, tempo: float, quando: datetime) -> None:
        """Marca os anúncios novos e grava a página no banco. Qualquer falha do banco só tira a sessão
        do banco, a busca continua."""
        if not (self.persistir and self.armazem):
            return
        if not hasattr(self.cursor, "exportar"):
            return self._sem_banco("a fonte não sabe exportar onde parou")
        try:
            if self.db_id is None:
                if self.paginas:  # nasceu com o banco fora e já tem páginas: não dá para guardar com buraco
                    return self._sem_banco("nasceu sem o banco")
                self.db_id, self.execucao_id, self.anterior_em = self.armazem.criar_sessao(
                    hash_da_chave(self.chave), self.chave, self.busca.model_dump_json(), self.usuario
                )
            self.armazem.marcar_vistos(hash_da_chave(self.chave), self.execucao_id, self.anterior_em, pag.anuncios, self.usuario)
            valida = None
            if not self.paginas:
                valida = self.armazem.agora() + timedelta(seconds=self.ttl)
            self.armazem.salvar_pagina(self.db_id, pag, tempo, quando.replace(tzinfo=None), self.cursor.exportar(), valida)
        except BancoFora:
            self._sem_banco("o banco saiu do ar")
        except Exception:
            log.exception("Erro ao guardar a página %s no banco. A sessão segue só na memória.", pag.numero)
            self._sem_banco("erro ao gravar")

    def pagina(
        self, n: int, ttl: float, pausa: Optional[tuple[float, float]] = None, ver_mais: bool = False,
    ) -> tuple[PaginaBusca, bool]:
        """Página `n` (a partir de 1) e se veio do cache. Lê da fonte só o que falta, na ordem. Se
        a fonte falhar devolve uma página com parou_por "bloqueio" que NÃO é guardada (pedir de novo
        tenta ler essa mesma página). Se a busca acabou antes de `n`, devolve a última página. Com
        `ver_mais`, a leitura da página 2 em diante repete menos vezes e espera pouco (a 1ª não muda)."""
        with self.trava:
            if len(self.paginas) < n:
                self._sincronizar()
            do_cache = n <= len(self.paginas)
            while len(self.paginas) < n and not self.terminou:
                inicio = time.monotonic()
                try:
                    if self.cursor is None:
                        self.cursor = self._abrir_cursor()
                    self.cursor.esperar(pausa)  # pausa fora do semáforo, para não travar a busca dos outros
                    with self.semaforo:  # só uma leitura real por vez
                        if ver_mais and self.paginas:
                            pag = self.cursor.proxima(config.REPETICOES_VER_MAIS, config.ESPERA_REPETICAO_VER_MAIS_SEGUNDOS)
                        else:
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
                agora_utc = datetime.now(timezone.utc)
                tempo, quando = time.monotonic() - inicio, agora_utc.replace(microsecond=agora_utc.microsecond // 1000 * 1000)  # o banco guarda até milissegundos
                self._guardar(pag, tempo, quando)
                self.paginas.append(pag)
                self.tempos.append(tempo)
                self.quando.append(quando)
                if len(self.paginas) == 1:
                    self.valida_ate = time.monotonic() + ttl
            return self.paginas[min(n, len(self.paginas)) - 1], do_cache


class Servico:
    """Sessões de busca em memória e, se houver, no banco, com a chave de busca e o TTL, e uma leitura
    real por vez. O banco é o que vale entre servidores e reinícios, a memória é só um atalho."""

    def __init__(
        self, fonte: Fonte, ttl: float, limites: Optional[LimitesBusca] = None, teto: int = config.MAX_PAGINAS_SOB_DEMANDA,
        armazem: Optional[Armazem] = None,
    ) -> None:
        self.fonte, self.ttl, self.limites, self.teto = fonte, ttl, limites or LimitesBusca(), teto
        self.armazem = armazem
        self.trava = threading.Lock()
        self.semaforo = threading.Semaphore(1)
        self.cache: dict[str, SessaoBusca] = {}
        self._limpou_em = 0.0

    def _nova(self, chave: str, busca: Busca) -> SessaoBusca:
        return SessaoBusca(chave, self.fonte, busca, self.limites, self.teto, self.semaforo, self.armazem, self.ttl)

    def _do_banco(self, chave: str, busca: Busca, id_: int) -> Optional[SessaoBusca]:
        """Monta a sessão guardada no banco, com as páginas e o ponto onde a busca continua."""
        assert self.armazem is not None
        guardada = self.armazem.carregar_sessao(hash_da_chave(chave))
        if guardada is None or guardada.id != id_ or (guardada.estado_cursor is None and guardada.paginas):
            return None
        sessao = self._nova(chave, busca)
        sessao.db_id, sessao.execucao_id, sessao.anterior_em = guardada.id, guardada.execucao_id, guardada.anterior_em
        sessao.estado_cursor = guardada.estado_cursor
        for pag, tempo, quando in guardada.paginas:
            sessao.paginas.append(pag)
            sessao.tempos.append(tempo)
            sessao.quando.append(quando.replace(tzinfo=timezone.utc))
        if guardada.valida_ate is not None:
            sessao.valida_ate = time.monotonic() + max(0.0, (guardada.valida_ate - self.armazem.agora()).total_seconds())
        return sessao

    def _limpar_banco(self, agora: float) -> None:
        if self.armazem is None or agora - self._limpou_em < 60:
            return
        self._limpou_em = agora
        try:
            self.armazem.limpar_vencidas(self.ttl)
        except BancoFora:
            pass

    def obter(self, busca: Busca, atualizar: bool = False) -> SessaoBusca:
        """A sessão da busca. `atualizar` joga fora a sessão guardada e começa outra, a menos que
        ela esteja lendo uma página agora (aí divide essa leitura). Com o banco, a sessão guardada
        vale para todos os servidores: quem não a tem na memória a busca lá."""
        chave, agora = chave_busca(busca), time.monotonic()
        with self.trava:
            self.cache = {k: s for k, s in self.cache.items() if s.vigente(agora)}
            self._limpar_banco(agora)
            sessao = self.cache.get(chave)
            if sessao is not None and not sessao.persistir and sessao.armazem is not None:
                # Sessão só de memória (o banco falhou). Vale até vencer, salvo "atualizar".
                if not (atualizar and not sessao.trava.locked()):
                    return sessao
            if atualizar and sessao is not None and not sessao.trava.locked():
                sessao = None
                apagar = True
            else:
                apagar = atualizar and sessao is None
            if self.armazem is not None:
                sessao = self._conferir_no_banco(chave, busca, sessao, apagar)
            if sessao is None:
                sessao = self._nova(chave, busca)
            self.cache[chave] = sessao
            return sessao

    def _conferir_no_banco(self, chave: str, busca: Busca, local: Optional[SessaoBusca], apagar: bool) -> Optional[SessaoBusca]:
        """Acerta a sessão da memória com a do banco. Devolve None se for preciso começar uma nova (já criada
        no banco, quando ele está de pé)."""
        assert self.armazem is not None
        h = hash_da_chave(chave)
        try:
            guardada = self.armazem.espiar(h, self.ttl)
            if apagar and guardada is not None:
                self.armazem.apagar_sessao(guardada[0])
                guardada = None
            if local is not None and guardada is not None and local.db_id == guardada[0]:
                return local
            if guardada is not None:
                return self._do_banco(chave, busca, guardada[0])  # outro servidor abriu ou trocou a sessão
            if local is not None and local.db_id is None:
                return local  # ainda sem página (o banco registra na 1ª) ou nasceu sem o banco e fica na memória
            # o banco não tem mais a sessão da memória (venceu ou foi trocada)
            nova = self._nova(chave, busca)
            nova.db_id, nova.execucao_id, nova.anterior_em = self.armazem.criar_sessao(
                h, chave, busca.model_dump_json(), nova.usuario
            )
            return nova
        except BancoFora:
            return local  # sem banco: segue com o que tem na memória (ou uma sessão nova só de memória)

    def pagina(
        self, sessao: SessaoBusca, n: int, pausa: Optional[tuple[float, float]] = None, ver_mais: bool = False,
    ) -> tuple[PaginaBusca, bool]:
        pag, do_cache = sessao.pagina(n, self.ttl, pausa, ver_mais)
        if pag.parou_por == olx.BLOQUEIO and not sessao.paginas:
            with self.trava:  # falha na 1ª página não fica no cache
                if self.cache.get(sessao.chave) is sessao:
                    del self.cache[sessao.chave]
            if sessao.db_id is not None and self.armazem is not None:
                try:
                    self.armazem.apagar_sessao(sessao.db_id)
                except BancoFora:
                    pass
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
        "novos": sum(1 for p in lidas for a in p.anuncios if a.novo),  # carros novos desde a última busca igual
        "primeira_busca": sessao.primeira_busca,  # True: não tinha busca igual antes. None: sem banco
    }
    return corpo


def criar_app(
    fonte: Fonte = olx,  # type: ignore[assignment]  # o módulo olx segue a interface Fonte
    ttl: float = config.CACHE_TTL_SEGUNDOS,
    estado_padrao: str = config.ESTADO_PADRAO,
    limites: Optional[LimitesBusca] = None,
    cors_origens: Optional[list[str]] = None,
    max_paginas_demanda: int = config.MAX_PAGINAS_SOB_DEMANDA,
    armazem: Optional[Armazem] = None,
) -> FastAPI:
    """`armazem` liga o cache no banco. Sem ele o cache é só de memória, como antes."""
    app = FastAPI(title="Garimpo Auto")
    app.add_middleware(
        CORSMiddleware, allow_origins=cors_origens if cors_origens is not None else config.CORS_ORIGENS,
        allow_methods=["GET"], allow_headers=["*"],
    )
    servico = Servico(fonte, ttl, limites, max_paginas_demanda, armazem)
    app.state.servico = servico

    @app.on_event("startup")
    def _preparar_banco() -> None:
        """Ao subir, confere o banco e aplica as migrations. Se ele estiver fora, o servidor sobe do mesmo jeito."""
        if armazem is None:
            return
        try:
            armazem.migrar()
            log.info("Banco conectado. O cache de busca fica nele.")
        except BancoFora:
            log.error("Subi sem o banco. A busca usa só a memória até ele voltar.")

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
        texto: str = Query(...),  # o parâmetro é obrigatório, mas pode vir vazio (texto=): é a vitrine do estado
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
        pag, do_cache = servico.pagina(sessao, pagina, config.PAUSA_VER_MAIS_SEGUNDOS, ver_mais=True)  # o clique já espaça os pedidos
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
        return JSONResponse(com_novidades(resultado_json(resultado, dev == 1, do_cache), resultado, sessao))

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
                        fim = com_novidades(resultado_json(evento[1], dev == 1, evento[2]), evento[1], sessao)
                        fim.pop("anuncios")  # já foram nos eventos "pagina"
                        yield sse("fim", fim)
            except Exception:
                yield sse("erro", {"mensagem": MSG_ERRO})

        return StreamingResponse(
            eventos(), media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app


app = criar_app(armazem=Armazem(config.DATABASE_URL, confere_segundos=config.BANCO_CONFERE_SEGUNDOS) if config.DATABASE_URL else None)
