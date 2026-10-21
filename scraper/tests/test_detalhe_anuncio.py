"""Página do anúncio (o Garimpar): leitura, conferência do id, repetições e endpoint. Sem internet.

Rodar dentro de scraper/:  .venv/bin/python -m pytest tests/test_detalhe_anuncio.py -v
"""

import copy
import html
import json
import re
import sys
import threading
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import server  # noqa: E402
from config import LimitesBusca  # noqa: E402
from schemas import DetalheAnuncio, FichaDetalhes, LocalAnuncio  # noqa: E402
from sources import olx  # noqa: E402
from tests.test_olx import Relogio, RespostaFalsa  # noqa: E402
from tests.test_server import FonteFalsa, cliente  # noqa: E402

FIXTURE = RAIZ / "tests" / "fixtures" / "olx_anuncio.json"
ID = "1546298897"
URL = f"https://mg.olx.com.br/regiao-de-pocos-de-caldas-e-varginha/autos-e-pecas/carros-vans-e-utilitarios/chevrolet-onix-2024-{ID}"


def ad_real():
    return copy.deepcopy(json.loads(FIXTURE.read_text(encoding="utf-8"))["ad"])


def html_do_anuncio(ad):
    """Mesmo formato da OLX: o JSON vai escapado dentro do atributo data-json do script initial-data."""
    corpo = html.escape(json.dumps({"ad": ad}, ensure_ascii=False), quote=True)
    return f"<html><head><script id=\"initial-data\" type=\"text/plain\" data-json='{corpo}'></script></head><body></body></html>"


class SessaoDoAnuncio:
    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.urls = []

    def get(self, url, **kw):
        self.urls.append(url)
        resposta = self.respostas.pop(0)
        if isinstance(resposta, Exception):
            raise resposta
        return resposta


def limites():
    return LimitesBusca(pausa_entre_paginas_segundos=(1.0, 1.0), tentativas_bloqueio=2, backoff_base_segundos=10.0)


# ---------------------------------------------------------------------------
# Leitura da página
# ---------------------------------------------------------------------------


def test_le_todos_os_quadros_da_pagina_real():
    d = olx.normalizar_detalhe(olx.extrair_anuncio(html_do_anuncio(ad_real())), URL)
    assert (d.source, d.external_id, d.url) == ("olx", ID, URL)
    assert d.detalhes == FichaDetalhes(
        categoria="Carros, vans e utilitários", modelo="Onix Hatch LT 1.0 12V Flex Mec. 4P", marca="Chevrolet",
        tipo="Hatch", ano=2024, km=19798, potencia="1.0", combustivel="Flex", cambio="Manual", direcao="Elétrica",
        cor="Prata", portas="4 portas", final_placa=None, kit_gnv="Não",
    )
    assert d.opcionais[:3] == ["Air bag", "Ar condicionado", "Alarme"]
    assert {"Computador de bordo", "Trava elétrica", "Vidro elétrico"} <= set(d.opcionais)
    assert d.outras[:2] == ["Aceita trocas", "IPVA pago"]
    assert d.outras.count("IPVA pago") == 1  # também vem na lista "Documentação e regularização"
    assert "Único dono" in d.outras and d.outras.count("Único dono") == 1
    assert d.localizacao == LocalAnuncio(bairro="Centro", cidade="Poços de Caldas", estado="MG", cep="37701740")


def test_descricao_completa_com_quebras_e_sem_contato():
    d = olx.normalizar_detalhe(ad_real(), URL)
    assert d.descricao.startswith("CHEVROLET ONIX LT2 2023 - IMPECÁVEL!\n\nUma oportunidade")
    assert "Valor: R$ 68.900" in d.descricao
    assert "<br>" not in d.descricao
    assert "99999" not in d.descricao
    assert d.descricao.endswith(f"Contato/WhatsApp {olx.CONTATO_ESCONDIDO}")


@pytest.mark.parametrize("texto", [
    "liga (31) 99999-0000", "zap 31999990000", "+55 31 3333-4444", "cel 99999 0000", "email loja@exemplo.com.br",
])
def test_esconde_telefone_e_email(texto):
    assert olx.CONTATO_ESCONDIDO in olx.esconder_contato(texto)
    assert not re.search(r"\d{4}|@", olx.esconder_contato(texto))


