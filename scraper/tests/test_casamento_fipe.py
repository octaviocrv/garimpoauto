import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from casamento_fipe import CasadorFipe  # noqa: E402
from schemas import Anuncio  # noqa: E402
from sources.fipe import AnoFonte, OpcaoFonte, PrecoFonte, ReferenciaFonte  # noqa: E402
from tests.apoio_banco import RelogioBanco, novo_armazem, zerar_banco_de_teste  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "fipe"


def ler(nome):
    return json.loads((FIXTURES / nome).read_text())


def opcoes(nome):
    return [OpcaoFonte(str(x["code"]), str(x["name"])) for x in ler(nome)]


def anos(nome):
    saida = []
    for x in ler(nome):
        ano, combustivel_codigo = str(x["code"]).rsplit("-", 1)
        saida.append(AnoFonte(str(x["code"]), str(x["name"]), int(ano), combustivel_codigo, str(x["name"]).split(" ", 1)[1]))
    return saida


class CatalogoFixture:
    referencia = ReferenciaFonte("338", "outubro/2026")
    por_modelo = {
        "6280": anos("anos_gol_novo_1_0_2p.json"),
        "6786": anos("anos_gol_trendline_1_0.json"),
        "6790": anos("anos_gol_comfortline_1_6.json"),
    }

    def referencia_atual(self):
        return self.referencia

    def marcas(self, _referencia):
        return opcoes("marcas.json")

    def modelos(self, _referencia, _marca):
        return opcoes("modelos_volkswagen.json")

    def anos(self, _referencia, _marca, modelo):
        return self.por_modelo.get(modelo, [])

    def preco(self, _referencia, _marca, _modelo, _ano):
        x = ler("preco_gol_trendline_1_0_2016.json")
        return PrecoFonte(
            x["codeFipe"], Decimal("39351.00"), x["referenceMonth"], x["brand"], x["model"],
            x["modelYear"], x["fuel"],
        )


@pytest.fixture
def banco():
    zerar_banco_de_teste()
    armazem = novo_armazem(RelogioBanco())
    armazem.migrar()
    yield armazem
    armazem.fechar()


def carro(id_, titulo, ano, motor, portas):
    return Anuncio(
        source="olx", external_id=id_, url="https://exemplo", titulo=titulo, marca="Volkswagen",
        modelo="Gol", modelo_original=f"Gol {motor}", ano=ano, km=60000, preco=35000,
        cambio="manual", combustivel="flex", portas=portas,
    )


@pytest.mark.parametrize(("anuncio", "modelo_codigo"), [
    (
        carro("a", "Gol Geração VI Trendline 1.0 8V Total Flex Mec. 4P", 2016, "1.0", 4),
        "6786",
    ),
    (
        carro("b", "Gol Geração V 1.0 8V MI Total Flex Mec. 2P", 2013, "1.0", 2),
        "6280",
    ),
    (
        carro("c", "Gol Geração VI Comfortline 1.6 8V Total Flex Mec. 4P", 2016, "1.6", 4),
        "6790",
    ),
])
def test_titulos_reais_escolhem_a_versao_certa_com_confianca_alta(banco, anuncio, modelo_codigo):
    escolha = CasadorFipe(CatalogoFixture(), banco).escolher(anuncio)
    assert escolha is not None
    assert escolha.modelo.codigo == modelo_codigo
    assert escolha.confianca == "alta"


def test_empate_nunca_vira_confianca_alta(banco):
    catalogo = CatalogoFixture()
    modelos = opcoes("modelos_volkswagen.json")
    original = catalogo.modelos
    catalogo.modelos = lambda ref, marca: [
        OpcaoFonte("x1", "Gol Trendline 1.0 T.Flex 8V 5p"),
        OpcaoFonte("x2", "Gol Trendline 1.0 T.Flex 8V 5p"),
    ]
    catalogo.por_modelo = {"x1": anos("anos_gol_trendline_1_0.json"), "x2": anos("anos_gol_trendline_1_0.json")}
    escolha = CasadorFipe(catalogo, banco).escolher(
        carro("d", "Gol Geração VI Trendline 1.0 8V Total Flex Mec. 4P", 2016, "1.0", 4),
    )
    assert escolha is not None and escolha.confianca != "alta"
    catalogo.modelos = original
    assert modelos


def test_dado_faltando_nao_casa_e_resultado_fica_guardado(banco):
    catalogo = CatalogoFixture()
    casador = CasadorFipe(catalogo, banco)
    anuncio = carro("e", "Gol", 2016, "1.0", 4)
    anuncio.combustivel = None
    primeiro = casador.casar(anuncio)
    segundo = casador.casar(anuncio)
    assert primeiro == segundo
    assert primeiro.confianca == "sem_candidato"
    assert primeiro.codigo_fipe is None
