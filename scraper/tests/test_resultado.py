"""Resultado da busca: motivo de parada, avisos, funil e limites configuráveis. Offline.

Rodar dentro de scraper/:  .venv/bin/python -m pytest tests -v
"""

import re
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from config import LimitesBusca  # noqa: E402
from schemas import Busca, ResultadoBusca  # noqa: E402
from sources import olx  # noqa: E402
from sources.base import Fonte  # noqa: E402
from tests.test_busca import carro  # noqa: E402
from tests.test_olx import Relogio, RespostaFalsa, SessaoFalsa, anuncio_cru, html_com_ads  # noqa: E402


def buscar(respostas, busca=None, **lim):
    lim.setdefault("pausa_entre_paginas_segundos", (1.0, 1.0))
    sessao, relogio = SessaoFalsa(respostas), Relogio()
    res = olx.buscar(
        busca or Busca(texto="civic"), LimitesBusca(**lim),
        sessao=sessao, dormir=relogio.dormir, relogio=relogio,
    )
    return res, sessao


def pagina(*ids_, total=99):
    return RespostaFalsa(200, html_com_ads([anuncio_cru(i) for i in ids_], total=total))


def codigos(res):
    return [a.codigo for a in res.avisos]


# --- motivo de parada: um teste por motivo ----------------------------------


def test_motivo_acabaram_paginas_por_total_da_fonte():
    res, _ = buscar([pagina(1, 2, total=2)])
    assert res.motivo_parada == "acabaram_paginas"
    assert codigos(res) == ["poucos_resultados"]  # 2 anúncios, abaixo do limiar de 5, mas sem aviso de teto


def test_motivo_acabaram_paginas_por_pagina_vazia():
    res, _ = buscar([pagina(1, total=99), RespostaFalsa(200, html_com_ads([], 99))])
    assert res.motivo_parada == "acabaram_paginas"
    assert res.paginas_lidas == 2


def test_motivo_teto_paginas():
    res, sessao = buscar([pagina(1), pagina(2), pagina(3)], max_paginas=2)
    assert res.motivo_parada == "teto_paginas"
    assert res.paginas_lidas == 2 and len(sessao.urls) == 2
    assert [a.external_id for a in res.anuncios] == ["1", "2"]  # devolve o que tem


def test_motivo_teto_tempo():
    res, sessao = buscar(
        [pagina(1), pagina(2), pagina(3)], max_paginas=8,
        pausa_entre_paginas_segundos=(10.0, 10.0), tempo_max_segundos=15.0,
    )
    assert res.motivo_parada == "teto_tempo"
    assert len(sessao.urls) == 2


def test_motivo_falha_fonte_devolve_o_que_juntou_sem_erro():
    res, _ = buscar([pagina(1, 2), RespostaFalsa(403), RespostaFalsa(403), RespostaFalsa(403)])
    assert res.motivo_parada == "falha_fonte"
    assert [a.external_id for a in res.anuncios] == ["1", "2"]
    assert res.paginas_lidas == 1


def test_falha_inesperada_no_meio_tambem_vira_falha_fonte(monkeypatch):
    original = olx.normalizar

    def quebra_no_segundo(ad):
        if ad["listId"] == 2:
            raise KeyError("campo estranho")
        return original(ad)

    monkeypatch.setattr(olx, "normalizar", quebra_no_segundo)
    res, _ = buscar([pagina(1), pagina(2)])
    assert res.motivo_parada == "falha_fonte"
    assert [a.external_id for a in res.anuncios] == ["1"]
    assert "KeyError" in res.avisos[0].detalhe_tecnico


# --- avisos: um teste por código --------------------------------------------


def test_aviso_teto_paginas_com_numeros():
    res, _ = buscar([pagina(1), pagina(2)], max_paginas=1, limiar_poucos_resultados=0)
    (aviso,) = res.avisos
    assert aviso.codigo == "teto_paginas"
    assert "parou em 1 paginas, teto 1, tempo" in aviso.detalhe_tecnico
    assert "de 180s" in aviso.detalhe_tecnico


