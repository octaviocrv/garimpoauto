"""Servidor: endpoints, SSE, cache e fila de coleta, com uma fonte falsa e sem internet.

Rodar dentro de scraper/:  .venv/bin/python -m pytest tests -v
"""

import json
import re
import sys
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import server  # noqa: E402
from config import LimitesBusca  # noqa: E402
from schemas import PaginaBusca  # noqa: E402
from sources import olx  # noqa: E402
from sources.base import Fonte  # noqa: E402
from tests.test_olx import anuncio_cru  # noqa: E402


class CursorFalso:
    """Uma busca da fonte falsa andando uma página por chamada."""

    def __init__(self, fonte, busca):
        self.fonte, self.busca = fonte, busca
        self.numero, self.terminou = 0, False

    def esperar(self):
        if self.numero > 0:
            self.fonte.esperas += 1

    def proxima(self):
        f = self.fonte
        n = self.numero + 1
        with f._lock:
            if n == 1:
                f.buscas.append(self.busca)
            f._ativas += 1
            f.max_simultaneas = max(f.max_simultaneas, f._ativas)
            f.paginas_pedidas.append((self.busca.texto, n))
        f.entrou.set()
        try:
            if f.segurar and n == 1:
                assert f.segurar.wait(5)
            if f.falha_apos is not None and n > f.falha_apos and f.falhas_restantes != 0:
                if f.falhas_restantes is not None:
                    f.falhas_restantes -= 1
                return PaginaBusca(
                    fonte=f.FONTE, numero=n, anuncios=[], acumulado=2 * (n - 1), total_ads=f.total,
                    parou_por=olx.BLOQUEIO, aviso=f"Parou por bloqueio na página {n}: HTTP 403.",
                )
            if f.excecao_apos is not None and n > f.excecao_apos:
                raise RuntimeError("resposta estranha")
            base = abs(hash(self.busca.texto)) % 100000 * 100
            ads = [olx.normalizar(anuncio_cru(base + n * 10 + k, seller={"name": "Fulano"})) for k in (1, 2)]
            ultima = n == f.paginas
            self.numero, self.terminou = n, ultima
            return PaginaBusca(
                fonte=f.FONTE, numero=n, anuncios=ads, acumulado=2 * n, total_ads=f.total,
                parou_por=olx.TOTAL_ADS if ultima else None, coletados=2,
            )
        finally:
            with f._lock:
                f._ativas -= 1


class FonteFalsa:
    """Segue a interface Fonte sem internet. Cada página tem 2 anúncios; os ids dependem do texto."""

    FONTE = "falsa"

    def __init__(self, paginas=3, falha_apos=None, excecao_apos=None, total=6, segurar=None, falhas=None):
        self.paginas, self.falha_apos, self.excecao_apos = paginas, falha_apos, excecao_apos
        self.total, self.segurar, self.falhas_restantes = total, segurar, falhas  # falhas None = sempre
        self.buscas = []  # uma entrada por busca aberta
        self.paginas_pedidas = []  # (texto, página) de cada leitura real
        self.esperas = 0
        self.entrou = threading.Event()
        self._lock = threading.Lock()
        self._ativas = 0
        self.max_simultaneas = 0

    def abrir(self, busca, limites=None, *, teto=None):
        return CursorFalso(self, busca)

    def buscar(self, busca, limites=None):
        raise AssertionError("o servidor usa abrir")

    def buscar_paginas(self, busca, limites=None):
        cursor = self.abrir(busca, limites)
        while not cursor.terminou:
            pag = cursor.proxima()
            yield pag
            if pag.parou_por:
                return


def cliente(fonte=None, **kw):
    fonte = fonte or FonteFalsa()
    kw.setdefault("ttl", 60.0)
    kw.setdefault("estado_padrao", "mg")
    kw.setdefault("limites", LimitesBusca())
    return TestClient(server.criar_app(fonte, **kw)), fonte


