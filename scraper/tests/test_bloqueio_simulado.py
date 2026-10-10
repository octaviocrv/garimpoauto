"""Bloqueio da OLX simulado de ponta a ponta, sem bater na OLX.

O coletor de verdade (CursorOlx, com retry e pausa) roda atrás do servidor de verdade. Só a
sessão HTTP é falsa: ela devolve o roteiro combinado (403, captcha, JSON quebrado, timeout,
página vazia) e o relógio é falso, então ninguém espera de verdade.

Em todos os casos vale a mesma regra: lista parcial nunca passa por completa. A página que
falhou não vem, as já lidas ficam guardadas, dá pra pedir a mesma página de novo, e o texto
fala como o Garimpo Auto (sem termo técnico e sem traço, dois pontos ou ponto e vírgula).

Rodar dentro de scraper/:  .venv/bin/python -m pytest tests -v
"""

import json
import re
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import server  # noqa: E402
from sources import olx  # noqa: E402
from tests.test_olx import Relogio, RespostaFalsa, anuncio_cru, html_com_ads, limites  # noqa: E402
from tests.test_server import eventos  # noqa: E402

TENTATIVAS = 2  # tentativas_bloqueio padrão (página 1, /buscar e stream): 1 pedido + 2 repetições
REPETICOES = 1  # "Ver mais" da página 2 em diante: 1 pedido + 1 repetição, esperando de 5 a 10 s


class SessaoRoteirizada:
    """Responde na ordem do roteiro. Item que é exceção é levantado (rede, timeout). Acabou o
    roteiro, devolve uma página vazia sem total, como a OLX faz depois da última."""

    def __init__(self, roteiro):
        self.roteiro, self.urls = list(roteiro), []

    def get(self, url, **kw):
        self.urls.append(url)
        if not self.roteiro:
            return RespostaFalsa(200, html_com_ads([], 0))
        item = self.roteiro.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class OlxFalsa:
    """A fonte OLX de verdade, com sessão e relógio falsos."""

    FONTE = "olx"

    def __init__(self, roteiro):
        self.sessao, self.relogio = SessaoRoteirizada(roteiro), Relogio()

    def abrir(self, busca, limites=None, *, teto=None):
        return olx.abrir(
            busca, limites, teto=teto, sessao=self.sessao, dormir=self.relogio.dormir, relogio=self.relogio
        )

    def buscar(self, busca, limites=None):
        raise AssertionError("o servidor usa abrir")

    def buscar_paginas(self, busca, limites=None):
        raise AssertionError("o servidor usa abrir")


def servidor(*roteiro, **kw):
    fonte = OlxFalsa(roteiro)
    app = server.criar_app(fonte, ttl=600.0, estado_padrao="mg", limites=limites(**kw))
    return TestClient(app), fonte


def boa(inicio, n=3, total=9):
    """Uma página boa da OLX com `n` anúncios a partir do id `inicio`."""
    return RespostaFalsa(200, html_com_ads([anuncio_cru(str(i)) for i in range(inicio, inicio + n)], total))


def vazia(total=9):
    return RespostaFalsa(200, html_com_ads([], total))


def next_push(texto):
    """Página com um pedaço de payload do Next, cru, para montar JSON fora do formato."""
    return RespostaFalsa(200, "<html><script>self.__next_f.push(%s)</script></html>" % json.dumps([1, texto]))


# Cada caso é o que a OLX devolve no lugar da página: (nome, o que vem, trecho do detalhe técnico)
FALHAS = [
    ("403", RespostaFalsa(403, ""), "HTTP 403"),
    ("429", RespostaFalsa(429, ""), "HTTP 429"),
    ("500", RespostaFalsa(500, ""), "HTTP 500"),
    ("captcha", RespostaFalsa(200, "<html><body><h1>Confirme que você não é um robô</h1></body></html>"), "sem o array"),
    ("pagina_em_branco", RespostaFalsa(200, ""), "sem o array"),
    ("json_cortado", next_push('{"ads":[{"listId": 5, "subject": "Gol'), "sem o array"),
    ("ads_virou_objeto", next_push('{"ads":{"a":1}}'), "sem o array"),
    ("ads_so_texto", next_push('{"ads":["x","y"]}'), "sem o array"),
    ("ads_sem_listId", next_push('{"ads":[{"subject":"Gol"}]}'), "sem o array"),
    ("timeout", TimeoutError("demorou"), "TimeoutError"),
    ("rede_caiu", ConnectionResetError("caiu"), "ConnectionResetError"),
]
IDS = [f[0] for f in FALHAS]


