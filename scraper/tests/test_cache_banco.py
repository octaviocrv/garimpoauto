"""Cache de busca no banco, de ponta a ponta: o servidor de verdade, o coletor da OLX de verdade, o
banco de teste de verdade, e só a OLX é falsa. Cada "servidor" é um app novo com a sua própria memória,
então reiniciar ou ter dois servidores é criar outro app no mesmo banco.

Rodar dentro de scraper/:  .venv/bin/python -m pytest tests -v
Precisa do banco de teste de pé (docker-compose up -d banco). Sem ele, estes testes são pulados.
"""

import logging
import sys
import time
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import server  # noqa: E402
from armazem import Armazem  # noqa: E402
from tests.apoio_banco import RelogioBanco, URL_TESTE, novo_armazem, zerar_banco_de_teste  # noqa: E402
from tests.test_armazem import epoch  # noqa: E402
from tests.test_bloqueio_simulado import OlxFalsa  # noqa: E402
from tests.test_olx import RespostaFalsa, anuncio_cru, html_com_ads, limites  # noqa: E402


@pytest.fixture
def relogio():
    return RelogioBanco()


@pytest.fixture(autouse=True)
def banco_limpo():
    zerar_banco_de_teste()


class Servidor:
    """Um servidor com memória própria, ligado ao banco de teste."""

    def __init__(self, relogio, *roteiro, armazem=None):
        self.fonte = OlxFalsa(roteiro)
        self.armazem = armazem or novo_armazem(relogio)
        self.app = server.criar_app(
            self.fonte, ttl=1200.0, estado_padrao="mg", limites=limites(), armazem=self.armazem
        )
        self.c = TestClient(self.app)

    def pagina(self, n, **extra):
        return self.c.get("/buscar/pagina", params={"texto": "gol", "pagina": n, **extra}).json()

    @property
    def pedidos(self):
        return len(self.fonte.sessao.urls)


def ad(i, relogio=None, minutos_atras=None, **extra):
    if minutos_atras is not None:
        extra.update(date=epoch(relogio.agora - timedelta(minutes=minutos_atras)), lastBumpAgeSecs="0")
    return anuncio_cru(str(i), **extra)


def pg(ads, total=9):
    return RespostaFalsa(200, html_com_ads(ads, total))


def lote(inicio, n=3, total=9):
    return pg([ad(i) for i in range(inicio, inicio + n)], total)


def ids(j):
    return [a["external_id"] for a in j["anuncios"]]


# --- Sobrevive a reinício e é compartilhado ---------------------------------------


def test_reiniciar_o_servidor_nao_perde_a_busca_e_continua_de_onde_parou(relogio):
    a = Servidor(relogio, lote(1), lote(4))
    p1, p2 = a.pagina(1), a.pagina(2)
    assert a.pedidos == 2
    # o servidor reinicia: memória nova, o mesmo banco. A OLX da 3ª página repete o último anúncio da 2ª.
    b = Servidor(relogio, pg([ad(6), ad(7), ad(8)], total=8))
    de_novo = b.pagina(2)
    assert b.pedidos == 0 and de_novo["do_cache"] is True
    assert ids(de_novo) == ids(p2) and de_novo["coletado_em"] == p2["coletado_em"] and de_novo["entregues"] == 6
    assert ids(b.pagina(1)) == ids(p1) and b.pedidos == 0
    p3 = b.pagina(3)
    assert b.pedidos == 1 and "o=3" in b.fonte.sessao.urls[0]
    assert ids(p3) == ["7", "8"] and p3["coletados"] == 8  # acumulado: o 6 repetido não contou duas vezes
    assert p3["entregues"] == 8 and p3["tem_mais"] is False and p3["do_cache"] is False