def eventos(texto):
    """Lê o corpo SSE e devolve [(evento, dados)], ignorando comentários."""
    saida = []
    for bloco in texto.strip().split("\n\n"):
        linhas = [l for l in bloco.splitlines() if not l.startswith(":")]
        if not linhas:
            continue
        nome = next(l[7:] for l in linhas if l.startswith("event: "))
        dados = json.loads(next(l[6:] for l in linhas if l.startswith("data: ")))
        saida.append((nome, dados))
    return saida


def test_a_fonte_falsa_segue_a_interface():
    assert isinstance(FonteFalsa(), Fonte)


def test_saude():
    c, _ = cliente()
    assert c.get("/saude").json() == {"status": "ok"}


def test_busca_normal_devolve_o_resultado_completo():
    c, _ = cliente()
    r = c.get("/buscar", params={"texto": "gol"})
    assert r.status_code == 200
    j = r.json()
    assert len(j["anuncios"]) == 6
    assert j["motivo_parada"] == "acabaram_paginas" and j["paginas_lidas"] == 3
    assert j["funil"]["coletados"] == 6 and j["funil"]["finais"] == 6
    assert j["fonte"] == "falsa"


def test_resposta_sem_dado_de_anunciante_nem_item_cru():
    c, _ = cliente()
    texto = c.get("/buscar", params={"texto": "gol"}).text.lower()
    assert '"raw"' not in texto and "fulano" not in texto and "seller" not in texto
    corpo = c.get("/buscar/stream", params={"texto": "gol"}).text.lower()
    assert '"raw"' not in corpo and "fulano" not in corpo


def test_stream_manda_uma_pagina_por_vez_e_o_fim():
    c, _ = cliente()
    r = c.get("/buscar/stream", params={"texto": "gol"})
    assert r.headers["content-type"].startswith("text/event-stream")
    ev = eventos(r.text)
    assert [n for n, _ in ev] == ["pagina", "pagina", "pagina", "fim"]
    assert [d["numero"] for n, d in ev if n == "pagina"] == [1, 2, 3]
    assert all(len(d["anuncios"]) == 2 for n, d in ev if n == "pagina")
    assert all(d["max_paginas"] == LimitesBusca().max_paginas for n, d in ev if n == "pagina")
    fim = ev[-1][1]
    assert "anuncios" not in fim
    assert fim["motivo_parada"] == "acabaram_paginas" and fim["funil"]["coletados"] == 6
    assert fim["paginas_lidas"] == 3


def test_cache_hit_nao_coleta_de_novo_e_o_stream_reenvia_as_paginas():
    c, fonte = cliente()
    primeira = c.get("/buscar", params={"texto": "Gol"}).json()
    segunda = c.get("/buscar", params={"texto": "  gol "}).json()  # mesma chave de busca
    assert len(fonte.buscas) == 1
    assert {**primeira, "do_cache": None} == {**segunda, "do_cache": None}  # igual, só muda de onde veio
    assert (primeira["do_cache"], segunda["do_cache"]) == (False, True)
    ev = eventos(c.get("/buscar/stream", params={"texto": "gol"}).text)
    assert [n for n, _ in ev] == ["pagina"] * 3 + ["fim"]
    assert len(fonte.buscas) == 1


def test_cache_vencido_coleta_de_novo():
    c, fonte = cliente(ttl=0.0)
    c.get("/buscar", params={"texto": "gol"})
    c.get("/buscar", params={"texto": "gol"})
    assert len(fonte.buscas) == 2


def test_filtros_diferentes_nao_dividem_cache():
    c, fonte = cliente()
    c.get("/buscar", params={"texto": "gol"})
    c.get("/buscar", params={"texto": "gol", "ano_min": 2010})
    assert len(fonte.buscas) == 2


