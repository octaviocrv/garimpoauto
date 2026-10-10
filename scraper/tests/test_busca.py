"""Busca genérica (qualquer carro): montagem de URL, filtro local e chave de busca. Offline.

Rodar dentro de scraper/:  .venv/bin/python -m pytest tests -v
"""

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from busca import chave_busca, filtrar_local, normalizar_texto  # noqa: E402
from schemas import Anuncio, Busca  # noqa: E402
from sources import olx  # noqa: E402
from tests.test_olx import Relogio, RespostaFalsa, SessaoFalsa, anuncio_cru, html_com_ads  # noqa: E402


def carro(list_id, marca, modelo, ano, km, cidade, uf="SP", preco="R$ 50.000", **extra):
    props = [
        {"name": "vehicle_brand", "value": marca},
        {"name": "vehicle_model", "value": modelo},
        {"name": "regdate", "value": str(ano)},
        {"name": "mileage", "value": str(km)},
    ]
    return anuncio_cru(
        list_id,
        subject=f"{marca} {modelo} {ano}",
        priceValue=preco,
        properties=props,
        location=f"{cidade}, Centro",
        locationDetails={"municipality": cidade, "neighbourhood": "Centro", "uf": uf},
        **extra,
    )


# Anúncios de exemplo de três carros que não são o Civic.
GOL = carro(101, "VW - VolksWagen", "Gol 1.0 City Total Flex", 2012, 98000, "São Paulo")
GOL_RJ = carro(102, "VW - VolksWagen", "Gol G5 1.6", 2012, 142000, "Niterói", uf="RJ")
ONIX = carro(103, "GM - Chevrolet", "Onix LT 1.0", 2019, 45000, "Campinas")
HILUX = carro(104, "Toyota", "Hilux CD SRV 4x4 Diesel", 2016, 160000, "Goiânia", uf="GO", preco="R$ 189.900")
UP = carro(105, "VW - VolksWagen", "Up! Move 1.0", 2017, 60000, "São Paulo")
TODOS = [olx.normalizar(a) for a in (GOL, GOL_RJ, ONIX, HILUX, UP)]


def ids(anuncios):
    return [a.external_id for a in anuncios]


# --- modelo de busca ---------------------------------------------------------


def test_so_o_texto_e_obrigatorio():
    b = Busca(texto="  onix  ")
    assert b.texto == "onix"
    assert all(getattr(b, c) is None for c in ("marca", "modelo", "estado", "regiao", "cidade", "km_max"))
    with pytest.raises(ValidationError):
        Busca()
    with pytest.raises(ValidationError):
        Busca(texto="   ")


def test_estado_vazio_vira_none_e_sigla_vai_para_maiuscula():
    assert Busca(texto="gol", estado="").estado is None
    assert Busca(texto="gol", estado="sp").estado == "SP"
    with pytest.raises(ValidationError):
        Busca(texto="gol", estado="minas")


def test_faixas_e_regiao_invalidas():
    with pytest.raises(ValidationError):
        Busca(texto="gol", ano_min=2020, ano_max=2010)
    with pytest.raises(ValidationError):
        Busca(texto="gol", preco_min=90000, preco_max=1000)
    with pytest.raises(ValidationError):
        Busca(texto="gol", regiao="campinas-e-regiao")  # região sem estado


# --- URL ---------------------------------------------------------------------


def test_url_gol_2012_com_estado():
    url = olx.montar_url(Busca(texto="gol 2012", estado="sp", ano_min=2012, ano_max=2012, preco_max=40000))
    assert url.startswith(f"{olx.URL_BASE}/estado-sp?")
    for pedaco in ("q=gol%202012", "rs=2012", "re=2012", "pe=40000"):
        assert pedaco in url


def test_url_sem_estado_e_brasil_todo():
    url = olx.montar_url(Busca(texto="hilux diesel"))
    assert url == f"{olx.URL_BASE}?q=hilux%20diesel&sf=1"
    assert "estado-" not in url


def test_url_com_regiao_e_so_o_que_a_olx_nao_aceita_fica_de_fora():
    b = Busca(texto="onix", estado="MG", regiao="belo-horizonte-e-regiao", marca="Chevrolet", modelo="Onix", cidade="Belo Horizonte")
    url = olx.montar_url(b)
    assert url == f"{olx.URL_BASE}/estado-mg/belo-horizonte-e-regiao?q=onix&sf=1"  # marca e modelo só entram com os códigos, a cidade da capital não tem página