def test_o_que_e_guardado_no_banco_e_a_pagina_o_total_e_a_hora(relogio):
    a = Servidor(relogio, lote(1, total=30))
    j = a.pagina(1)
    with a.armazem._conectar() as con, con.cursor() as cur:
        cur.execute("SELECT s.total_ads, s.valida_ate, s.criada_em, p.numero, p.coletada_em FROM busca_sessao s JOIN busca_pagina p ON p.sessao_id = s.id")
        linhas = cur.fetchall()
    assert len(linhas) == 1 and linhas[0]["total_ads"] == 30 and linhas[0]["numero"] == 1
    assert linhas[0]["valida_ate"] - linhas[0]["criada_em"] == timedelta(minutes=20)
    assert j["total_na_fonte"] == 30


def test_dois_servidores_dividem_as_paginas_sem_ler_a_olx_duas_vezes(relogio):
    a, b = Servidor(relogio, lote(1), lote(7)), Servidor(relogio, lote(4))
    p1 = a.pagina(1)
    assert ids(b.pagina(1)) == ids(p1) and b.pedidos == 0  # veio do banco
    p2 = b.pagina(2)  # o servidor B lê a 2
    assert b.pedidos == 1
    de_a = a.pagina(2)  # o A já tinha a 1 na memória e pega a 2 do banco
    assert a.pedidos == 1 and de_a["do_cache"] is True and ids(de_a) == ids(p2)
    assert ids(a.pagina(3)) == ["7", "8", "9"] and a.pedidos == 2  # e continua dali, sem repetir a 2


def test_usuarios_diferentes_na_mesma_busca_dividem_o_cache(relogio):
    a = Servidor(relogio, lote(1), lote(4))
    a.pagina(1)
    b = Servidor(relogio)
    for _ in range(3):
        assert b.pagina(1)["do_cache"] is True
    assert b.pedidos == 0


def test_busca_diferente_nao_usa_o_cache_de_outra(relogio):
    a = Servidor(relogio, lote(1))
    a.pagina(1)
    b = Servidor(relogio, lote(100))
    j = b.c.get("/buscar/pagina", params={"texto": "civic", "pagina": 1}).json()
    assert b.pedidos == 1 and j["do_cache"] is False and ids(j) == ["100", "101", "102"]


def test_vale_20_minutos_depois_da_primeira_pagina(relogio):
    a = Servidor(relogio, lote(1))
    a.pagina(1)
    relogio.passar(minutes=19, seconds=50)
    assert Servidor(relogio).pagina(1)["do_cache"] is True
    relogio.passar(seconds=20)
    c = Servidor(relogio, lote(1))
    assert c.pagina(1)["do_cache"] is False and c.pedidos == 1  # venceu: lê da OLX de novo


def test_o_mesmo_servidor_tambem_respeita_o_vencimento_do_banco(relogio):
    a = Servidor(relogio, lote(1), lote(1))
    a.pagina(1)
    relogio.passar(minutes=21)
    assert a.pagina(1)["do_cache"] is False and a.pedidos == 2


def test_atualizar_troca_a_busca_para_todos(relogio):
    a, b = Servidor(relogio, lote(1)), Servidor(relogio, lote(50))
    assert ids(a.pagina(1)) == ["1", "2", "3"]
    novo = b.pagina(1, atualizar=1)
    assert ids(novo) == ["50", "51", "52"] and novo["do_cache"] is False
    de_a = a.pagina(1)
    assert ids(de_a) == ["50", "51", "52"] and de_a["do_cache"] is True and a.pedidos == 1


def test_falha_na_pagina_2_nao_vai_para_o_banco_e_o_outro_servidor_le_a_2_dali(relogio):
    a = Servidor(relogio, lote(1), *[RespostaFalsa(403, "")] * 2)
    a.pagina(1)
    assert a.pagina(2)["falhou"] is True
    b = Servidor(relogio, lote(4))
    j = b.pagina(2)
    assert j["falhou"] is False and ids(j) == ["4", "5", "6"] and "o=2" in b.fonte.sessao.urls[0] and b.pedidos == 1


