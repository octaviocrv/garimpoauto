"""CursorOlx: a busca da OLX andando uma página por chamada (base do "Ver mais"). Offline."""

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from schemas import Busca  # noqa: E402
from sources import olx  # noqa: E402
from sources.base import Cursor  # noqa: E402
from tests.test_contrato_olx import pagina_real  # noqa: E402
from tests.test_filtros_origem import API  # noqa: E402
from tests.test_olx import Relogio, RespostaFalsa, SessaoFalsa, anuncio_cru, html_com_ads, limites  # noqa: E402


@pytest.fixture(autouse=True)
def _sem_cache_de_codigos():
    olx.limpar_cache_codigos()
    yield
    olx.limpar_cache_codigos()


def abrir(respostas, busca=None, api=None, teto=None, **kw):
    sessao, relogio = SessaoFalsa(respostas, api=api), Relogio()
    cursor = olx.abrir(
        busca or Busca(texto="civic 2018", estado="MG"), limites(**kw), teto=teto,
        sessao=sessao, dormir=relogio.dormir, relogio=relogio,
    )
    return cursor, sessao, relogio


def test_o_cursor_segue_a_interface_cursor():
    cursor, _, _ = abrir([])
    assert isinstance(cursor, Cursor)


def test_primeira_pagina_sai_sem_pausa_e_o_pedido_so_acontece_no_proxima():
    cursor, sessao, relogio = abrir([pagina_real("olx_civic_p1")])
    assert sessao.urls == []  # abrir não bate na OLX
    cursor.esperar()  # a 1ª não espera
    pag = cursor.proxima()
    assert relogio.esperas == [] and pag.numero == 1 and len(pag.anuncios) == 50
    assert pag.total_ads == 78 and pag.parou_por is None and not cursor.terminou


def test_primeira_pagina_com_marca_e_modelo_tambem_sai_sem_nenhuma_pausa():
    busca = Busca(texto="civic", marca="Honda", modelo="Civic", estado="MG")
    cursor, sessao, relogio = abrir([pagina_real("olx_poucos")], busca, api=API)
    cursor.esperar()
    pag = cursor.proxima()
    assert relogio.esperas == []
    assert sum("/api/filters/" in u for u in sessao.urls) == 2
    assert "vb=33" in sessao.urls_de_listagem[0] and pag.na_origem[-2:] == ["marca", "modelo"]


def test_segunda_pagina_espera_o_intervalo_cheio_se_o_clique_foi_imediato():
    cursor, _, relogio = abrir([pagina_real("olx_civic_p1"), pagina_real("olx_civic_p2")])
    cursor.proxima()
    cursor.esperar()
    assert relogio.esperas == [1.0]  # o limites() de teste fixa a pausa em 1 s


def test_segunda_pagina_nao_espera_quando_a_pessoa_ja_demorou_mais_que_a_pausa():
    cursor, _, relogio = abrir([pagina_real("olx_civic_p1"), pagina_real("olx_civic_p2")])
    cursor.proxima()
    relogio.agora += 30  # a pessoa leu a lista e clicou 30 s depois
    cursor.esperar()
    assert relogio.esperas == []


def test_so_desconta_o_que_ja_passou():
    cursor, _, relogio = abrir([pagina_real("olx_civic_p1"), pagina_real("olx_civic_p2")])
    cursor.proxima()
    relogio.agora += 0.4
    cursor.esperar()
    assert relogio.esperas == [pytest.approx(0.6)]


def test_duas_paginas_reais_fecham_no_total_da_olx():
    cursor, sessao, _ = abrir([pagina_real("olx_civic_p1"), pagina_real("olx_civic_p2")])
    p1, p2 = cursor.proxima(), cursor.proxima()
    assert (p1.numero, p2.numero) == (1, 2)
    assert p1.acumulado + len(p2.anuncios) == 78 == p2.acumulado
    assert p1.parou_por is None and p2.parou_por == "total_ads" and cursor.terminou
    assert "o=2" in sessao.urls_de_listagem[1]
    with pytest.raises(RuntimeError):
        cursor.proxima()


def test_teto_de_paginas_para_a_busca_e_diz_o_motivo():
    cursor, _, _ = abrir([pagina_real("olx_civic_p1"), pagina_real("olx_civic_p2")], teto=1)
    assert cursor.proxima().parou_por == "max_paginas" and cursor.terminou