def test_url_com_cidade_que_a_olx_tem_vai_ate_a_cidade():
    b = Busca(texto="onix", estado="MG", regiao="belo-horizonte-e-regiao", cidade="Contagem")
    assert olx.montar_url(b) == f"{olx.URL_BASE}/estado-mg/belo-horizonte-e-regiao/grande-belo-horizonte/contagem?q=onix&sf=1"


@pytest.mark.parametrize("pedido, degrau", [(60000, "60000"), (55000, "60000"), (1, "5000"), (0, "0"), (99000, "100000"), (450000, "500000"), (160001, "180000")])
def test_km_vai_para_o_degrau_que_cobre_o_pedido(pedido, degrau):
    url = olx.montar_url(Busca(texto="onix", km_max=pedido))
    assert f"me={degrau}" in url


def test_km_acima_do_ultimo_degrau_nao_vai_na_url():
    assert "me=" not in olx.montar_url(Busca(texto="hilux", km_max=900000))


# --- filtro local ------------------------------------------------------------


def test_filtro_de_marca_ignora_caixa_e_acento_e_acha_vw():
    assert ids(filtrar_local(TODOS, Busca(texto="x", marca="volkswagen"))) == ["101", "102", "105"]
    assert ids(filtrar_local(TODOS, Busca(texto="x", marca="CHEVROLET"))) == ["103"]
    assert ids(filtrar_local(TODOS, Busca(texto="x", marca="toyóta"))) == ["104"]


def test_filtro_de_modelo_e_por_palavra_inteira():
    assert ids(filtrar_local(TODOS, Busca(texto="x", modelo="gol"))) == ["101", "102"]
    assert ids(filtrar_local(TODOS, Busca(texto="x", modelo="HILUX"))) == ["104"]
    assert ids(filtrar_local(TODOS, Busca(texto="x", modelo="up"))) == ["105"]
    assert filtrar_local(TODOS, Busca(texto="x", modelo="uno")) == []


def test_filtro_de_cidade_sem_acento_e_sem_caixa():
    assert ids(filtrar_local(TODOS, Busca(texto="x", cidade="sao paulo"))) == ["101", "105"]
    assert ids(filtrar_local(TODOS, Busca(texto="x", cidade="GOIANIA"))) == ["104"]
    assert ids(filtrar_local(TODOS, Busca(texto="x", cidade="niteroi"))) == ["102"]


def test_km_exato_depois_do_arredondamento_da_olx():
    # km_max=95000 vai para a OLX como 100000; o corte exato é local.
    b = Busca(texto="gol", km_max=95000)
    assert "me=100000" in olx.montar_url(b)
    assert ids(filtrar_local(TODOS, b)) == ["103", "105"]  # o gol de 98000 e os de 142000 e 160000 ficam fora
    assert ids(filtrar_local(TODOS, Busca(texto="gol", km_max=98000))) == ["101", "103", "105"]


def test_campo_vazio_nao_passa_por_filtro_que_o_usa_e_none_nao_e_inventado():
    sem_km = olx.normalizar(carro(110, "Fiat", "Uno Vivace", 2013, 0, "Recife", uf="PE"))
    sem_km.km = None
    assert filtrar_local([sem_km], Busca(texto="uno", km_max=100000)) == []
    assert filtrar_local([sem_km], Busca(texto="uno")) == [sem_km]  # sem filtro, passa


def test_ignorar_pula_filtros_que_a_fonte_ja_aplicou():
    b = Busca(texto="x", estado="SP", ano_min=2017)
    assert ids(filtrar_local(TODOS, b)) == ["103", "105"]  # estado SP e ano >= 2017
    assert len(filtrar_local(TODOS, b, ignorar=("estado", "ano_min"))) == len(TODOS)


def test_busca_sem_filtros_nao_remove_nada():
    assert filtrar_local(TODOS, Busca(texto="qualquer")) == TODOS


def test_modelo_original_guarda_o_texto_da_olx():
    a = olx.normalizar(HILUX)
    assert a.modelo_original == "Hilux CD SRV 4x4 Diesel"


# --- chave de busca ----------------------------------------------------------


def test_chave_ignora_caixa_acento_e_espacos():
    a = Busca(texto="  Hilux   DIESEL ", cidade="Goiânia", estado="go")
    b = Busca(texto="hilux diesel", cidade="goiania", estado="GO")
    assert chave_busca(a) == chave_busca(b)