@pytest.mark.parametrize("texto", [
    "R$ 68.900 em 48x R$ 1.824,15", "19.000 km", "CEP 37701-740 ou 37701740", "anos 2019 2020 2021",
])
def test_nao_esconde_preco_km_cep_nem_ano(texto):
    assert olx.esconder_contato(texto) == texto


def test_campo_ausente_fica_vazio_sem_inventar():
    ad = {"listId": int(ID), "properties": [{"name": "regdate", "value": "2015"}, {"name": "end_tag", "value": "7"}]}
    d = olx.normalizar_detalhe(ad, URL)
    assert d.detalhes.ano == 2015 and d.detalhes.final_placa == "7"
    assert d.detalhes.km is None and d.detalhes.marca is None and d.detalhes.kit_gnv is None
    assert d.opcionais == [] and d.outras == [] and d.descricao is None
    assert d.localizacao == LocalAnuncio()


def test_listas_vazias_da_olx_nao_viram_item_e_nao_mostra_o_que_e_nao():
    ad = {"listId": int(ID), "properties": [
        {"name": "documentation_and_regularization", "value": "0"},
        {"name": "exchange", "value": "Não"},
        {"name": "has_auction", "value": "Sim"},
        {"name": "car_features", "value": "Alarme, Som"},
        {"name": "has_gnv_kit", "value": "Sim"},
    ]}
    d = olx.normalizar_detalhe(ad, URL)
    assert d.outras == ["De leilão"]
    assert d.opcionais == ["Alarme", "Som"]
    assert d.detalhes.kit_gnv == "Sim"


def test_localizacao_cai_para_location_properties():
    ad = {"listId": int(ID), "locationProperties": [
        {"label": "CEP", "value": "30140-071"}, {"label": "Município", "value": "Belo Horizonte"}, {"label": "Bairro", "value": "Savassi"},
    ]}
    assert olx.normalizar_detalhe(ad, URL).localizacao == LocalAnuncio(bairro="Savassi", cidade="Belo Horizonte", cep="30140071")


def test_nao_guarda_propriedade_de_anunciante():
    ad = ad_real()
    ad["properties"].append({"name": "sellerName", "value": "Fulano"})
    ad["user"] = {"name": "Fulano"}
    texto = olx.normalizar_detalhe(ad, URL).model_dump_json()
    assert "Fulano" not in texto


def test_pagina_sem_initial_data_levanta_erro_proprio():
    with pytest.raises(olx.PaginaSemAnuncioError):
        olx.extrair_anuncio("<html><body>Carregando</body></html>")


# ---------------------------------------------------------------------------
# Endereço do anúncio
# ---------------------------------------------------------------------------


def test_endereco_limpo_sem_query_nem_ancora():
    assert olx.url_do_anuncio(ID, URL + "?lis=listing_1#fotos") == URL


@pytest.mark.parametrize("id_, url", [
    (ID, f"http://mg.olx.com.br/x/carro-{ID}"),
    (ID, f"https://olx.com.br.golpe.com/x/carro-{ID}"),
    (ID, f"https://mg.olx.com.br/x/carro-1{ID}"),
    (ID, "https://mg.olx.com.br/x/carro-123"),
    (ID, f"https://usuario@mg.olx.com.br/x/carro-{ID}"),
    ("abc", "https://mg.olx.com.br/x/carro-abc"),
    ("", "https://mg.olx.com.br/x/carro-"),
])
def test_endereco_que_nao_e_desse_anuncio_na_olx_e_recusado(id_, url):
    with pytest.raises(ValueError):
        olx.url_do_anuncio(id_, url)


# ---------------------------------------------------------------------------
# Pedido à OLX
# ---------------------------------------------------------------------------


def test_detalhar_pede_uma_vez_e_confere_o_id():
    sessao = SessaoDoAnuncio([RespostaFalsa(200, html_do_anuncio(ad_real()))])
    d = olx.detalhar(ID, URL + "?x=1", limites(), sessao=sessao, dormir=lambda s: None)
    assert sessao.urls == [URL]
    assert isinstance(d, DetalheAnuncio) and d.external_id == ID


