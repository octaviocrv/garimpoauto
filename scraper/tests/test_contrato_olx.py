"""Contrato da fonte OLX com páginas reais salvas (tests/fixtures/olx_*.json, sem dado de
anunciante). Mostram o que a OLX entrega de verdade: muitos resultados em duas páginas, poucos,
zero e bloqueio. Tudo offline. O total que a OLX diz ter tem que bater com o que chegou."""

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from schemas import Busca  # noqa: E402
from sources import olx  # noqa: E402
from tests.test_olx import Relogio, RespostaFalsa, SessaoFalsa, html_com_ads, limites  # noqa: E402

FIXTURES = RAIZ / "tests" / "fixtures"


def pagina_real(nome: str) -> RespostaFalsa:
    dados = json.loads((FIXTURES / f"{nome}.json").read_text(encoding="utf-8"))
    return RespostaFalsa(200, html_com_ads(dados["ads"], dados["total"]))


def buscar(respostas, busca=None, **kw):
    sessao, relogio = SessaoFalsa(respostas), Relogio()
    resultado = olx.buscar(
        busca or Busca(texto="civic 2018", estado="MG"), limites(**kw),
        sessao=sessao, dormir=relogio.dormir, relogio=relogio,
    )
    return resultado, sessao


def test_muitos_resultados_em_duas_paginas_e_o_total_da_olx_bate_com_o_que_chegou():
    r, sessao = buscar([pagina_real("olx_civic_p1"), pagina_real("olx_civic_p2")])
    assert r.funil.total_na_fonte == 78
    assert len(r.anuncios) == 78 == r.funil.finais == r.funil.coletados
    assert len({a.external_id for a in r.anuncios}) == 78  # sem id repetido
    assert r.paginas_lidas == 2 and r.motivo_parada == "acabaram_paginas"
    assert len(sessao.urls) == 2 and "o=2" in sessao.urls[1]
    assert r.avisos == []


def test_propaganda_fica_de_fora_e_so_entra_anuncio_com_list_id():
    dados = json.loads((FIXTURES / "olx_civic_p1.json").read_text(encoding="utf-8"))
    assert len(dados["ads"]) > 50 and sum("listId" in a for a in dados["ads"]) == 50
    itens, total = olx.extrair_pagina(pagina_real("olx_civic_p1").html_content)
    assert len(itens) == 50 and total == 78


def test_campos_principais_vem_preenchidos_em_99_por_cento():
    r, _ = buscar([pagina_real("olx_civic_p1"), pagina_real("olx_civic_p2")])
    for campo in ("preco", "ano", "km", "cidade", "modelo", "marca", "estado"):
        cheios = sum(getattr(a, campo) is not None for a in r.anuncios)
        assert cheios / len(r.anuncios) >= 0.99, campo
    # o que falta vem marcado e nunca é descartado
    assert all(a.incompleto == bool(a.campos_faltando) for a in r.anuncios)


def test_nenhum_dado_de_anunciante_no_item_cru():
    r, _ = buscar([pagina_real("olx_civic_p1")], max_paginas=1)
    texto = json.dumps([a.raw for a in r.anuncios]).lower()
    for termo in ("sellername", "username", "phone", "telefone", "whatsapp"):
        assert termo not in texto


def test_poucos_resultados_numa_pagina_so():
    r, sessao = buscar([pagina_real("olx_poucos")])
    assert r.funil.total_na_fonte == 10 and len(r.anuncios) == 10
    assert len(sessao.urls) == 1 and r.paginas_lidas == 1
    assert r.motivo_parada == "acabaram_paginas"


def test_zero_resultados_nao_e_erro_e_diz_que_sobrou_pouco():
    r, _ = buscar([pagina_real("olx_zero")])
    assert r.anuncios == [] and r.funil.total_na_fonte == 0
    assert r.motivo_parada == "acabaram_paginas"
    assert [a.codigo for a in r.avisos] == ["poucos_resultados"]


def test_bloqueio_na_primeira_pagina_nao_quebra_e_avisa():
    r, sessao = buscar([RespostaFalsa(403)] * 3)
    assert r.anuncios == [] and r.motivo_parada == "falha_fonte"
    assert [a.codigo for a in r.avisos] == ["fonte_parcial"]
    assert len(sessao.urls) == 3  # a tentativa normal e mais 2


def test_bloqueio_na_segunda_pagina_devolve_a_primeira_e_diz_que_ficou_parcial():
    r, _ = buscar([pagina_real("olx_civic_p1")] + [RespostaFalsa(429)] * 3)
    assert len(r.anuncios) == 50 and r.paginas_lidas == 1
    assert r.motivo_parada == "falha_fonte"
    aviso = next(a for a in r.avisos if a.codigo == "fonte_parcial")
    assert "incompleta" in aviso.mensagem and "bloqueio" in aviso.detalhe_tecnico.lower()
    assert r.funil.coletados == 50 and r.funil.finais == 50