def test_chave_tem_ordem_fixa_e_so_filtros_preenchidos():
    b = Busca(texto="Onix", km_max=50000, marca="Chevrolet", ano_min=2018)
    assert chave_busca(b) == "texto=onix|marca=chevrolet|ano_min=2018|km_max=50000|ordenar=recentes"


def test_chaves_diferentes_para_buscas_diferentes_e_estado_vazio_distinto():
    assert chave_busca(Busca(texto="gol")) != chave_busca(Busca(texto="gol", estado="sp"))
    assert chave_busca(Busca(texto="gol", ano_min=2010)) != chave_busca(Busca(texto="gol", ano_max=2010))
    assert normalizar_texto("Ação  À-vista") == "acao a-vista"


# --- busca completa com filtro local aplicado -------------------------------


def test_buscar_aplica_filtro_local_e_manda_so_o_que_a_olx_aceita():
    html = html_com_ads([GOL, GOL_RJ, UP], total=3)
    sessao, relogio = SessaoFalsa([RespostaFalsa(200, html)]), Relogio()
    busca = Busca(texto="gol", marca="volkswagen", modelo="gol", km_max=100000, cidade="são paulo")
    res = olx.buscar_tudo(busca, sessao=sessao, dormir=relogio.dormir, relogio=relogio)
    assert ids(res.anuncios) == ["101"]
    assert sessao.urls_de_listagem == [f"{olx.URL_BASE}?q=gol&me=100000&sf=1"]  # sem estado, sem marca/modelo/cidade (a OLX não entendeu os nomes)


# --- câmbio, combustível, anunciante, km mínimo e ordenação -------------------


def test_cambio_combustivel_e_anunciante_aceitam_acento_e_caixa():
    b = Busca(texto="civic", cambio=" Automático ", combustivel="FLEX", anunciante="Profissional")
    assert (b.cambio, b.combustivel, b.anunciante) == ("automatico", "flex", "profissional")
    url = olx.montar_url(b)
    for pedaco in ("gb=2", "fu=3", "f=1"):
        assert pedaco in url
    assert Busca(texto="x", cambio="semi automático").cambio == "semi-automatico"
    assert Busca(texto="x", cambio="  ").cambio is None


@pytest.mark.parametrize("campo,valor", [("cambio", "voador"), ("combustivel", "agua"), ("anunciante", "robo"), ("ordenar", "maior_preco")])
def test_opcao_invalida_e_recusada(campo, valor):
    with pytest.raises(ValueError):
        Busca(texto="x", **{campo: valor})


def test_ordenacao_padrao_e_mais_recentes_e_relevancia_nao_manda_nada():
    assert Busca(texto="x").ordenar == "recentes" and "sf=1" in olx.montar_url(Busca(texto="x"))
    assert "sp=1" in olx.montar_url(Busca(texto="x", ordenar="menor_preco"))
    url = olx.montar_url(Busca(texto="x", ordenar="relevancia"))
    assert "sf=" not in url and "sp=" not in url


@pytest.mark.parametrize("pedido, degrau", [(60000, "60000"), (55000, "40000"), (5000, "5000"), (4999, None), (500000, "500000")])
def test_km_minimo_vai_para_o_degrau_de_baixo(pedido, degrau):
    url = olx.montar_url(Busca(texto="onix", km_min=pedido))
    assert (f"ms={degrau}" in url) if degrau else ("ms=" not in url)


def test_km_minimo_e_maximo_exatos_sao_aplicados_depois_da_coleta():
    a = [Anuncio(source="olx", external_id=str(i), url="u", km=km) for i, km in enumerate((10000, 45000, 70000, None))]
    busca = Busca(texto="x", km_min=40000, km_max=60000)
    assert [x.km for x in filtrar_local(a, busca)] == [45000]


def test_km_minimo_maior_que_maximo_e_recusado():
    with pytest.raises(ValueError):
        Busca(texto="x", km_min=90000, km_max=10000)


def test_a_ordenacao_e_os_filtros_novos_entram_na_chave_do_cache():
    base = Busca(texto="gol")
    assert chave_busca(base) != chave_busca(Busca(texto="gol", ordenar="relevancia"))
    for extra in ({"cambio": "manual"}, {"combustivel": "flex"}, {"anunciante": "particular"}, {"km_min": 1000}, {"versao": "1.0"}):
        assert chave_busca(base) != chave_busca(Busca(texto="gol", **extra)), extra
    assert chave_busca(Busca(texto="gol", cambio="Automático")) == chave_busca(Busca(texto="gol", cambio="automatico"))
