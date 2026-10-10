"""Enriquece uma página com FIPE sem atrasar a busca além do teto configurado."""

from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
import logging
import threading
import time
from typing import Optional

import config
from armazem import Armazem, BancoFora
from casamento_fipe import CasadorFipe, CasamentoFipe
from catalogo_fipe import CatalogoFipe
from schemas import Anuncio, ReferenciaFipe
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

    def _avisar_uma_vez(self, chave: str, mensagem: str) -> None:
        with self._trava_aviso:
            if chave in self._avisados:
                return
            self._avisados.add(chave)
        log.warning(mensagem)

    def _casar(self, indice: int, anuncio: Anuncio) -> tuple[int, Optional[CasamentoFipe]]:
        try:
            return indice, self.casador.casar(anuncio)
        except BancoFora:
            self._avisar_uma_vez("banco", "Banco fora do ar. A busca segue sem consultar a FIPE.")
        except LimiteFipeAtingido:
            self._avisar_uma_vez("limite", "Limite diário da FIPE atingido. A busca segue sem novos valores.")
        except FonteFipeIndisponivel:
            self._avisar_uma_vez("fonte", "A FIPE não respondeu. A busca segue normalmente.")
        except Exception:
            log.exception("Erro ao enriquecer anúncio com FIPE.")
        return indice, None

    @staticmethod
    def _aplicar(anuncio: Anuncio, resultado: CasamentoFipe) -> None:
        anuncio.fipe_bloqueio = resultado.bloqueio
        if (
            resultado.confianca != "alta" or resultado.codigo_fipe is None
            or resultado.preco is None or resultado.mes_referencia is None or anuncio.preco is None
        ):
            anuncio.fipe = None
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

    def enriquecer(self, anuncios: list[Anuncio]) -> None:
        if not anuncios or self.armazem.fora:
            if self.armazem.fora:
                self._avisar_uma_vez("banco", "Banco fora do ar. A busca segue sem consultar a FIPE.")
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
                indice, resultado = futuro.result()
                if resultado is not None:
                    self._aplicar(anuncios[indice], resultado)
            agendar()


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
