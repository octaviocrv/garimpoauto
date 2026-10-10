"""Região e cidade pela API: o que a OLX já devolve filtrado, o total e a frase certos. Offline."""

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import server  # noqa: E402
from config import LimitesBusca  # noqa: E402
from sources import olx  # noqa: E402
from tests.test_contrato_olx import pagina_real  # noqa: E402
from tests.test_olx import Relogio, SessaoFalsa  # noqa: E402

BH = "belo-horizonte-e-regiao"


class FonteOlxFalsa:
    """A fonte OLX de verdade (cursor, filtros, URL), mas com a rede trocada por páginas salvas."""

    FONTE = "olx"

    def __init__(self, paginas):
        self.sessao = SessaoFalsa(paginas)
        self.relogio = Relogio()
        self.abertas = 0

    def abrir(self, busca, limites=None, *, teto=None):
        self.abertas += 1
        return olx.abrir(busca, limites, teto=teto, sessao=self.sessao, dormir=self.relogio.dormir, relogio=self.relogio)

    def buscar_paginas(self, busca, limites=None):
        raise AssertionError("o servidor usa abrir")

    buscar = buscar_paginas


def cliente(paginas):
    fonte = FonteOlxFalsa(paginas)
    app = server.criar_app(fonte, ttl=60.0, estado_padrao="mg", limites=LimitesBusca())
    return TestClient(app), fonte


def pagina(c, **params):
    return c.get("/buscar/pagina", params={"texto": "civic", "pagina": 1, **params})


def test_cidade_que_a_olx_conhece_ja_vem_filtrada_e_o_total_e_o_dela():
    c, fonte = cliente([pagina_real("olx_contagem")])
    j = pagina(c, estado="MG", cidade="Contagem").json()
    assert fonte.sessao.urls_de_listagem[0].endswith(f"/estado-mg/{BH}/grande-belo-horizonte/contagem?q=civic&sf=1")
    assert j["total_na_fonte"] == 146 and len(j["anuncios"]) == 50
    assert {a["cidade"] for a in j["anuncios"]} == {"Contagem"}
    assert "cidade" in j["filtros_na_origem"] and "cidade" not in j["filtros_locais"]
    assert j["cortados_por_filtro"] == {} and j["avisos"] == []
    assert j["informacao"] == "Mostrando 50 de 146 carros. Toca em Ver mais pra ver o resto."


def test_o_total_nao_e_o_do_estado_inteiro():
    c, _ = cliente([pagina_real("olx_contagem")])
    assert pagina(c, estado="MG", cidade="Contagem").json()["total_na_fonte"] == 146  # o do estado é mais de mil


def test_regiao_escolhida_vai_na_url_e_conta_como_filtro_da_origem():
    c, fonte = cliente([pagina_real("olx_civic_p1")])
    j = pagina(c, estado="MG", regiao=BH).json()
    assert fonte.sessao.urls_de_listagem[0].endswith(f"/estado-mg/{BH}?q=civic&sf=1")
    assert "regiao" in j["filtros_na_origem"] and j["busca"]["regiao"] == BH


def test_regiao_escrita_de_outro_jeito_vira_o_mesmo_pedido_e_o_mesmo_cache():
    c, fonte = cliente([pagina_real("olx_civic_p1")])
    pagina(c, estado="MG", regiao="Belo Horizonte e região")
    j = pagina(c, estado="MG", regiao=BH).json()
    assert fonte.abertas == 1 and j["do_cache"] is True


def test_regiao_que_nao_existe_da_erro_curto_e_nao_busca_no_brasil_todo():
    c, fonte = cliente([])
    r = pagina(c, estado="MG", regiao="regiao-de-marte")
    assert r.status_code == 422 and r.json() == {"erro": server.MSG_REGIAO}
    assert fonte.abertas == 0 and fonte.sessao.urls == []


def test_regiao_de_outro_estado_tambem_e_recusada():
    c, _ = cliente([])
    assert pagina(c, estado="SP", regiao=BH).status_code == 422


def test_regiao_com_brasil_todo_e_pedido_ruim():
    c, _ = cliente([])
    assert pagina(c, estado="todos", regiao=BH).json() == {"erro": server.MSG_PEDIDO}


def test_cidade_sem_pagina_na_olx_filtra_aqui_e_avisa_sem_esconder():
    c, fonte = cliente([pagina_real("olx_civic_p1")])
    j = pagina(c, estado="MG", cidade="Belo Horizonte").json()
    assert fonte.sessao.urls_de_listagem[0].endswith("/estado-mg?q=civic&sf=1")
    assert "cidade" in j["filtros_locais"] and "cidade" not in j["filtros_na_origem"]
    aviso = next(a for a in j["avisos"] if a["codigo"] == "filtro_aproximado")
    assert "a cidade Belo Horizonte" in aviso["mensagem"] and "Pode ter ficado" in aviso["mensagem"]
    assert {a["cidade"] for a in j["anuncios"]} <= {"Belo Horizonte"}


def test_cidade_com_regiao_no_mesmo_pedido_nao_gasta_leitura_a_mais():
    c, fonte = cliente([pagina_real("olx_contagem")])
    pagina(c, estado="MG", regiao=BH, cidade="Contagem")
    assert len(fonte.sessao.urls_de_listagem) == 1 and not any("/api/filters/" in u for u in fonte.sessao.urls)


def test_lista_de_regioes_para_o_seletor():
    c, _ = cliente([])
    j = c.get("/regioes", params={"estado": "MG"}).json()
    assert j["estado"] == "MG" and len(j["regioes"]) == 7
    assert {"slug": BH, "nome": j["regioes"][0]["nome"]} in j["regioes"]
    padrao = c.get("/regioes").json()
    assert padrao["estado"] == "MG"  # sem estado, usa o padrão do servidor
    assert c.get("/regioes", params={"estado": "xx"}).status_code == 422


def test_todo_estado_tem_a_lista_de_regioes():
    c, _ = cliente([])
    for uf in ("AC", "SP", "RJ", "DF", "BA", "PR"):
        j = c.get("/regioes", params={"estado": uf}).json()
        assert j["regioes"], uf