def pagina(c, n, **extra):
    return c.get("/buscar/pagina", params={"texto": "gol", "pagina": n, **extra}).json()


def textos_para_a_pessoa(j):
    """Tudo que a tela mostra sem o modo dev."""
    return [j["informacao"]] + [a["mensagem"] for a in j["avisos"]]


def sem_cara_de_robo(texto):
    assert not re.search(r"[-:;–—]", texto), texto
    for palavra in ("http", "captcha", "payload", "json", "timeout", "bloque", "403", "429", "erro 5", "listid"):
        assert palavra not in texto.lower(), (palavra, texto)


# --- Falha no meio do "Ver mais" ---------------------------------------------


@pytest.mark.parametrize("falha", [f[1] for f in FALHAS], ids=IDS)
def test_falha_na_pagina_2_avisa_guarda_a_1_e_deixa_tentar_de_novo(falha):
    c, fonte = servidor(boa(1), *[falha] * (REPETICOES + 1))
    assert pagina(c, 1)["falhou"] is False
    j = pagina(c, 2)
    assert j["falhou"] is True and j["anuncios"] == []
    assert j["entregues"] == 3 and j["coletados"] == 3  # a página 1 continua valendo
    assert j["tem_mais"] is True and j["proxima_pagina"] == 2 and j["motivo_parada"] is None
    assert j["informacao"] == server.MSG_MAIS_FALHOU
    assert [(a["codigo"], a["mensagem"]) for a in j["avisos"]] == [("fonte_parcial", server.MSG_MAIS_FALHOU)]
    assert len(fonte.sessao.urls) == 1 + 1 + REPETICOES  # a OLX recebeu a página 1 e depois repetiu a 2


@pytest.mark.parametrize("falha,trecho", [(f[1], f[2]) for f in FALHAS], ids=IDS)
def test_detalhe_tecnico_so_com_dev_e_diz_o_que_aconteceu(falha, trecho):
    c, _ = servidor(boa(1), *[falha] * (REPETICOES + 1))
    pagina(c, 1)
    comum = pagina(c, 2)
    assert "detalhe_tecnico" not in comum["avisos"][0]
    c2, _ = servidor(boa(1), *[falha] * (REPETICOES + 1))
    pagina(c2, 1)
    dev = pagina(c2, 2, dev=1)["avisos"][0]["detalhe_tecnico"]
    assert trecho in dev and "página 2" in dev and "3 anúncios" in dev


@pytest.mark.parametrize("falha", [f[1] for f in FALHAS], ids=IDS)
def test_o_texto_da_falha_esta_no_tom_do_garimpo(falha):
    c, _ = servidor(boa(1), *[falha] * (REPETICOES + 1))
    pagina(c, 1)
    for texto in textos_para_a_pessoa(pagina(c, 2)):
        sem_cara_de_robo(texto)


@pytest.mark.parametrize("falha", [f[1] for f in FALHAS], ids=IDS)
def test_depois_da_falha_a_mesma_pagina_volta_quando_a_olx_melhora(falha):
    c, fonte = servidor(boa(1), *[falha] * (REPETICOES + 1), boa(4), boa(7))
    pagina(c, 1)
    assert pagina(c, 2)["falhou"] is True
    certa = pagina(c, 2)
    assert certa["falhou"] is False and certa["entregues"] == 6 and certa["proxima_pagina"] == 3
    ids = [a["external_id"] for a in certa["anuncios"]]
    assert ids == ["4", "5", "6"]
    assert "o=2" in fonte.sessao.urls[-1]  # tentou a página 2 outra vez, não a 3
    de_cache = pagina(c, 1)
    assert de_cache["do_cache"] is True and len(fonte.sessao.urls) == 1 + (REPETICOES + 1) + 1