def test_falha_logo_na_pagina_1_nao_deixa_sessao_nem_busca_anterior(relogio):
    a = Servidor(relogio, *[RespostaFalsa(403, "")] * 3)
    assert a.pagina(1)["falhou"] is True
    with a.armazem._conectar() as con, con.cursor() as cur:
        for tabela in ("busca_sessao", "busca_pagina", "busca_execucao", "busca_visto"):
            cur.execute(f"SELECT COUNT(*) AS n FROM {tabela}")
            assert cur.fetchone()["n"] == 0, tabela
    b = Servidor(relogio, lote(1))
    assert b.pagina(1)["primeira_busca"] is True


# --- Novo desde a última vez ----------------------------------------------------------


def test_novo_desde_a_ultima_vez_so_o_que_apareceu_depois(relogio):
    a = Servidor(
        relogio,
        pg([ad(1, relogio, 3000), ad(2, relogio, 3000), ad(3, relogio, 3000)], total=3),
    )
    primeira = a.pagina(1)
    assert primeira["primeira_busca"] is True and primeira["novos"] == 0
    assert [x["novo"] for x in primeira["anuncios"]] == [False, False, False]

    relogio.passar(minutes=25)  # a busca venceu, a próxima recomeça do zero
    b = Servidor(
        relogio,
        pg([
            ad(9, relogio, 5),      # anunciado há 5 min, depois da última busca: novo
            ad(1, relogio, 3000),   # já visto
            ad(7, relogio, 4000),   # nunca visto, mas mais velho que a última busca: estava no fundo da lista
            ad(2, relogio, 3000),
        ], total=4),
    )
    segunda = b.pagina(1)
    assert segunda["primeira_busca"] is False and segunda["novos"] == 1
    assert {x["external_id"]: x["novo"] for x in segunda["anuncios"]} == {"9": True, "1": False, "7": False, "2": False}
    # a mesma página lida de novo (cache) diz a mesma coisa, mesmo depois de reiniciar
    de_novo = Servidor(relogio).pagina(1)
    assert de_novo["do_cache"] is True and de_novo["novos"] == 1
    assert {x["external_id"]: x["novo"] for x in de_novo["anuncios"]} == {x["external_id"]: x["novo"] for x in segunda["anuncios"]}
    assert b.pedidos == 1


def test_novo_conta_so_o_que_ja_foi_entregue_nas_paginas_ate_aqui(relogio):
    a = Servidor(relogio, pg([ad(1, relogio, 3000)], total=2), pg([ad(2, relogio, 3000)], total=2))
    a.pagina(1), a.pagina(2)
    relogio.passar(minutes=25)
    b = Servidor(relogio, pg([ad(8, relogio, 2), ad(1, relogio, 3000)], total=4), pg([ad(9, relogio, 1), ad(2, relogio, 3000)], total=4))
    assert b.pagina(1)["novos"] == 1
    assert b.pagina(2)["novos"] == 2


def test_buscar_inteiro_e_o_stream_tambem_trazem_novos_e_primeira_busca(relogio):
    a = Servidor(relogio, pg([ad(1, relogio, 3000), ad(2, relogio, 3000)], total=2))
    j = a.c.get("/buscar", params={"texto": "gol"}).json()
    assert j["primeira_busca"] is True and j["novos"] == 0
    relogio.passar(minutes=25)
    b = Servidor(relogio, pg([ad(5, relogio, 1), ad(1, relogio, 3000)], total=2))
    j = b.c.get("/buscar", params={"texto": "gol"}).json()
    assert j["primeira_busca"] is False and j["novos"] == 1
    assert [x["novo"] for x in j["anuncios"]] == [True, False]
    relogio.passar(minutes=25)
    c = Servidor(relogio, pg([ad(6, relogio, 1), ad(5, relogio, 30)], total=2))
    ev = c.c.get("/buscar/stream", params={"texto": "gol"}).text
    assert '"novos": 1' in ev and '"primeira_busca": false' in ev


def test_o_novo_vem_sem_dado_de_anunciante_nem_item_cru(relogio):
    a = Servidor(relogio, pg([ad(1, relogio, 5, seller={"name": "Fulano"})], total=1))
    texto = a.c.get("/buscar/pagina", params={"texto": "gol"}).text.lower()
    assert "fulano" not in texto and '"raw"' not in texto and '"novo"' in texto


