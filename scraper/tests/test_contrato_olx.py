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