def test_ver_mais_repete_uma_vez_esperando_de_5_a_10_segundos():
    c, fonte = servidor(boa(1), *[RespostaFalsa(403, "")] * 2, backoff_base_segundos=20.0)
    pagina(c, 1)
    pagina(c, 2)
    esperas = fonte.relogio.esperas[1:]  # a 1ª é a pausa entre as páginas
    assert len(esperas) == REPETICOES and 5 <= esperas[0] <= 10
    assert len(fonte.sessao.urls) == 3  # página 1, página 2 e uma repetição


def test_pagina_1_e_stream_continuam_com_as_duas_repeticoes_e_a_espera_crescente():
    c, fonte = servidor(*[RespostaFalsa(403, "")] * 3, backoff_base_segundos=20.0)
    pagina(c, 1)
    esperas = fonte.relogio.esperas
    assert len(esperas) == TENTATIVAS and 20 <= esperas[0] <= 30 and 40 <= esperas[1] <= 60
    c2, fonte2 = servidor(boa(1), *[RespostaFalsa(403, "")] * 3, backoff_base_segundos=20.0)
    c2.get("/buscar/stream", params={"texto": "gol"})
    assert len(fonte2.sessao.urls) == 1 + 1 + TENTATIVAS
    assert 20 <= fonte2.relogio.esperas[1] <= 30 and 40 <= fonte2.relogio.esperas[2] <= 60


def test_sem_tempo_pra_tentar_de_novo_falha_na_hora_em_vez_de_passar_do_limite():
    c, fonte = servidor(boa(1), *[RespostaFalsa(403, "")] * 2, tempo_max_segundos=3.0)
    pagina(c, 1)
    j = pagina(c, 2, dev=1)
    assert j["falhou"] is True and "sem tempo" in j["avisos"][0]["detalhe_tecnico"]
    assert len(fonte.sessao.urls) == 2  # não repetiu


def test_sem_espera_de_verdade_nos_testes():
    """Quem dorme é o relógio falso: o teste todo de uma falha com 40 s de espera roda em menos de 1 s."""
    import time
    c, fonte = servidor(boa(1), *[RespostaFalsa(403, "")] * 3, backoff_base_segundos=60.0)
    inicio = time.monotonic()
    pagina(c, 1)
    c.get("/buscar", params={"texto": "gol"})
    assert time.monotonic() - inicio < 1.0 and sum(fonte.relogio.esperas) > 5


# --- Falha logo na primeira página -------------------------------------------


@pytest.mark.parametrize("falha", [f[1] for f in FALHAS], ids=IDS)
def test_falha_na_primeira_pagina_diz_que_nao_achou_e_nao_fica_no_cache(falha):
    c, fonte = servidor(*[falha] * (TENTATIVAS + 1), boa(1, total=3))
    j = pagina(c, 1)
    assert j["falhou"] is True and j["anuncios"] == [] and j["entregues"] == 0
    assert j["tem_mais"] is True and j["proxima_pagina"] == 1
    assert j["informacao"] == server.MSG_ERRO
    assert [a["mensagem"] for a in j["avisos"]] == [server.MSG_ERRO]
    for texto in textos_para_a_pessoa(j):
        sem_cara_de_robo(texto)
    ok = pagina(c, 1)  # a busca não ficou presa na falha
    assert ok["falhou"] is False and ok["entregues"] == 3 and ok["do_cache"] is False


# --- /buscar e /buscar/stream ------------------------------------------------