# --- Banco fora do ar -------------------------------------------------------------------


def test_sem_banco_configurado_a_busca_e_so_de_memoria_e_nao_sabe_dizer_o_que_e_novo():
    fonte = OlxFalsa([lote(1)])
    c = TestClient(server.criar_app(fonte, ttl=60.0, estado_padrao="mg", limites=limites()))
    j = c.get("/buscar/pagina", params={"texto": "gol"}).json()
    assert j["primeira_busca"] is None and j["novos"] == 0 and j["do_cache"] is False


def test_banco_fora_a_busca_funciona_sem_travar_e_o_log_diz_uma_vez(relogio, caplog):
    caplog.set_level(logging.INFO, logger="garimpo.banco")
    morto = Armazem("mysql://garimpo:x@127.0.0.1:1/garimpo_auto", agora=relogio, confere_segundos=60, timeout_segundos=0.5)
    a = Servidor(relogio, lote(1), lote(4), armazem=morto)
    inicio = time.monotonic()
    p1, p2 = a.pagina(1), a.pagina(2)
    outra = a.pagina(1)
    assert time.monotonic() - inicio < 2.0
    assert ids(p1) == ["1", "2", "3"] and ids(p2) == ["4", "5", "6"] and outra["do_cache"] is True
    assert p1["primeira_busca"] is None and p1["novos"] == 0
    assert len([r for r in caplog.records if "Banco fora do ar" in r.getMessage()]) == 1
    morto.fechar()


def test_banco_cai_no_meio_a_sessao_segue_na_memoria_e_a_proxima_busca_volta_ao_banco(relogio, caplog, monkeypatch):
    caplog.set_level(logging.INFO, logger="garimpo.banco")
    a = Servidor(relogio, lote(1), lote(4), lote(7))
    a.pagina(1)
    original = a.armazem._conectar
    monkeypatch.setattr(a.armazem, "_conectar", lambda **kw: (_ for _ in ()).throw(
        __import__("pymysql").err.OperationalError(2003, "caiu")))
    j = a.pagina(2)  # o banco caiu agora
    assert j["falhou"] is False and ids(j) == ["4", "5", "6"] and a.armazem.fora
    assert any("só na memória" in r.getMessage() for r in caplog.records)
    assert ids(a.pagina(3)) == ["7", "8", "9"] and a.pedidos == 3  # segue lendo
    monkeypatch.setattr(a.armazem, "_conectar", original)
    for _ in range(100):
        if not a.armazem.fora:
            break
        time.sleep(0.05)
    assert any("Banco voltou" in r.getMessage() for r in caplog.records)
    assert a.pagina(2)["do_cache"] is True  # a sessão de memória vale até vencer
    # outro servidor não vê as páginas 2 e 3 (nunca foram ao banco) e lê da 2 em diante sem perder nada
    b = Servidor(relogio, lote(4))
    assert ids(b.pagina(2)) == ["4", "5", "6"] and b.pedidos == 1


def test_ao_subir_o_servidor_aplica_as_migrations(relogio):
    a = Servidor(relogio)
    with TestClient(a.app) as c:  # roda o "startup"
        assert c.get("/saude").json() == {"status": "ok"}
    with a.armazem._conectar() as con, con.cursor() as cur:
        cur.execute("SELECT versao FROM schema_migracoes ORDER BY versao")
        assert [r["versao"] for r in cur.fetchall()] == ["001_cache_de_busca", "002_vistos"]


def test_ao_subir_sem_banco_o_servidor_sobe_do_mesmo_jeito(relogio, caplog):
    morto = Armazem("mysql://garimpo:x@127.0.0.1:1/garimpo_auto", agora=relogio, confere_segundos=60, timeout_segundos=0.5)
    a = Servidor(relogio, lote(1), armazem=morto)
    with TestClient(a.app) as c:
        assert c.get("/saude").json() == {"status": "ok"}
        assert c.get("/buscar/pagina", params={"texto": "gol"}).status_code == 200
    assert any("Subi sem o banco" in r.getMessage() for r in caplog.records)
    morto.fechar()