def test_bloqueio_nao_avanca_e_a_proxima_chamada_tenta_a_mesma_pagina():
    cursor, sessao, _ = abrir([pagina_real("olx_civic_p1"), RespostaFalsa(429), RespostaFalsa(429), RespostaFalsa(429), pagina_real("olx_civic_p2")])
    cursor.proxima()
    falhou = cursor.proxima()
    assert falhou.parou_por == "bloqueio" and falhou.numero == 2 and not cursor.terminou
    assert falhou.acumulado == 50 and "bloqueio" in falhou.aviso.lower()
    de_novo = cursor.proxima()
    assert de_novo.numero == 2 and de_novo.parou_por == "total_ads" and len(de_novo.anuncios) == 28
    assert sessao.urls_de_listagem[1] == sessao.urls_de_listagem[-1]  # mesma página, mesmo endereço


def test_anuncio_novo_que_empurra_a_lista_nao_repete_carro_nas_paginas_seguintes():
    """Entre a página 1 e a 2 entra um anúncio: o último da 1 reaparece no começo da 2."""
    ids1 = [anuncio_cru(str(i), subject=f"c{i}") for i in range(1, 4)]
    ids2 = [ids1[-1]] + [anuncio_cru(str(i)) for i in range(4, 6)]
    cursor, _, _ = abrir([RespostaFalsa(200, html_com_ads(ids1, 5)), RespostaFalsa(200, html_com_ads(ids2, 5))])
    p1, p2 = cursor.proxima(), cursor.proxima()
    todos = [a.external_id for a in p1.anuncios + p2.anuncios]
    assert todos == ["1", "2", "3", "4", "5"] and len(set(todos)) == 5
    assert p2.coletados == 2 and p2.acumulado == 5


def test_pagina_so_com_repetidos_encerra_a_busca_dizendo_o_motivo():
    a = [anuncio_cru("1")]
    cursor, _, _ = abrir([RespostaFalsa(200, html_com_ads(a, 9)), RespostaFalsa(200, html_com_ads(a, 9))])
    cursor.proxima()
    p2 = cursor.proxima()
    assert p2.parou_por == "pagina_vazia" and "repetidos" in p2.aviso and cursor.terminou


def test_pagina_menor_que_a_primeira_e_a_ultima_mesmo_que_o_total_da_olx_seja_maior():
    """No teste real (fiat argo, MG) a OLX listou 1.360 e dizia ter 1.411: a página 29 veio vazia."""
    cheia = [anuncio_cru(str(i)) for i in range(1, 6)]
    incompleta = [anuncio_cru(str(i)) for i in range(6, 8)]
    cursor, sessao, _ = abrir([RespostaFalsa(200, html_com_ads(cheia, 50)), RespostaFalsa(200, html_com_ads(incompleta, 50))])
    p1, p2 = cursor.proxima(), cursor.proxima()
    assert p1.parou_por is None
    assert p2.parou_por == "pagina_vazia" and cursor.terminou and len(p2.anuncios) == 2
    assert len(sessao.urls_de_listagem) == 2  # não precisa gastar uma 3ª leitura para descobrir


def test_pagina_com_um_repetido_mas_cheia_nao_encerra():
    a = [anuncio_cru(str(i)) for i in range(1, 6)]
    b = [a[-1]] + [anuncio_cru(str(i)) for i in range(6, 10)]  # 5 itens, 1 já visto
    cursor, _, _ = abrir([RespostaFalsa(200, html_com_ads(a, 50)), RespostaFalsa(200, html_com_ads(b, 50))])
    cursor.proxima()
    p2 = cursor.proxima()
    assert p2.coletados == 4 and p2.parou_por is None


def test_pausa_do_ver_mais_pode_ser_menor_que_a_normal():
    cursor, _, relogio = abrir([pagina_real("olx_civic_p1"), pagina_real("olx_civic_p2")])
    cursor.proxima()
    cursor.esperar((2.0, 4.0))
    assert 2.0 <= relogio.esperas[0] <= 4.0
    relogio.agora += 10
    cursor.esperar((2.0, 4.0))  # a pessoa demorou 10 s para clicar
    assert len(relogio.esperas) == 1


# --- a OLX responde o Brasil todo quando não conhece o local ------------------------

BH = "belo-horizonte-e-regiao"


def ads_de(uf, ids):
    return [anuncio_cru(str(i), locationDetails={"municipality": "Cidade", "neighbourhood": "X", "uf": uf}) for i in ids]


def pagina_de(uf, ids, total=50):
    return RespostaFalsa(200, html_com_ads(ads_de(uf, ids), total))


