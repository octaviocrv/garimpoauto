"""Aquece o cache FIPE com os anúncios das páginas de busca ainda guardadas."""

from __future__ import annotations

import argparse
from collections import Counter
import sys

import config
from armazem import Armazem, BancoFora
from casamento_fipe import CasadorFipe
from catalogo_fipe import CatalogoFipe
from schemas import Anuncio
from sources.fipe import FipeOnline, FonteFipeIndisponivel, LimiteFipeAtingido


def ordenar_por_modelo_comum(anuncios: list[Anuncio]) -> list[Anuncio]:
    frequencia = Counter(
        ((a.marca or "").lower(), (a.modelo or "").lower())
        for a in anuncios if a.marca and a.modelo
    )
    return sorted(
        anuncios,
        key=lambda a: (
            -frequencia[((a.marca or "").lower(), (a.modelo or "").lower())],
            (a.marca or "").lower(), (a.modelo or "").lower(), a.external_id,
        ),
    )


class OrcamentoExecucao:
    def __init__(self, armazem: Armazem, limite_execucao: int, limite_dia: int) -> None:
        self.armazem, self.limite_execucao, self.limite_dia = armazem, limite_execucao, limite_dia
        self.usadas = 0

    def reservar(self) -> bool:
        if self.usadas >= self.limite_execucao:
            return False
        if not self.armazem.fipe_reservar_requisicao(self.limite_dia):
            return False
        self.usadas += 1
        return True


def executar(orcamento: int) -> tuple[dict[str, int], int, int]:
    if not config.DATABASE_URL:
        raise RuntimeError("Falta GARIMPO_DATABASE_URL no .env")
    armazem = Armazem(config.DATABASE_URL, confere_segundos=config.BANCO_CONFERE_SEGUNDOS)
    armazem.migrar()
    anuncios = ordenar_por_modelo_comum(armazem.fipe_anuncios_para_aquecer())
    if not anuncios:
        return armazem.fipe_resumo_casamentos(), 0, 0

    controle = OrcamentoExecucao(armazem, orcamento, config.FIPE_LIMITE_DIA)
    fonte = FipeOnline(
        token=config.FIPE_TOKEN,
        timeout=config.FIPE_TIMEOUT_REQUISICAO_SEGUNDOS,
        repeticoes=config.FIPE_REPETICOES,
        backoff=config.FIPE_BACKOFF_SEGUNDOS,
        pausa=config.FIPE_PAUSA_SEGUNDOS,
        reservar=controle.reservar,
    )
    catalogo = CatalogoFipe(armazem, fonte)
    casador = CasadorFipe(catalogo, armazem)
    processados = 0
    referencia = None
    for anuncio in anuncios:
        try:
            resultado = casador.casar(anuncio)
            processados += 1
            if referencia is None:
                referencia = resultado.referencia_codigo
            if referencia:
                armazem.fipe_salvar_estado(
                    referencia, "aquecimento", "anuncios",
                    {"fonte": anuncio.source, "anuncio_id": anuncio.external_id, "processados": processados},
                )
        except LimiteFipeAtingido:
            break
        except FonteFipeIndisponivel:
            break
    return armazem.fipe_resumo_casamentos(), processados, controle.usadas


def main() -> None:
    parser = argparse.ArgumentParser(description="Aquece a FIPE dos carros já carregados")
    parser.add_argument("--orcamento", type=int, default=100, help="Máximo de chamadas nesta execução")
    args = parser.parse_args()
    if args.orcamento < 1:
        sys.exit("O orçamento precisa ser pelo menos 1")
    try:
        resumo, processados, chamadas = executar(args.orcamento)
    except BancoFora:
        sys.exit("Banco fora do ar. Nenhuma chamada à FIPE foi feita.")
    except RuntimeError as erro:
        sys.exit(str(erro))
    print(f"Anúncios processados {processados}")
    print(f"Chamadas usadas nesta execução {chamadas}")
    print(f"Confiança alta {resumo.get('alta', 0)}")
    print(f"Confiança média {resumo.get('media', 0)}")
    print(f"Confiança baixa {resumo.get('baixa', 0)}")
    print(f"Sem candidato {resumo.get('sem_candidato', 0)}")


if __name__ == "__main__":
    main()
