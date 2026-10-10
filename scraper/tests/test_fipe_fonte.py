import json
import sys
from pathlib import Path

import httpx
import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from sources.fipe import FipeOnline, FonteFipeIndisponivel, LimiteFipeAtingido  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "fipe"


def fixture(nome):
    return json.loads((FIXTURES / nome).read_text())


def cliente_com_fixtures():
    rotas = {
        "/api/v2/references": fixture("referencias.json"),
        "/api/v2/cars/brands": fixture("marcas.json"),
        "/api/v2/cars/brands/59/models": fixture("modelos_volkswagen.json"),
        "/api/v2/cars/brands/59/models/6786/years": fixture("anos_gol_trendline_1_0.json"),
        "/api/v2/cars/brands/59/models/6786/years/2016-5": fixture("preco_gol_trendline_1_0_2016.json"),
    }

    def responder(request):
        assert request.url.params.get("reference") in (None, "338")
        return httpx.Response(200, json=rotas[request.url.path])

    return httpx.Client(
        base_url="https://fipe.parallelum.com.br/api/v2",
        transport=httpx.MockTransport(responder),
    )


def test_contrato_real_de_referencias_catalogo_ano_combustivel_e_preco():
    fonte = FipeOnline(cliente=cliente_com_fixtures(), reservar=lambda: True, pausa=0)
    referencia = fonte.referencias()[0]
    assert (referencia.codigo, referencia.mes) == ("338", "outubro/2026")
    volkswagen = next(x for x in fonte.marcas("338") if x.nome == "VW - VolksWagen")
    assert volkswagen.codigo == "59"
    trendline = next(x for x in fonte.modelos("338", "59") if x.codigo == "6786")
    assert trendline.nome == "Gol Trendline 1.0 T.Flex 8V 5p"
    ano = fonte.anos("338", "59", "6786")[0]
    assert (ano.codigo, ano.ano_modelo, ano.combustivel_codigo, ano.combustivel) == ("2016-5", 2016, "5", "Flex")
    preco = fonte.preco("338", "59", "6786", "2016-5")
    assert str(preco.preco) == "39351.00"
    assert preco.codigo_fipe == "005384-8"
    assert preco.mes_referencia == "outubro de 2026"


def test_429_espera_e_repete_poucas_vezes():
    chamadas = 0
    esperas = []

    def responder(_request):
        nonlocal chamadas
        chamadas += 1
        if chamadas == 1:
            return httpx.Response(429)
        return httpx.Response(200, json=fixture("referencias.json"))

    fonte = FipeOnline(
        cliente=httpx.Client(base_url=FipeOnline.BASE_URL, transport=httpx.MockTransport(responder)),
        reservar=lambda: True, pausa=0, repeticoes=1, backoff=0.5, dormir=esperas.append,
    )
    assert fonte.referencias()[0].codigo == "338"
    assert chamadas == 2
    assert esperas == [0.5]


def test_erro_de_rede_repete_e_depois_falha():
    chamadas = 0

    def responder(request):
        nonlocal chamadas
        chamadas += 1
        raise httpx.ConnectError("sem rede", request=request)

    fonte = FipeOnline(
        cliente=httpx.Client(base_url=FipeOnline.BASE_URL, transport=httpx.MockTransport(responder)),
        reservar=lambda: True, pausa=0, repeticoes=1, backoff=0, dormir=lambda _s: None,
    )
    with pytest.raises(FonteFipeIndisponivel):
        fonte.referencias()
    assert chamadas == 2


def test_orcamento_e_reservado_antes_de_tocar_na_fonte():
    chamadas = 0

    def responder(_request):
        nonlocal chamadas
        chamadas += 1
        return httpx.Response(200, json=[])

    fonte = FipeOnline(
        cliente=httpx.Client(base_url=FipeOnline.BASE_URL, transport=httpx.MockTransport(responder)),
        reservar=lambda: False, pausa=0,
    )
    with pytest.raises(LimiteFipeAtingido):
        fonte.referencias()
    assert chamadas == 0
