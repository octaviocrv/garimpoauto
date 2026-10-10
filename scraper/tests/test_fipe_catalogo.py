import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from catalogo_fipe import CatalogoFipe  # noqa: E402
from sources.fipe import AnoFonte, OpcaoFonte, PrecoFonte, ReferenciaFonte  # noqa: E402
from tests.apoio_banco import RelogioBanco, novo_armazem, zerar_banco_de_teste  # noqa: E402


@pytest.fixture
def banco():
    zerar_banco_de_teste()
    armazem = novo_armazem(RelogioBanco())
    armazem.migrar()
    yield armazem
    armazem.fechar()


class FonteContada:
    def __init__(self):
        self.chamadas = []

    def referencias(self):
        self.chamadas.append("referencias")
        return [ReferenciaFonte("338", "outubro/2026")]

    def marcas(self, referencia):
        self.chamadas.append(f"marcas {referencia}")
        return [OpcaoFonte("59", "VW - VolksWagen")]

    def modelos(self, referencia, marca):
        self.chamadas.append(f"modelos {referencia} {marca}")
        return [OpcaoFonte("6786", "Gol Trendline 1.0 T.Flex 8V 5p")]

    def anos(self, referencia, marca, modelo):
        self.chamadas.append(f"anos {referencia} {marca} {modelo}")
        return [AnoFonte("2016-5", "2016 Flex", 2016, "5", "Flex")]

    def preco(self, referencia, marca, modelo, ano):
        self.chamadas.append(f"preco {referencia} {marca} {modelo} {ano}")
        return PrecoFonte(
            "005384-8", Decimal("39351.00"), "outubro de 2026", "VW - VolksWagen",
            "Gol Trendline 1.0 T.Flex 8V 5p", 2016, "Flex",
        )


def test_catalogo_mensal_busca_uma_vez_e_depois_le_so_do_banco(banco):
    fonte = FonteContada()
    catalogo = CatalogoFipe(banco, fonte)
    for _ in range(2):
        assert catalogo.referencia_atual().codigo == "338"
        assert catalogo.marcas("338")[0].codigo == "59"
        assert catalogo.modelos("338", "59")[0].codigo == "6786"
        assert catalogo.anos("338", "59", "6786")[0].codigo == "2016-5"
        assert catalogo.preco("338", "59", "6786", "2016-5").codigo_fipe == "005384-8"
    assert fonte.chamadas == [
        "referencias", "marcas 338", "modelos 338 59", "anos 338 59 6786", "preco 338 59 6786 2016-5",
    ]


def test_orcamento_diario_para_exatamente_no_limite(banco):
    assert banco.fipe_reservar_requisicao(2)
    assert banco.fipe_reservar_requisicao(2)
    assert not banco.fipe_reservar_requisicao(2)
    assert banco.fipe_requisicoes_hoje() == 2