def test_pagina_200_sem_ads_conta_como_bloqueio():
    r, _ = buscar([RespostaFalsa(200, "<html><body>captcha</body></html>")] * 3)
    assert r.motivo_parada == "falha_fonte"


def test_o_funil_sempre_fecha_as_contas():
    busca = Busca(texto="civic 2018", estado="MG", cidade="Belo Horizonte")
    r, _ = buscar([pagina_real("olx_civic_p1"), pagina_real("olx_civic_p2")], busca)
    assert r.funil.coletados - sum(r.funil.cortados_por_filtro.values()) == r.funil.finais == len(r.anuncios)
    assert all(a.cidade == "Belo Horizonte" for a in r.anuncios)


# --- datas, destaque e repetido (páginas reais) -------------------------------


def todos_os_anuncios():
    r, _ = buscar([pagina_real("olx_civic_p1"), pagina_real("olx_civic_p2")])
    return r.anuncios


def test_data_so_vira_publicacao_quando_nunca_foi_renovado():
    brutos = {}
    for nome in ("olx_civic_p1", "olx_civic_p2"):
        for ad in json.loads((FIXTURES / f"{nome}.json").read_text(encoding="utf-8"))["ads"]:
            if "listId" in ad:
                brutos[str(ad["listId"])] = ad
    anuncios = todos_os_anuncios()
    nunca = [a for a in anuncios if brutos[a.external_id]["lastBumpAgeSecs"] == "0"]
    renovados = [a for a in anuncios if brutos[a.external_id]["lastBumpAgeSecs"] != "0"]
    assert nunca and renovados  # a página real tem os dois casos
    assert all(a.publicado_em is not None and a.renovado_em is None for a in nunca)
    assert all(a.publicado_em is None and a.renovado_em is not None for a in renovados)
    assert all((a.publicado_em or a.renovado_em).tzinfo is not None for a in anuncios)


def test_anuncio_em_destaque_e_marcado_e_continua_na_lista():
    anuncios = todos_os_anuncios()
    destaques = [a for a in anuncios if a.em_destaque]
    assert 0 < len(destaques) < len(anuncios) and len(anuncios) == 78


def test_repetido_entre_lojas_e_marcado_sem_apagar_nada():
    anuncios = todos_os_anuncios()
    ids = {a.external_id for a in anuncios}
    repetidos = [a for a in anuncios if a.repetido_de]
    assert all(a.repetido_de in ids and a.repetido_de != a.external_id for a in repetidos)
    assert len(anuncios) == 78  # marcar não tira ninguém


def test_sem_o_campo_de_renovacao_nao_inventa_data():
    from tests.test_olx import anuncio_cru
    sem = anuncio_cru("1")
    sem.pop("lastBumpAgeSecs", None)
    a = olx.normalizar(sem)
    assert a.publicado_em is None and a.renovado_em is None
    nunca = olx.normalizar(anuncio_cru("2", lastBumpAgeSecs="0"))
    assert nunca.publicado_em is not None and nunca.renovado_em is None
    renovado = olx.normalizar(anuncio_cru("3", lastBumpAgeSecs="3600"))
    assert renovado.publicado_em is None and renovado.renovado_em is not None
    estranho = olx.normalizar(anuncio_cru("4", lastBumpAgeSecs="abc"))
    assert estranho.publicado_em is None and estranho.renovado_em is None


def test_destaque_pelos_dois_campos_da_olx():
    from tests.test_olx import anuncio_cru
    assert olx.normalizar(anuncio_cru("1", isFeatured=True)).em_destaque
    assert olx.normalizar(anuncio_cru("2", fixedOnTop=True)).em_destaque
    assert not olx.normalizar(anuncio_cru("3", isFeatured=False, fixedOnTop=False)).em_destaque


def test_mesmo_carro_em_paginas_diferentes_aponta_para_o_primeiro():
    from tests.test_olx import anuncio_cru
    a, b, c = (anuncio_cru(i) for i in ("10", "11", "12"))
    c["priceValue"] = "R$ 99.000"  # preço diferente: outro carro
    p1 = RespostaFalsa(200, html_com_ads([a], 3))
    p2 = RespostaFalsa(200, html_com_ads([b, c], 3))
    r, _ = buscar([p1, p2])
    por_id = {x.external_id: x for x in r.anuncios}
    assert por_id["10"].repetido_de is None
    assert por_id["11"].repetido_de == "10"
    assert por_id["12"].repetido_de is None
    assert len(r.anuncios) == 3


def test_sem_preco_ou_km_nao_marca_repetido():
    from tests.test_olx import anuncio_cru
    a, b = anuncio_cru("20", priceValue=None, price=None), anuncio_cru("21", priceValue=None, price=None)
    r, _ = buscar([RespostaFalsa(200, html_com_ads([a, b], 2))])
    assert all(x.repetido_de is None for x in r.anuncios)