def test_detalhar_tenta_de_novo_depois_de_bloqueio():
    relogio = Relogio()
    sessao = SessaoDoAnuncio([RespostaFalsa(403), RespostaFalsa(200, "<html></html>"), RespostaFalsa(200, html_do_anuncio(ad_real()))])
    d = olx.detalhar(ID, URL, limites(), sessao=sessao, dormir=relogio.dormir, relogio=relogio)
    assert d.external_id == ID and len(sessao.urls) == 3 and len(relogio.esperas) == 2


def test_detalhar_usa_as_repeticoes_pedidas():
    relogio = Relogio()
    sessao = SessaoDoAnuncio([RespostaFalsa(429), RespostaFalsa(429)])
    with pytest.raises(olx.DetalheIndisponivelError, match="HTTP 429"):
        olx.detalhar(ID, URL, limites(), repeticoes=1, espera_repeticao=(2.0, 2.0), sessao=sessao,
                     dormir=relogio.dormir, relogio=relogio)
    assert relogio.esperas == [2.0] and len(sessao.urls) == 2


def test_detalhar_falha_de_rede_vira_indisponivel():
    sessao = SessaoDoAnuncio([TimeoutError(), TimeoutError()])
    with pytest.raises(olx.DetalheIndisponivelError, match="falha de rede"):
        olx.detalhar(ID, URL, limites(), repeticoes=1, espera_repeticao=(0, 0), sessao=sessao, dormir=lambda s: None)


@pytest.mark.parametrize("status", [404, 410])
def test_anuncio_que_saiu_do_ar_nao_repete(status):
    sessao = SessaoDoAnuncio([RespostaFalsa(status)])
    with pytest.raises(olx.AnuncioSaiuError):
        olx.detalhar(ID, URL, limites(), sessao=sessao, dormir=lambda s: None)
    assert len(sessao.urls) == 1


def test_pagina_de_outro_anuncio_e_recusada():
    ad = ad_real()
    ad["listId"] = 999
    sessao = SessaoDoAnuncio([RespostaFalsa(200, html_do_anuncio(ad))])
    with pytest.raises(olx.DetalheIndisponivelError, match="999"):
        olx.detalhar(ID, URL, limites(), sessao=sessao, dormir=lambda s: None)
    assert len(sessao.urls) == 1


def test_endereco_errado_nem_chega_a_pedir():
    sessao = SessaoDoAnuncio([])
    with pytest.raises(ValueError):
        olx.detalhar(ID, "https://exemplo.com/" + ID, limites(), sessao=sessao)
    assert sessao.urls == []


# ---------------------------------------------------------------------------
# Endpoint /anuncio/detalhe
# ---------------------------------------------------------------------------


class FonteComDetalhe(FonteFalsa):
    url_do_anuncio = staticmethod(olx.url_do_anuncio)

    def __init__(self, erros=None, segurar=None):
        super().__init__()
        self.erros = list(erros or [])
        self.detalhes_pedidos = []
        self.segurar_detalhe = segurar

    def detalhar(self, external_id, url, limites=None, *, repeticoes=None, espera_repeticao=None):
        self.detalhes_pedidos.append((external_id, url, repeticoes, espera_repeticao))
        if self.segurar_detalhe:
            assert self.segurar_detalhe.wait(5)
        if self.erros:
            raise self.erros.pop(0)
        olx.url_do_anuncio(external_id, url)
        return olx.normalizar_detalhe(ad_real() | {"listId": int(external_id)}, url)


def pedir(c, id_=ID, url=URL, fonte="falsa"):
    return c.get("/anuncio/detalhe", params={"fonte": fonte, "id": id_, "url": url})


def test_endpoint_devolve_o_detalhe_ligado_ao_anuncio():
    c, fonte = cliente(FonteComDetalhe())
    r = pedir(c)
    assert r.status_code == 200
    corpo = r.json()
    assert (corpo["source"], corpo["external_id"]) == ("olx", ID)
    assert corpo["detalhes"]["km"] == 19798 and corpo["localizacao"]["cep"] == "37701740"
    assert "Aceita trocas" in corpo["outras"] and corpo["descricao"]
    assert corpo["do_cache"] is False
    assert fonte.buscas == []  # não abre busca nenhuma
    _, _, repeticoes, espera = fonte.detalhes_pedidos[0]
    assert (repeticoes, espera) == (server.config.REPETICOES_VER_MAIS, server.config.ESPERA_REPETICAO_VER_MAIS_SEGUNDOS)