def test_mesma_busca_simultanea_espera_a_coleta_em_andamento():
    liberar = threading.Event()
    c, fonte = cliente(FonteFalsa(segurar=liberar))
    respostas = []

    def pedir():
        respostas.append(c.get("/buscar", params={"texto": "onix"}).json())

    ts = [threading.Thread(target=pedir) for _ in range(2)]
    ts[0].start()
    assert fonte.entrou.wait(5)
    ts[1].start()
    time.sleep(0.3)  # a segunda já chegou e está esperando
    liberar.set()
    for t in ts:
        t.join(10)
    assert len(fonte.buscas) == 1
    assert len(respostas) == 2 and respostas[0] == respostas[1]


def test_busca_diferente_espera_na_fila_so_uma_coleta_por_vez():
    liberar = threading.Event()
    c, fonte = cliente(FonteFalsa(segurar=liberar))
    respostas = []
    ts = [
        threading.Thread(target=lambda t=t: respostas.append(c.get("/buscar", params={"texto": t}).status_code))
        for t in ("onix", "hilux")
    ]
    for t in ts:
        t.start()
    assert fonte.entrou.wait(5)
    time.sleep(0.3)
    assert len(fonte.buscas) == 1  # a segunda ainda não começou
    liberar.set()
    for t in ts:
        t.join(10)
    assert respostas == [200, 200] and len(fonte.buscas) == 2
    assert fonte.max_simultaneas == 1


@pytest.mark.parametrize(
    "params, esperado",
    [({}, "MG"), ({"estado": "todos"}, None), ({"estado": "TODOS"}, None), ({"estado": "sp"}, "SP"), ({"estado": ""}, "MG")],
)
def test_estado_padrao_todos_e_informado(params, esperado):
    c, fonte = cliente()
    assert c.get("/buscar", params={"texto": "gol", **params}).status_code == 200
    assert fonte.buscas[0].estado == esperado


def test_repassa_os_filtros_para_a_busca():
    c, fonte = cliente()
    c.get("/buscar", params={
        "texto": "hilux", "marca": "toyota", "modelo": "hilux", "ano_min": 2015, "ano_max": 2020,
        "preco_min": 100000, "preco_max": 200000, "km_max": 90000, "regiao": "goiania-e-regiao",
        "estado": "go", "cidade": "Goiânia",
    })
    b = fonte.buscas[0]
    assert (b.marca, b.modelo, b.ano_min, b.ano_max, b.preco_min, b.preco_max, b.km_max) == (
        "toyota", "hilux", 2015, 2020, 100000, 200000, 90000)
    assert (b.regiao, b.estado, b.cidade) == ("goiania-e-regiao", "GO", "Goiânia")


def test_detalhe_tecnico_so_com_dev():
    c, _ = cliente(limites=LimitesBusca(limiar_muitos_resultados=1))
    sem = c.get("/buscar", params={"texto": "gol"}).json()["avisos"]
    com = c.get("/buscar", params={"texto": "gol", "dev": 1}).json()["avisos"]
    assert [a["codigo"] for a in sem] == [a["codigo"] for a in com] == ["muitos_resultados"]
    assert "detalhe_tecnico" not in sem[0] and sem[0]["mensagem"]
    assert "limiar 1" in com[0]["detalhe_tecnico"]
    fim_sem = eventos(c.get("/buscar/stream", params={"texto": "gol"}).text)[-1][1]
    fim_com = eventos(c.get("/buscar/stream", params={"texto": "gol", "dev": 1}).text)[-1][1]
    assert "detalhe_tecnico" not in fim_sem["avisos"][0] and "detalhe_tecnico" in fim_com["avisos"][0]


def test_falha_da_fonte_no_meio_devolve_o_que_juntou_e_nao_fica_no_cache():
    c, fonte = cliente(FonteFalsa(paginas=4, falha_apos=1))
    r = c.get("/buscar", params={"texto": "gol"})
    assert r.status_code == 200
    j = r.json()
    assert len(j["anuncios"]) == 2 and j["motivo_parada"] == "falha_fonte"
    assert "fonte_parcial" in [a["codigo"] for a in j["avisos"]]
    c.get("/buscar", params={"texto": "gol"})
    assert len(fonte.buscas) == 2  # falha não é guardada


