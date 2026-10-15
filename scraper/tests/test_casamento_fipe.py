import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from casamento_fipe import CasadorFipe, CasamentoFipe, _ranquear_modelos, bloqueio_do_anuncio, normalizar  # noqa: E402
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


class CatalogoCasosReais:
    referencia = ReferenciaFonte("338", "outubro/2026")
    marcas_fipe = [
        OpcaoFonte("23", "GM - Chevrolet"),
        OpcaoFonte("21", "Fiat"),
        OpcaoFonte("22", "Ford"),
        OpcaoFonte("59", "VW - VolksWagen"),
        OpcaoFonte("56", "Toyota"),
    ]
    modelos_fipe = {
        "23": [
            OpcaoFonte("onix", "ONIX HATCH LT 1.4 8V FlexPower 5p Mec."),
            OpcaoFonte("onix-plus", "ONIX PLUS PREM. 1.0 12V TB Flex Aut."),
        ],
        "21": [
            OpcaoFonte("toro-freedom", "Toro Freedom 1.3 T270 4x2 Flex Aut."),
            OpcaoFonte("toro-endurance", "Toro Endurance 1.3 T270 4x2 Flex Aut."),
            OpcaoFonte("toro-volcano", "Toro Volcano 1.3 T270 4x2 Flex Aut."),
        ],
        "22": [
            OpcaoFonte("ranger-black", "Ranger Black 2.2 4x2 CD Diesel Aut."),
            OpcaoFonte("ranger-xls", "Ranger XLS 2.2 4x2 CD Diesel Aut."),
        ],
        "59": [
            OpcaoFonte("tcross-highline", "T-Cross Hig. 250 TSI 1.4 Flex 16V 5p Aut"),
            OpcaoFonte("tcross-extreme", "T-Cross Ext. 250 TSI 1.4 Flex 16V 5p Aut"),
        ],
        "56": [OpcaoFonte("hilux-srv", "Hilux CD SRV D4-D 4x4 3.0 TDI Diesel")],
    }

    def referencia_atual(self):
        return self.referencia

    def marcas(self, _referencia):
        return self.marcas_fipe

    def modelos(self, _referencia, marca):
        return self.modelos_fipe.get(marca, [])

    def anos(self, _referencia, _marca, modelo):
        dados = {
            "onix": (2014, "Flex"),
            "toro-freedom": (2024, "Flex"),
            "toro-endurance": (2024, "Flex"),
            "toro-volcano": (2024, "Flex"),
            "ranger-black": (2023, "Diesel"),
            "ranger-xls": (2023, "Diesel"),
            "tcross-highline": (2025, "Flex"),
            "tcross-extreme": (2025, "Flex"),
            "hilux-srv": (2013, "Diesel"),
        }
        if modelo not in dados:
            return []
        ano, combustivel = dados[modelo]
        return [AnoFonte(f"{ano}-1", f"{ano} {combustivel}", ano, "1", combustivel)]


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


