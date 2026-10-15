"""Enriquece uma página com FIPE sem atrasar a busca além do teto configurado."""

from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
import logging
import threading
import time
from typing import Optional

import config
from armazem import Armazem, BancoFora
from casamento_fipe import CasadorFipe, CasamentoFipe, bloqueio_do_anuncio, chave_combinacao, hash_entrada
from catalogo_fipe import CatalogoFipe
from schemas import Anuncio, MotivoAusenciaFipe, ReferenciaFipe
from sources.fipe import FipeOnline, FonteFipeIndisponivel, LimiteFipeAtingido

log = logging.getLogger("garimpo.fipe")


class EnriquecedorFipe:
    def __init__(
        self, casador: CasadorFipe, armazem: Armazem, *, tempo_pagina: float, paralelismo: int = 2,
        monotonic=time.monotonic,
    ) -> None:
        self.casador, self.armazem = casador, armazem
        self.tempo_pagina, self.monotonic = tempo_pagina, monotonic
        self.executor = ThreadPoolExecutor(max_workers=min(2, max(1, paralelismo)), thread_name_prefix="fipe")
        self._avisados: set[str] = set()
        self._trava_aviso = threading.Lock()
        self._ausencias: list[dict[str, str]] = []
        self._trava_ausencias = threading.Lock()

    def _avisar_uma_vez(self, chave: str, mensagem: str) -> None:
        with self._trava_aviso:
            if chave in self._avisados:
                return
            self._avisados.add(chave)
        log.warning(mensagem)

    def _enfileirar_ausencia(
        self, anuncio: Anuncio, motivo: MotivoAusenciaFipe, detalhe: str,
    ) -> None:
        chave = (anuncio.source, anuncio.external_id, hash_entrada(anuncio), motivo)
        with self._trava_ausencias:
            self._ausencias.append({
                "fonte": chave[0], "anuncio_id": chave[1], "entrada_hash": chave[2],
                "motivo": motivo, "detalhe": detalhe,
            })

    def _descarregar_ausencias(self) -> None:
        if self.armazem.fora:
            return
        with self._trava_ausencias:
            ocorrencias = list(self._ausencias)
            self._ausencias.clear()
        if not ocorrencias:
            return
        try:
            self.armazem.fipe_salvar_ausencias(ocorrencias)
        except BancoFora:
            with self._trava_ausencias:
                self._ausencias.extend(ocorrencias)
        except Exception:
            with self._trava_ausencias:
                self._ausencias.extend(ocorrencias)
            log.exception("Erro ao guardar motivo da ausência da FIPE.")

    def _despachar_ausencias(self) -> None:
        with self._trava_ausencias:
            tem_ausencias = bool(self._ausencias)
        if tem_ausencias and not self.armazem.fora:
            self.executor.submit(self._descarregar_ausencias)

    def _casar(
        self, indice: int, anuncio: Anuncio,
    ) -> tuple[int, Optional[CasamentoFipe], Optional[MotivoAusenciaFipe]]:
        try:
            return indice, self.casador.casar(anuncio), None
        except BancoFora:
            self._avisar_uma_vez("banco", "Banco fora do ar. A busca segue sem consultar a FIPE.")
            motivo: MotivoAusenciaFipe = "banco_fora"
            detalhe = "Banco fora do ar"
        except LimiteFipeAtingido:
            self._avisar_uma_vez("limite", "Limite diário da FIPE atingido. A busca segue sem novos valores.")
            motivo = "sem_orcamento"
            detalhe = "Limite diário da FIPE atingido"
        except FonteFipeIndisponivel:
            self._avisar_uma_vez("fonte", "A FIPE não respondeu. A busca segue normalmente.")
            motivo = "fonte_indisponivel"
            detalhe = "Fonte FIPE indisponível"
        except Exception:
            log.exception("Erro ao enriquecer anúncio com FIPE.")
            motivo = "erro_inesperado"
            detalhe = "Erro inesperado ao consultar a FIPE"
        self._enfileirar_ausencia(anuncio, motivo, detalhe)
        self._despachar_ausencias()
        return indice, None, motivo

    @staticmethod
    def _aplicar(anuncio: Anuncio, resultado: CasamentoFipe) -> None:
        anuncio.fipe_bloqueio = resultado.bloqueio
        if (
            resultado.confianca != "alta" or resultado.codigo_fipe is None
            or resultado.preco is None or resultado.mes_referencia is None or anuncio.preco is None
        ):
            anuncio.fipe = None
            anuncio.fipe_ausencia = {
                "sem_candidato": "sem_candidato",
                "media": "confianca_media",
                "baixa": "confianca_baixa",
            }.get(resultado.confianca, "sem_candidato")
            return
        diferenca = round((resultado.preco - anuncio.preco) / resultado.preco * 100)
        anuncio.fipe = ReferenciaFipe(
            codigo=resultado.codigo_fipe,
            preco=resultado.preco,
            diferenca_percentual=diferenca,
            mes_referencia=resultado.mes_referencia,
            confianca="alta",
            preco_estranho=resultado.preco_estranho,
        )
        anuncio.fipe_ausencia = None

    def enriquecer(self, anuncios: list[Anuncio]) -> None:
        self._despachar_ausencias()
        if not anuncios or self.armazem.fora:
            if self.armazem.fora:
                self._avisar_uma_vez("banco", "Banco fora do ar. A busca segue sem consultar a FIPE.")
                for anuncio in anuncios:
                    anuncio.fipe_ausencia = "banco_fora"
                    self._enfileirar_ausencia(anuncio, "banco_fora", "Banco fora do ar")
            return
        prazo = self.monotonic() + self.tempo_pagina
        proximo = 0
        pendentes: dict[Future, int] = {}

        def agendar() -> None:
            nonlocal proximo
            while proximo < len(anuncios) and len(pendentes) < 2:
                futuro = self.executor.submit(self._casar, proximo, anuncios[proximo])
                pendentes[futuro] = proximo
                proximo += 1

        agendar()
        while pendentes:
            restante = prazo - self.monotonic()
            if restante <= 0:
                break
            concluidos, _ = wait(tuple(pendentes), timeout=restante, return_when=FIRST_COMPLETED)
            if not concluidos:
                break
            for futuro in concluidos:
                pendentes.pop(futuro, None)
                indice, resultado, ausencia = futuro.result()
                if resultado is not None:
                    self._aplicar(anuncios[indice], resultado)
                elif ausencia is not None:
                    anuncios[indice].fipe_ausencia = ausencia
            agendar()
        sem_tempo = set(pendentes.values()) | set(range(proximo, len(anuncios)))
        for indice in sem_tempo:
            anuncios[indice].fipe_ausencia = "tempo_esgotado"
            self._enfileirar_ausencia(
                anuncios[indice], "tempo_esgotado", "Tempo da FIPE esgotado nesta página",
            )
        self._despachar_ausencias()

    def carregar_cache(self, anuncios: list[Anuncio]) -> None:
        if self.armazem.fora:
            return
        for anuncio in anuncios:
            try:
                resultado = self.casador.guardado(anuncio)
            except BancoFora:
                self._avisar_uma_vez("banco", "Banco fora do ar. A busca segue sem consultar a FIPE.")
                return
            if resultado is not None:
                self._aplicar(anuncio, resultado)

    def resolver_busca(self, anuncios: list[Anuncio]) -> None:
        grupos: dict[tuple[object, ...], list[Anuncio]] = {}
        for anuncio in anuncios:
            grupos.setdefault(chave_combinacao(anuncio), []).append(anuncio)

        def elegivel(anuncio: Anuncio) -> bool:
            return (
                bloqueio_do_anuncio(anuncio) is None
                and bool(anuncio.marca and anuncio.modelo and anuncio.ano is not None)
                and bool(anuncio.combustivel and anuncio.preco is not None and anuncio.preco > 0)
            )

        representantes: dict[tuple[object, ...], Anuncio] = {}
        for chave, grupo in grupos.items():
            guardado = next((
                anuncio for anuncio in grupo
                if anuncio.fipe is not None
                or anuncio.fipe_ausencia in {"confianca_media", "confianca_baixa"}
                or (anuncio.fipe_ausencia == "sem_candidato" and elegivel(anuncio))
            ), None)
            apto = next((anuncio for anuncio in grupo if elegivel(anuncio)), None)
            representantes[chave] = guardado or apto or grupo[0]
        self.enriquecer(list(representantes.values()))
        for chave, grupo in grupos.items():
            base = representantes[chave]
            if base.fipe is None and base.fipe_ausencia in {
                "sem_orcamento", "tempo_esgotado", "banco_fora", "fonte_indisponivel", "erro_inesperado",
            }:
                continue
            try:
                resultado = self.casador.guardado(base)
            except BancoFora:
                self._avisar_uma_vez("banco", "Banco fora do ar. A busca segue sem consultar a FIPE.")
                return
            if resultado is None:
                continue
            for anuncio in grupo:
                if anuncio is base:
                    continue
                try:
                    reaproveitado = self.casador.reaproveitar(anuncio, resultado)
                except BancoFora:
                    self._avisar_uma_vez("banco", "Banco fora do ar. A busca segue sem consultar a FIPE.")
                    return
                self._aplicar(anuncio, reaproveitado)

    def resolver(self, anuncio: Anuncio) -> None:
        self.enriquecer([anuncio])


def criar_enriquecedor(armazem: Optional[Armazem]) -> Optional[EnriquecedorFipe]:
    if armazem is None:
        return None
    fonte = FipeOnline(
        token=config.FIPE_TOKEN,
        timeout=config.FIPE_TIMEOUT_REQUISICAO_SEGUNDOS,
        repeticoes=config.FIPE_REPETICOES,
        backoff=config.FIPE_BACKOFF_SEGUNDOS,
        pausa=config.FIPE_PAUSA_SEGUNDOS,
        reservar=lambda: armazem.fipe_reservar_requisicao(config.FIPE_LIMITE_DIA),
    )
    catalogo = CatalogoFipe(armazem, fonte)
    casador = CasadorFipe(catalogo, armazem)
    return EnriquecedorFipe(casador, armazem, tempo_pagina=config.FIPE_TEMPO_PAGINA_SEGUNDOS)