def test_excecao_da_fonte_no_meio_tambem_vira_falha_fonte():
    c, _ = cliente(FonteFalsa(paginas=4, excecao_apos=2))
    j = c.get("/buscar", params={"texto": "gol"}).json()
    assert j["motivo_parada"] == "falha_fonte" and len(j["anuncios"]) == 4


def test_stream_com_falha_manda_as_paginas_e_o_fim_com_o_motivo():
    c, _ = cliente(FonteFalsa(paginas=4, falha_apos=2))
    ev = eventos(c.get("/buscar/stream", params={"texto": "gol"}).text)
    nomes = [n for n, _ in ev]
    assert nomes[-1] == "fim" and nomes.count("pagina") >= 2
    assert ev[-1][1]["motivo_parada"] == "falha_fonte"
    assert "fonte_parcial" in [a["codigo"] for a in ev[-1][1]["avisos"]]


def test_stream_manda_evento_erro_humano_se_a_coleta_quebrar(monkeypatch):
    def quebra(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(server, "montar_resultado", quebra)
    c, _ = cliente()
    ev = eventos(c.get("/buscar/stream", params={"texto": "gol"}).text)
    assert ev[-1] == ("erro", {"mensagem": server.MSG_ERRO})
    assert c.get("/buscar", params={"texto": "gol"}).json() == {"erro": server.MSG_ERRO}


def test_pedido_invalido_da_erro_curto_e_humano():
    c, fonte = cliente()
    ruins = [{}, {"texto": "gol", "ano_min": 2020, "ano_max": 2010}, {"texto": "gol", "ano_min": "abc"},
             {"texto": "gol", "estado": "minas"}, {"texto": "gol", "estado": "todos", "regiao": "x-e-regiao"}]
    for params in ruins:
        r = c.get("/buscar", params=params)
        assert r.status_code == 422 and r.json() == {"erro": server.MSG_PEDIDO}, params
    assert fonte.buscas == []


def test_mensagens_de_erro_sem_traco_dois_pontos_ou_ponto_e_virgula():
    for msg in (server.MSG_ERRO, server.MSG_PEDIDO):
        assert not re.search(r"[-:;–—]", msg)


def test_cors_so_para_o_vite_local():
    c, _ = cliente()
    ok = c.get("/saude", headers={"Origin": "http://localhost:5173"})
    assert ok.headers["access-control-allow-origin"] == "http://localhost:5173"
    outro = c.get("/saude", headers={"Origin": "http://site-qualquer.com"})
    assert "access-control-allow-origin" not in outro.headers
    c2, _ = cliente(cors_origens=["http://meu-front.local"])
    assert c2.get("/saude", headers={"Origin": "http://meu-front.local"}).headers["access-control-allow-origin"] == "http://meu-front.local"


def test_repassa_cambio_combustivel_anunciante_km_minimo_versao_e_ordenacao():
    c, fonte = cliente()
    r = c.get("/buscar", params={
        "texto": "civic", "versao": "touring", "km_min": 20000, "cambio": "Automático",
        "combustivel": "flex", "anunciante": "profissional", "ordenar": "menor_preco",
    })
    assert r.status_code == 200
    b = fonte.buscas[0]
    assert (b.versao, b.km_min, b.cambio, b.combustivel, b.anunciante, b.ordenar) == (
        "touring", 20000, "automatico", "flex", "profissional", "menor_preco")


def test_ordenacao_padrao_e_mais_recentes_e_entra_na_chave_do_cache():
    c, fonte = cliente()
    c.get("/buscar", params={"texto": "gol"})
    c.get("/buscar", params={"texto": "gol", "ordenar": "relevancia"})
    c.get("/buscar", params={"texto": "gol", "ordenar": "recentes"})  # igual à primeira: cache
    assert [b.ordenar for b in fonte.buscas] == ["recentes", "relevancia"]


@pytest.mark.parametrize("params", [{"cambio": "voador"}, {"ordenar": "maior_preco"}, {"anunciante": "x"}, {"km_min": 9, "km_max": 1}])
def test_opcao_invalida_da_erro_curto_e_humano(params):
    c, _ = cliente()
    r = c.get("/buscar", params={"texto": "gol", **params})
    assert r.status_code == 422 and r.json() == {"erro": server.MSG_PEDIDO}


# --- hora da coleta, estado aplicado e ignorar o cache --------------------------


def test_resultado_informa_estado_aplicado_hora_da_coleta_e_ordenacao():
    c, _ = cliente()
    j = c.get("/buscar", params={"texto": "gol"}).json()
    assert j["estado_aplicado"] == "MG" and j["busca"]["estado"] == "MG"
    assert j["busca"]["ordenar"] == "recentes"
    assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", j["coletado_em"])
    assert c.get("/buscar", params={"texto": "gol", "estado": "todos"}).json()["estado_aplicado"] == "todos"
    assert c.get("/buscar", params={"texto": "gol", "estado": "sp"}).json()["estado_aplicado"] == "SP"


def test_do_cache_so_e_verdade_na_segunda_vez_e_a_hora_nao_muda():
    c, fonte = cliente()
    primeira = c.get("/buscar", params={"texto": "gol"}).json()
    segunda = c.get("/buscar", params={"texto": "gol"}).json()
    assert (primeira["do_cache"], segunda["do_cache"]) == (False, True)
    assert primeira["coletado_em"] == segunda["coletado_em"] and len(fonte.buscas) == 1


def test_atualizar_ignora_o_cache_e_coleta_de_novo_com_hora_nova():
    c, fonte = cliente()
    a = c.get("/buscar", params={"texto": "gol"}).json()
    b = c.get("/buscar", params={"texto": "gol", "atualizar": 1}).json()
    assert len(fonte.buscas) == 2 and b["do_cache"] is False and b["coletado_em"] >= a["coletado_em"]
    d = c.get("/buscar", params={"texto": "gol"}).json()  # a nova coleta virou o cache
    assert len(fonte.buscas) == 2 and d["do_cache"] is True and d["coletado_em"] == b["coletado_em"]


def test_atualizar_no_stream_tambem_coleta_de_novo_e_o_fim_traz_hora_e_estado():
    c, fonte = cliente()
    c.get("/buscar/stream", params={"texto": "gol"})
    ev = eventos(c.get("/buscar/stream", params={"texto": "gol", "atualizar": 1}).text)
    fim = ev[-1][1]
    assert len(fonte.buscas) == 2 and fim["do_cache"] is False
    assert fim["estado_aplicado"] == "MG" and "coletado_em" in fim
    de_novo = eventos(c.get("/buscar/stream", params={"texto": "gol"}).text)[-1][1]
    assert de_novo["do_cache"] is True and len(fonte.buscas) == 2


def test_atualizar_durante_coleta_em_andamento_divide_a_mesma_coleta():
    segurar = threading.Event()
    c, fonte = cliente(FonteFalsa(segurar=segurar))
    respostas = []
    t = threading.Thread(target=lambda: respostas.append(c.get("/buscar", params={"texto": "gol"}).status_code))
    t.start()
    assert fonte.entrou.wait(5)
    t2 = threading.Thread(target=lambda: respostas.append(c.get("/buscar", params={"texto": "gol", "atualizar": 1}).status_code))
    t2.start()
    time.sleep(0.2)
    segurar.set()
    t.join(10)
    t2.join(10)
    assert respostas == [200, 200] and len(fonte.buscas) == 1


def test_resposta_com_os_campos_novos_continua_sem_dado_de_anunciante():
    c, _ = cliente()
    texto = c.get("/buscar", params={"texto": "gol"}).text.lower()
    assert '"raw"' not in texto and "seller" not in texto and "fulano" not in texto