def carro_real(id_, marca, titulo, ano, combustivel, cambio, portas=4):
    modelo = titulo.removeprefix(f"{marca} ").rsplit(" ", 1)[0]
    return Anuncio(
        source="olx", external_id=id_, url="https://exemplo", titulo=titulo, marca=marca,
        modelo=modelo, modelo_original=modelo,
        ano=ano, km=60000, preco=80000, cambio=cambio, combustivel=combustivel, portas=portas,
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


def test_resultado_reaproveitado_preserva_bloqueio_e_preco_de_cada_anuncio(banco):
    casador = CasadorFipe(CatalogoFixture(), banco, ano_atual=2026)
    base = CasamentoFipe("338", "005384-8", 40000, "outubro de 2026", "alta", "Casamento exato")
    bloqueado = carro("bloqueado", "Gol Trendline 1.0", 2020, "1.0", 4)
    bloqueado.km = 100
    estranho = carro("estranho", "Gol Trendline 1.0", 2020, "1.0", 4)
    estranho.preco = 15000
    resultado_bloqueado = casador.reaproveitar(bloqueado, base)
    resultado_estranho = casador.reaproveitar(estranho, base)
    assert resultado_bloqueado.confianca == "sem_candidato"
    assert resultado_bloqueado.bloqueio == "km_incoerente"
    assert resultado_estranho.confianca == "alta"
    assert resultado_estranho.preco_estranho is True


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


@pytest.mark.parametrize(("titulo", "bloqueio"), [
    ("Veículo em preparação", "anuncio_promocional"),
    ("Gol 1.0 por apenas entrada", "anuncio_promocional"),
])
def test_propaganda_e_marcada_sem_consultar_catalogo(banco, titulo, bloqueio):
    anuncio = carro("propaganda", titulo, 2016, "1.0", 4)
    resultado = CasadorFipe(CatalogoFixture(), banco, ano_atual=2026).casar(anuncio)
    assert resultado.bloqueio == bloqueio
    assert resultado.codigo_fipe is None


def test_km_incoerente_com_ano_e_marcado_sem_esconder_o_anuncio(banco):
    anuncio = carro("km", "Gol Trendline 1.0", 2016, "1.0", 4)
    anuncio.km = 500
    assert bloqueio_do_anuncio(anuncio, 2026) == "km_incoerente"
    resultado = CasadorFipe(CatalogoFixture(), banco, ano_atual=2026).casar(anuncio)
    assert resultado.bloqueio == "km_incoerente"
    assert resultado.codigo_fipe is None


def test_preco_abaixo_de_metade_da_fipe_fica_marcado(banco):
    anuncio = carro("barato", "Gol Geração VI Trendline 1.0 8V Total Flex Mec. 4P", 2016, "1.0", 4)
    anuncio.preco = 10000
    resultado = CasadorFipe(CatalogoFixture(), banco, ano_atual=2026).casar(anuncio)
    assert resultado.confianca == "alta"
    assert resultado.codigo_fipe == "005384-8"
    assert resultado.preco_estranho is True


@pytest.mark.parametrize(("anuncio", "modelo_codigo"), [
    (
        carro_real("onix", "Chevrolet", "Chevrolet Onix Hatch LT 1.4 8V Flex Power Mec. 4P 2014", 2014, "Flex", "Manual"),
        "onix",
    ),
    (
        carro_real("toro", "Fiat", "Fiat Toro Freedom 1.3 T270 4X2 Flex AUT 2024", 2024, "Flex", "Automático"),
        "toro-freedom",
    ),
    (
        carro_real("ranger", "Ford", "Ford Ranger Black 2.2 4X2 CD Diesel AUT 2023", 2023, "Diesel", "Automático"),
        "ranger-black",
    ),
    (
        carro_real("tcross", "Volkswagen", "Volkswagen T-Cross Highline 1.4 TSI Flex 16V 5P AUT 2025", 2025, "Flex", "Automático"),
        "tcross-highline",
    ),
])
def test_falhas_reais_passam_a_escolher_a_versao_certa(banco, anuncio, modelo_codigo):
    escolha = CasadorFipe(CatalogoCasosReais(), banco).escolher(anuncio)
    assert escolha is not None
    assert escolha.modelo.codigo == modelo_codigo
    assert escolha.confianca == "alta"


def test_cambio_estruturado_conflitante_impede_confianca_alta(banco):
    anuncio = carro_real(
        "hilux", "Toyota", "Toyota Hilux CD SRV D4-d 4X4 3.0 TDI Diesel AUT 2013",
        2013, "Diesel", "Manual",
    )
    assert CasadorFipe(CatalogoCasosReais(), banco).escolher(anuncio) is None


CASOS_POPULARES = [
    ("Chevrolet Onix Hatch LT 1.4 8V Flex Power Mec. 4P", "ONIX HATCH LT 1.4 8V FlexPower 5p Mec.", "ONIX PLUS LT 1.0 12V Flex 4p Mec."),
    ("Chevrolet Onix Plus Premier 1.0 Turbo Flex AUT", "ONIX PLUS PREM. 1.0 12V TB Flex Aut.", "ONIX HATCH PREM. 1.0 12V TB Flex Aut."),
    ("Fiat Toro Freedom 1.3 T270 4X2 Flex AUT", "Toro Freedom 1.3 T270 4x2 Flex Aut.", "Toro Endurance 1.3 T270 4x2 Flex Aut."),
    ("Fiat Argo Drive 1.0 Flex 6V Mec.", "ARGO DRIVE 1.0 6V Flex", "ARGO TREKKING 1.3 8V Flex"),
    ("Fiat Mobi Like 1.0 Flex Mec.", "MOBI LIKE 1.0 Fire Flex 5p.", "MOBI TREKKING 1.0 Flex 5p."),
    ("Fiat Strada Freedom 1.3 Flex 8V CD", "Strada Freedom 1.3 Flex 8V CD", "Strada Volcano 1.3 Flex 8V CD"),
    ("Volkswagen T-Cross Highline 1.4 TSI Flex AUT", "T-Cross Hig. 250 TSI 1.4 Flex 16V 5p Aut", "T-Cross Ext. 250 TSI 1.4 Flex 16V 5p Aut"),
    ("Volkswagen Polo Highline TSI 1.0 Flex AUT", "Polo Highline TSI 1.0 Flex 12V Aut.", "Polo Comfort. TSI 1.0 Flex 12V Aut."),
    ("Volkswagen Gol Trendline 1.0 Total Flex Mec.", "Gol Trendline 1.0 T.Flex 8V 5p", "Gol Comfortline 1.6 T.Flex 8V 5p"),
    ("Volkswagen Nivus Comfortline 1.0 TSI Flex AUT", "Nivus Comfortline 1.0 200 TSI Flex Aut.", "Nivus Highline 1.0 200 TSI Flex Aut."),
    ("Ford Ranger Black 2.2 4X2 CD Diesel AUT", "Ranger Black 2.2 4x2 CD Diesel Aut.", "Ranger XLS 2.2 4x2 CD Diesel Aut."),
    ("Toyota Corolla XEi 2.0 Flex AUT", "Corolla XEi 2.0 Flex 16V Aut.", "Corolla Altis Prem. 2.0 Flex 16V Aut"),
    ("Toyota Hilux CD SRV 2.8 4X4 Diesel AUT", "Hilux CD SRV 4x4 2.8 TDI Diesel Aut.", "Hilux CD SRX 4x4 2.8 TDI Diesel Aut."),
    ("Toyota Yaris XL 1.5 Flex AUT", "YARIS XL 1.5 Flex 16V 5p Aut.", "YARIS XS 1.5 Flex 16V 5p Aut."),
    ("Honda Civic EXL 2.0 Flex AUT", "Civic Sedan EXL 2.0 Flex 16V Aut.4p", "Civic Sedan EX 2.0 Flex 16V Aut.4p"),
    ("Honda City EX 1.5 Flex AUT", "CITY Sedan EX 1.5 Flex 16V 4p Aut.", "CITY Sedan EXL 1.5 Flex 16V 4p Aut."),
    ("Honda HR-V EX 1.8 Flex AUT", "HR-V EX 1.8 Flexone 16V 5p Aut.", "HR-V EXL 1.8 Flexone 16V 5p Aut."),
    ("Hyundai HB20 Comfort 1.0 Flex Mec.", "HB20 Comfort 1.0 Flex 12V Mec.", "HB20 Platinum 1.0 TB Flex 12V Aut."),
    ("Hyundai Creta Platinum 1.0 Turbo Flex AUT", "Creta Platinum 1.0 TB 12V Flex Aut.", "Creta Limited 1.0 TB 12V Flex Aut."),
    ("Jeep Renegade Longitude 1.8 Flex AUT", "Renegade Longitude 1.8 4x2 Flex 16V Aut.", "Renegade Sport 1.8 4x2 Flex 16V Aut."),
    ("Jeep Compass Limited 2.0 Flex AUT", "COMPASS LIMITED 2.0 4x2 Flex 16V Aut.", "COMPASS LONGITUDE 2.0 4x2 Flex 16V Aut."),
    ("Nissan Kicks Exclusive 1.6 Flex AUT", "KICKS Exclusive 1.6 16V Flex Aut.", "KICKS Advance 1.6 16V Flex Aut."),
    ("Nissan Versa Advance 1.6 Flex AUT", "VERSA Advance 1.6 16V Flex Aut.", "VERSA Exclusive 1.6 16V Flex Aut."),
    ("Renault Kwid Zen 1.0 Flex Mec.", "KWID Zen 1.0 Flex 12V 5p Mec.", "KWID Intense 1.0 Flex 12V 5p Mec."),
    ("Renault Sandero Stepway 1.6 Flex Mec.", "SANDERO STEPWAY 1.6 Flex 8V 5p", "SANDERO Expression 1.6 Flex 8V 5p"),
    ("Renault Duster Iconic 1.3 Turbo Flex AUT", "DUSTER Iconic 1.3 TB 16V Flex Aut.", "DUSTER Intense 1.6 16V Flex Aut."),
    ("Chevrolet Tracker Premier 1.2 Turbo Flex AUT", "TRACKER Premier 1.2 Turbo 12V Flex Aut.", "TRACKER LTZ 1.0 Turbo 12V Flex Aut."),
    ("Peugeot 208 Allure 1.6 Flex AUT", "208 Allure 1.6 Flex 16V 5p Aut.", "208 Griffe 1.6 Flex 16V 5p Aut."),
    ("Citroen C4 Cactus Feel 1.6 Flex AUT", "C4 CACTUS FEEL 1.6 16V Flex Aut.", "C4 CACTUS SHINE 1.6 Turbo Flex Aut."),
    ("Volkswagen Saveiro Robust 1.6 Flex Mec.", "Saveiro Robust 1.6 Total Flex 8V", "Saveiro Cross 1.6 T.Flex 16V CD"),
]


@pytest.mark.parametrize(("titulo", "esperado", "alternativa"), CASOS_POPULARES)
def test_ranking_generico_com_trinta_carros_populares(titulo, esperado, alternativa):
    modelo = titulo.split(" ", 1)[1]
    anuncio = Anuncio(
        source="olx", external_id="popular", url="https://exemplo", titulo=titulo,
        marca="Marca", modelo=modelo, modelo_original=modelo, ano=2020, km=50000,
        preco=60000, cambio=None, combustivel="flex", portas=None,
    )
    ranqueados = _ranquear_modelos(
        anuncio,
        [OpcaoFonte("esperado", esperado), OpcaoFonte("alternativa", alternativa)],
    )
    assert ranqueados
    assert ranqueados[0][1].codigo == "esperado", (
        titulo, normalizar(esperado), normalizar(alternativa), ranqueados,
    )
