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