def test_aviso_teto_tempo_com_numeros():
    res, _ = buscar(
        [pagina(1), pagina(2)], pausa_entre_paginas_segundos=(10.0, 10.0),
        tempo_max_segundos=5.0, limiar_poucos_resultados=0,
    )
    (aviso,) = res.avisos
    assert aviso.codigo == "teto_tempo"
    assert "de 5s" in aviso.detalhe_tecnico


def test_aviso_muitos_resultados_so_avisa_e_nao_corta():
    ids_ = list(range(1, 61))
    res, _ = buscar([pagina(*ids_, total=60)], limiar_muitos_resultados=50)
    assert "muitos_resultados" in codigos(res)
    assert len(res.anuncios) == 60  # nenhum corte por quantidade
    assert "limiar 50" in next(a for a in res.avisos if a.codigo == "muitos_resultados").detalhe_tecnico


def test_aviso_poucos_resultados_depois_do_filtro_local():
    html = html_com_ads([carro(i, "Honda", "Civic", 2018, 50000 + i, "Recife", uf="PE") for i in range(1, 11)], total=10)
    res, _ = buscar([RespostaFalsa(200, html)], Busca(texto="civic", cidade="Natal"))
    assert res.funil.finais == 0
    assert codigos(res) == ["poucos_resultados"]
    assert "cortados 10" in res.avisos[0].detalhe_tecnico


def test_aviso_fonte_parcial():
    res, _ = buscar([pagina(1), RespostaFalsa(429), RespostaFalsa(429), RespostaFalsa(429)], limiar_poucos_resultados=0)
    (aviso,) = res.avisos
    assert aviso.codigo == "fonte_parcial"
    assert "HTTP 429" in aviso.detalhe_tecnico and "coletados 1" in aviso.detalhe_tecnico


def test_sem_aviso_quando_tudo_normal():
    res, _ = buscar([pagina(1, 2, 3, 4, 5, 6, total=6)])
    assert res.avisos == []


def test_mensagem_curta_e_sem_traco_dois_pontos_ou_ponto_e_virgula():
    cenarios = [
        buscar([pagina(1), pagina(2)], max_paginas=1)[0],
        buscar([pagina(1), pagina(2)], pausa_entre_paginas_segundos=(10.0, 10.0), tempo_max_segundos=5.0)[0],
        buscar([pagina(1), RespostaFalsa(403), RespostaFalsa(403), RespostaFalsa(403)])[0],
        buscar([RespostaFalsa(403)] * 3)[0],
        buscar([pagina(*range(1, 11), total=900)], limiar_muitos_resultados=50)[0],
        buscar([pagina(1, total=1)])[0],
    ]
    vistos = {a.codigo for r in cenarios for a in r.avisos}
    assert vistos == {"teto_paginas", "teto_tempo", "fonte_parcial", "muitos_resultados", "poucos_resultados"}
    for r in cenarios:
        for a in r.avisos:
            assert not re.search(r"[-:;–—]", a.mensagem), a.mensagem
            assert len(a.mensagem) < 140


# --- funil -------------------------------------------------------------------


def test_funil_bate_com_filtros_locais():
    anuncios = [
        carro(1, "Honda", "Civic EXL", 2018, 40000, "Natal", uf="RN"),
        carro(2, "Honda", "Civic LXR", 2016, 30000, "Natal", uf="RN"),   # reprova ano? ano ok, km ok
        carro(3, "Toyota", "Corolla", 2018, 40000, "Natal", uf="RN"),    # marca
        carro(4, "Honda", "Fit", 2018, 40000, "Natal", uf="RN"),         # modelo
        carro(5, "Honda", "Civic EXL", 2018, 40000, "Recife", uf="PE"),  # cidade
        carro(6, "Honda", "Civic EXL", 2018, 90000, "Natal", uf="RN"),   # km
    ]
    busca = Busca(texto="civic", marca="honda", modelo="civic", cidade="natal", km_max=50000)
    res, _ = buscar([RespostaFalsa(200, html_com_ads(anuncios, total=6))], busca)
    f = res.funil
    assert (f.total_na_fonte, f.coletados, f.finais) == (6, 6, 2)
    assert f.cortados_por_filtro == {"marca": 1, "modelo": 1, "cidade": 1, "km": 1}
    assert f.coletados - sum(f.cortados_por_filtro.values()) == f.finais == len(res.anuncios)