@pytest.mark.parametrize("falha", [f[1] for f in FALHAS], ids=IDS)
def test_buscar_com_falha_no_meio_entrega_so_o_que_leu_e_diz_que_pode_faltar(falha):
    c, _ = servidor(boa(1), *[falha] * (TENTATIVAS + 1))
    j = c.get("/buscar", params={"texto": "gol"}).json()
    assert j["motivo_parada"] == "falha_fonte" and j["paginas_lidas"] == 1
    assert [a["external_id"] for a in j["anuncios"]] == ["1", "2", "3"]
    assert j["funil"]["total_na_fonte"] == 9  # o total que a OLX falou fica visível: 3 de 9, nunca "tudo"
    assert [(a["codigo"], a["mensagem"]) for a in j["avisos"]] == [
        ("fonte_parcial", "A OLX não respondeu direito no meio da busca, então a lista pode estar incompleta.")
    ]
    sem_cara_de_robo(j["avisos"][0]["mensagem"])


@pytest.mark.parametrize("falha", [f[1] for f in FALHAS], ids=IDS)
def test_buscar_sem_nenhuma_pagina_diz_que_a_olx_nao_respondeu(falha):
    c, _ = servidor(*[falha] * (TENTATIVAS + 1))
    j = c.get("/buscar", params={"texto": "gol"}).json()
    assert j["motivo_parada"] == "falha_fonte" and j["anuncios"] == [] and j["paginas_lidas"] == 0
    assert [(a["codigo"], a["mensagem"]) for a in j["avisos"]] == [
        ("fonte_parcial", "A OLX não respondeu a essa busca.")
    ]
    sem_cara_de_robo(j["avisos"][0]["mensagem"])


@pytest.mark.parametrize("falha", [f[1] for f in FALHAS], ids=IDS)
def test_stream_com_falha_manda_as_paginas_boas_e_um_fim_que_nao_finge_estar_completo(falha):
    c, _ = servidor(boa(1), *[falha] * (TENTATIVAS + 1))
    ev = eventos(c.get("/buscar/stream", params={"texto": "gol"}).text)
    assert [n for n, _ in ev] == ["pagina", "fim"]  # falha da OLX não vira evento "erro" nem derruba o stream
    fim = ev[1][1]
    assert fim["motivo_parada"] == "falha_fonte" and fim["paginas_lidas"] == 1
    assert fim["avisos"][0]["codigo"] == "fonte_parcial"


def test_a_busca_seguinte_continua_de_onde_parou_sem_ler_a_pagina_1_de_novo():
    c, fonte = servidor(boa(1), RespostaFalsa(403, ""), RespostaFalsa(403, ""), RespostaFalsa(403, ""), boa(4), boa(7))
    assert c.get("/buscar", params={"texto": "gol"}).json()["motivo_parada"] == "falha_fonte"
    j = c.get("/buscar", params={"texto": "gol"}).json()
    assert j["motivo_parada"] == "acabaram_paginas" and j["paginas_lidas"] == 3
    assert [a["external_id"] for a in j["anuncios"]] == [str(i) for i in range(1, 10)]
    assert [u for u in fonte.sessao.urls if "o=1" in u or "o=" not in u].__len__() == 1  # a página 1 foi uma vez só


# --- Página vazia no meio da busca -------------------------------------------


def test_pagina_vazia_no_meio_com_o_total_muito_maior_nao_passa_por_lista_completa():
    c, _ = servidor(boa(1), vazia(total=9), vazia(total=9))
    pagina(c, 1)
    j = pagina(c, 2)
    assert j["falhou"] is True and j["anuncios"] == [] and j["entregues"] == 3
    assert j["tem_mais"] is True and j["proxima_pagina"] == 2
    assert j["informacao"] == server.MSG_MAIS_FALHOU and "todos" not in j["informacao"]
    assert j["avisos"][0]["codigo"] == "fonte_parcial"