def test_segunda_vez_vem_guardado_sem_pedir_de_novo():
    c, fonte = cliente(FonteComDetalhe())
    pedir(c)
    r = pedir(c)
    assert r.json()["do_cache"] is True and len(fonte.detalhes_pedidos) == 1
    outro = pedir(c, id_="123", url="https://mg.olx.com.br/x/carro-123")
    assert outro.json()["external_id"] == "123" and len(fonte.detalhes_pedidos) == 2


def test_guardado_vence_com_o_ttl():
    c, fonte = cliente(FonteComDetalhe(), ttl=0.0)
    pedir(c)
    pedir(c)
    assert len(fonte.detalhes_pedidos) == 2


def test_falha_nao_fica_guardada_e_tentar_de_novo_le_de_novo():
    c, fonte = cliente(FonteComDetalhe(erros=[olx.DetalheIndisponivelError("HTTP 403")]))
    r = pedir(c)
    assert r.status_code == 503 and r.json() == {"erro": server.MSG_DETALHE_FALHOU}
    r = pedir(c)
    assert r.status_code == 200 and len(fonte.detalhes_pedidos) == 2


def test_anuncio_que_saiu_do_ar_avisa_com_calma():
    c, _ = cliente(FonteComDetalhe(erros=[olx.AnuncioSaiuError("HTTP 404")]))
    r = pedir(c)
    assert r.status_code == 404 and r.json() == {"erro": server.MSG_DETALHE_SAIU}


def test_erro_inesperado_tambem_vira_mensagem_humana():
    c, _ = cliente(FonteComDetalhe(erros=[RuntimeError("quebrou")]))
    r = pedir(c)
    assert r.status_code == 503 and r.json() == {"erro": server.MSG_DETALHE_FALHOU}


def test_pedido_ruim_nao_chega_na_olx():
    c, fonte = cliente(FonteComDetalhe())
    assert pedir(c, url="https://exemplo.com/carro-" + ID).status_code == 422
    assert pedir(c, fonte="webmotors").json() == {"erro": server.MSG_DETALHE_PEDIDO}
    assert c.get("/anuncio/detalhe", params={"fonte": "falsa", "id": ID}).status_code == 422
    assert fonte.detalhes_pedidos == []


def test_endereco_ruim_nao_pega_carona_no_guardado():
    c, fonte = cliente(FonteComDetalhe())
    assert pedir(c).status_code == 200
    r = pedir(c, url="https://golpe.com/carro-" + ID)
    assert r.status_code == 422 and r.json() == {"erro": server.MSG_DETALHE_PEDIDO}
    assert pedir(c, url=URL + "?de=lista").json()["do_cache"] is True
    assert [p[1] for p in fonte.detalhes_pedidos] == [URL]


def test_fonte_sem_detalhe_responde_que_nao_reconheceu():
    c, _ = cliente(FonteFalsa())
    r = pedir(c)
    assert r.status_code == 422 and r.json() == {"erro": server.MSG_DETALHE_PEDIDO}


def test_mesmo_anuncio_ao_mesmo_tempo_le_uma_vez_so():
    segurar = threading.Event()
    c, fonte = cliente(FonteComDetalhe(segurar=segurar))
    respostas = []
    linhas = [threading.Thread(target=lambda: respostas.append(pedir(c))) for _ in range(3)]
    for linha in linhas:
        linha.start()
    segurar.set()
    for linha in linhas:
        linha.join(5)
    assert [r.status_code for r in respostas] == [200, 200, 200]
    assert len(fonte.detalhes_pedidos) == 1


def test_guarda_e_limpa_as_travas():
    guardados = server.DetalhesGuardados(60.0)
    d = olx.normalizar_detalhe(ad_real(), URL)
    assert guardados.obter(("olx", ID), lambda: d) == (d, False)
    assert guardados.obter(("olx", ID), lambda: pytest.fail("não devia ler")) == (d, True)
    assert guardados._travas == {}


def test_mensagens_do_detalhe_sem_traco_dois_pontos_ou_ponto_e_virgula():
    for msg in (server.MSG_DETALHE_FALHOU, server.MSG_DETALHE_SAIU, server.MSG_DETALHE_PEDIDO):
        assert not re.search(r"[-:;–—]", msg)
        assert "veículo" not in msg.lower()