def test_funil_soma_varias_paginas_e_nao_conta_repetidos():
    p1 = html_com_ads([carro(1, "Honda", "Civic", 2018, 10, "A"), carro(2, "Fiat", "Uno", 2018, 10, "A")], total=3)
    p2 = html_com_ads([carro(2, "Fiat", "Uno", 2018, 10, "A"), carro(3, "Fiat", "Uno", 2018, 10, "A")], total=3)
    res, _ = buscar([RespostaFalsa(200, p1), RespostaFalsa(200, p2)], Busca(texto="x", marca="fiat"))
    f = res.funil
    assert (f.coletados, f.cortados_por_filtro, f.finais) == (3, {"marca": 1}, 2)
    assert f.coletados - sum(f.cortados_por_filtro.values()) == f.finais
    assert res.paginas_lidas == 2


def test_funil_sem_filtros_locais_nao_corta_nada():
    res, _ = buscar([pagina(1, 2, 3, total=3)])
    assert res.funil.cortados_por_filtro == {}
    assert res.funil.coletados == res.funil.finais == 3


# --- limites configuráveis ---------------------------------------------------


def test_limites_padrao_medianos_e_sem_limite_de_resultados():
    lim = LimitesBusca()
    assert (lim.max_paginas, lim.tempo_max_segundos, lim.limiar_muitos_resultados) == (8, 180.0, 500)
    assert lim.pausa_entre_paginas_segundos == (6.0, 14.0)
    assert not any("resultados" in c and "limiar" not in c for c in LimitesBusca.model_fields)


def test_variavel_de_ambiente_sobrescreve_e_parametro_sobrescreve_o_ambiente(monkeypatch):
    monkeypatch.setenv("GARIMPO_MAX_PAGINAS", "3")
    monkeypatch.setenv("GARIMPO_PAUSA_ENTRE_PAGINAS_SEGUNDOS", "2, 4")
    monkeypatch.setenv("GARIMPO_TEMPO_MAX_SEGUNDOS", "60")
    lim = LimitesBusca()
    assert (lim.max_paginas, lim.tempo_max_segundos, lim.pausa_entre_paginas_segundos) == (3, 60.0, (2.0, 4.0))
    assert LimitesBusca(max_paginas=5).max_paginas == 5


def test_variavel_de_ambiente_invalida_da_erro_claro(monkeypatch):
    monkeypatch.setenv("GARIMPO_MAX_PAGINAS", "muitas")
    with pytest.raises(ValueError, match="GARIMPO_MAX_PAGINAS"):
        LimitesBusca()


def test_a_busca_usa_o_limite_configurado_no_ambiente(monkeypatch):
    monkeypatch.setenv("GARIMPO_MAX_PAGINAS", "1")
    sessao, relogio = SessaoFalsa([pagina(1), pagina(2)]), Relogio()
    res = olx.buscar(Busca(texto="civic"), sessao=sessao, dormir=relogio.dormir, relogio=relogio)
    assert res.motivo_parada == "teto_paginas" and len(sessao.urls) == 1


# --- interface comum ---------------------------------------------------------


def test_olx_segue_a_interface_de_fonte():
    assert isinstance(olx, Fonte)
    assert olx.FONTE == "olx"
    res, _ = buscar([pagina(1, total=1)])
    assert isinstance(res, ResultadoBusca) and res.fonte == "olx"