def test_zona_que_a_olx_nao_serve_recua_para_a_regiao_e_avisa():
    busca = Busca(texto="civic", estado="MG", regiao=BH, zona="barreiro")
    cursor, sessao, _ = abrir([pagina_de("SP", range(1, 6)), pagina_de("MG", range(10, 14))], busca)
    pag = cursor.proxima()
    assert [u.split("carros-vans-e-utilitarios")[1] for u in sessao.urls_de_listagem] == [
        f"/estado-mg/{BH}/barreiro?q=civic&sf=1", f"/estado-mg/{BH}?q=civic&sf=1",
    ]
    assert [a.external_id for a in pag.anuncios] == ["10", "11", "12", "13"]  # nada do Brasil todo entrou
    assert "zona" not in pag.na_origem and "regiao" in pag.na_origem
    assert pag.nao_resolvidos == ["a zona barreiro"] and pag.numero == 1


def test_recua_ate_o_estado_se_a_regiao_tambem_nao_for_servida():
    busca = Busca(texto="civic", estado="MG", regiao=BH, zona="barreiro")
    cursor, sessao, _ = abrir([pagina_de("SP", [1]), pagina_de("RJ", [2]), pagina_de("MG", [3])], busca)
    pag = cursor.proxima()
    assert len(sessao.urls_de_listagem) == 3 and sessao.urls_de_listagem[-1].endswith("/estado-mg?q=civic&sf=1")
    assert [a.external_id for a in pag.anuncios] == ["3"]
    assert "regiao" not in pag.na_origem and "zona" not in pag.na_origem
    assert pag.nao_resolvidos == ["a zona barreiro", "a região belo-horizonte-e-regiao"]  # na ordem em que foram caindo


def test_cidade_que_a_olx_nao_serve_volta_a_ser_filtro_local():
    busca = Busca(texto="civic", estado="MG", cidade="Contagem")
    certos = [anuncio_cru("20", locationDetails={"municipality": "Contagem", "neighbourhood": "X", "uf": "MG"}),
              anuncio_cru("21", locationDetails={"municipality": "Betim", "neighbourhood": "X", "uf": "MG"})]
    cursor, sessao, _ = abrir([pagina_de("SP", [1]), RespostaFalsa(200, html_com_ads(certos, 2))], busca)
    pag = cursor.proxima()
    assert sessao.urls_de_listagem[0].endswith("/grande-belo-horizonte/contagem?q=civic&sf=1")
    assert sessao.urls_de_listagem[1].endswith(f"/estado-mg/{BH}/grande-belo-horizonte?q=civic&sf=1")
    assert [a.external_id for a in pag.anuncios] == ["20"]  # o filtro de cidade voltou a valer
    assert "cidade" not in pag.na_origem and pag.nao_resolvidos == ["a cidade Contagem"]
    assert pag.cortados_por_filtro == {"cidade": 1}


def test_local_servido_de_verdade_nao_gasta_leitura_a_mais():
    busca = Busca(texto="civic", estado="MG", regiao=BH, zona="barreiro")
    cursor, sessao, relogio = abrir([pagina_de("MG", range(1, 4))], busca)
    pag = cursor.proxima()
    assert len(sessao.urls_de_listagem) == 1 and relogio.esperas == []
    assert {"regiao", "zona"} <= set(pag.na_origem) and pag.nao_resolvidos == []


def test_sem_estado_nao_tem_o_que_conferir():
    cursor, sessao, _ = abrir([pagina_de("SP", [1]), pagina_de("MG", [2])], Busca(texto="civic"))
    assert [a.external_id for a in cursor.proxima().anuncios] == ["1"] and len(sessao.urls_de_listagem) == 1


def test_o_recuo_vale_para_as_paginas_seguintes():
    busca = Busca(texto="civic", estado="MG", regiao=BH, zona="barreiro")
    p1 = RespostaFalsa(200, html_com_ads(ads_de("MG", range(1, 4)), 8))
    cursor, sessao, _ = abrir([pagina_de("SP", [9]), p1, pagina_de("MG", range(4, 7), 8)], busca)
    cursor.proxima()
    cursor.proxima()
    assert f"/estado-mg/{BH}?" in sessao.urls_de_listagem[-1] and "o=2" in sessao.urls_de_listagem[-1]
    assert "barreiro" not in sessao.urls_de_listagem[-1]  # a página 2 já sai sem a zona que a OLX não serve
