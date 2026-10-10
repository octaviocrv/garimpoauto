"""Busca sem texto, a vitrine da tela: o estado todo, mais recentes, página 1. Usa a página real
salva em tests/fixtures/olx_vitrine_mg.json (50 carros de MG, total 73.619), sem internet."""

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from busca import chave_busca  # noqa: E402
from schemas import Busca  # noqa: E402
from sources import olx  # noqa: E402
from tests.test_contrato_olx import buscar, pagina_real  # noqa: E402
from tests.test_local_servidor import cliente  # noqa: E402


def vitrine(c, **params):
    return c.get("/buscar/pagina", params={"pagina": 1, "estado": "MG", **params})


def test_texto_vazio_vale_mas_o_campo_continua_obrigatorio():
    assert Busca(texto="").texto == "" and Busca(texto="   ").texto == ""
    with pytest.raises(ValidationError):
        Busca()


def test_url_sem_texto_pede_a_categoria_do_estado_sem_q():
    url = olx.montar_url(Busca(texto="", estado="MG"))
    assert url == f"{olx.URL_BASE}/estado-mg?sf=1"
    assert "q=" not in url


def test_url_sem_texto_mantem_os_filtros_e_com_texto_nada_muda():
    url = olx.montar_url(Busca(texto="", estado="MG", ano_min=2018, preco_max=50000))
    assert "q=" not in url and "rs=2018" in url and "pe=50000" in url
    assert olx.montar_url(Busca(texto="gol", estado="MG")) == f"{olx.URL_BASE}/estado-mg?q=gol&sf=1"


def test_a_chave_de_cache_da_vitrine_e_propria_e_estavel():
    vazia = Busca(texto="", estado="MG")
    assert chave_busca(vazia) == "texto=|estado=mg|ordenar=recentes"
    assert chave_busca(vazia) == chave_busca(Busca(texto="   ", estado="mg"))
    assert chave_busca(vazia) != chave_busca(Busca(texto="gol", estado="MG"))
    assert chave_busca(vazia) != chave_busca(Busca(texto="", estado="SP"))
    assert chave_busca(vazia) != chave_busca(Busca(texto="", estado="MG", ano_min=2018))


def test_pagina_real_sem_texto_traz_50_carros_de_mg_e_o_total():
    r, sessao = buscar([pagina_real("olx_vitrine_mg")], Busca(texto="", estado="MG"), max_paginas=1)
    assert r.funil.total_na_fonte == 73619 and len(r.anuncios) == 50
    assert {a.estado for a in r.anuncios} == {"MG"}
    assert sessao.urls[0].endswith("/estado-mg?sf=1")


def test_endpoint_aceita_texto_vazio_e_mostra_o_total():
    c, fonte = cliente([pagina_real("olx_vitrine_mg")])
    j = vitrine(c, texto="").json()
    assert len(j["anuncios"]) == 50 and j["total_na_fonte"] == 73619
    assert j["tem_mais"] is True and j["proxima_pagina"] == 2
    assert j["informacao"] == "Mostrando 50 de 73.619 carros. Toca em Ver mais pra ver o resto."
    assert fonte.sessao.urls_de_listagem[0].endswith("/estado-mg?sf=1")
    assert vitrine(c).status_code == 422  # esquecer o parâmetro continua sendo pedido ruim


def test_nos_tres_endpoints_texto_vazio_nao_e_pedido_ruim():
    c, _ = cliente([pagina_real("olx_vitrine_mg")] * 3)
    assert c.get("/buscar", params={"texto": "", "estado": "MG"}).status_code == 200
    assert c.get("/buscar/stream", params={"texto": "", "estado": "MG"}).status_code == 200
    assert vitrine(c, texto="").status_code == 200


def test_vitrine_repetida_vem_do_cache_e_nao_baixa_de_novo():
    c, fonte = cliente([pagina_real("olx_vitrine_mg")])
    a = vitrine(c, texto="").json()
    b = vitrine(c, texto="").json()
    assert (a["do_cache"], b["do_cache"]) == (False, True)
    assert len(fonte.sessao.urls_de_listagem) == 1


def test_busca_com_texto_nao_se_mistura_com_a_vitrine():
    c, fonte = cliente([pagina_real("olx_vitrine_mg"), pagina_real("olx_civic_p1")])
    vitrine(c, texto="")
    j = vitrine(c, texto="civic").json()
    assert j["total_na_fonte"] == 78 and j["do_cache"] is False
    assert fonte.sessao.urls_de_listagem[1].endswith("/estado-mg?q=civic&sf=1")


def test_filtro_sem_texto_busca_com_o_filtro_e_nao_vira_vitrine():
    c, fonte = cliente([pagina_real("olx_vitrine_mg")])
    vitrine(c, texto="", ano_min=2018)
    assert "rs=2018" in fonte.sessao.urls_de_listagem[0]