def test_vazia_de_novo_na_mesma_pagina_encerra_dizendo_que_a_olx_conta_mais_do_que_mostra():
    c, _ = servidor(boa(1), vazia(total=9), vazia(total=9))
    pagina(c, 1)
    pagina(c, 2)
    j = pagina(c, 2)
    assert j["falhou"] is False and j["tem_mais"] is False and j["proxima_pagina"] is None
    assert j["motivo_parada"] == "acabaram_paginas" and j["entregues"] == 3
    assert j["informacao"] == "Achei 3 carros. A OLX fala em 9, mas só mostra esses."
    assert "Esses são todos" not in j["informacao"]


def test_pagina_vazia_logo_na_primeira_com_total_alto_tambem_nao_vira_nenhum_carro():
    c, _ = servidor(vazia(total=1413), boa(1, total=3))
    j = pagina(c, 1)
    assert j["falhou"] is True and j["informacao"] == server.MSG_ERRO and j["entregues"] == 0
    assert "Não achei nenhum carro com esses filtros" not in j["informacao"]
    assert pagina(c, 1)["entregues"] == 3


def test_busca_que_nao_tem_nenhum_carro_continua_sendo_vazia_de_verdade():
    c, _ = servidor(vazia(total=0))
    j = pagina(c, 1)
    assert j["falhou"] is False and j["tem_mais"] is False and j["entregues"] == 0 and j["avisos"] == []
    assert j["informacao"] == "Não achei nenhum carro com esses filtros. Que tal afrouxar algum?"


def test_fim_normal_da_olx_perto_do_total_nao_vira_falha():
    """A OLX lista uns 92% a 96% do que conta. Vazia depois disso é o fim, sem alarme."""
    c, _ = servidor(boa(1, n=3, total=10), boa(4, n=3, total=10), boa(7, n=2, total=10), vazia(total=10))
    pagina(c, 1)
    pagina(c, 2)
    j = pagina(c, 3)  # 8 de 10 e a última veio menor: acabou
    assert j["falhou"] is False and j["tem_mais"] is False and j["entregues"] == 8
    c2, _ = servidor(boa(1, n=3, total=10), boa(4, n=3, total=10), boa(7, n=3, total=10), vazia(total=10))
    for n in (1, 2, 3):
        pagina(c2, n)
    fim = pagina(c2, 4)  # 9 de 10, página vazia
    assert fim["falhou"] is False and fim["tem_mais"] is False and fim["entregues"] == 9
    assert fim["informacao"] == "Achei 9 carros. Esses são todos."


# --- Anúncio fora do formato no meio da página -------------------------------


def test_anuncio_quebrado_no_meio_da_pagina_nao_faz_os_vizinhos_sumirem_na_nova_tentativa():
    """Na página 1 a sessão inteira é jogada fora e recomeça. Da 2 em diante ela fica, então os
    anúncios bons que vieram antes do quebrado não podem ser dados como vistos."""
    quebrado = RespostaFalsa(200, html_com_ads(
        [anuncio_cru("4"), anuncio_cru("5"), anuncio_cru("6", images=5), anuncio_cru("7")], 7
    ))
    certa = RespostaFalsa(200, html_com_ads([anuncio_cru(str(i)) for i in (4, 5, 6, 7)], 7))
    c, _ = servidor(boa(1), quebrado, certa)
    pagina(c, 1)
    ruim = pagina(c, 2, dev=1)
    assert ruim["falhou"] is True and ruim["anuncios"] == [] and ruim["entregues"] == 3
    assert "TypeError" in ruim["avisos"][0]["detalhe_tecnico"]
    j = pagina(c, 2)
    assert j["falhou"] is False
    assert [a["external_id"] for a in j["anuncios"]] == ["4", "5", "6", "7"]
    assert j["entregues"] == 7 and j["informacao"] == "Achei 7 carros. Esses são todos."


# --- Toda mensagem que o servidor pode mandar --------------------------------


def test_todo_aviso_do_servidor_esta_no_tom():
    for texto in (server.MSG_ERRO, server.MSG_MAIS_FALHOU, server.MSG_PEDIDO, server.MSG_REGIAO, server.MSG_ZONA, server.MSG_ZONA_SEM_REGIAO):
        assert not re.search(r"[-:;–—]", texto), texto
