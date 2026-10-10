"""Armazem: o banco do cache de busca e dos vistos, e o que acontece quando ele cai.

Rodar dentro de scraper/:  .venv/bin/python -m pytest tests -v
Precisa do banco de teste de pé (docker-compose up -d banco). Sem ele, os testes que o usam são pulados.
"""

import logging
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import armazem as modulo  # noqa: E402
from armazem import Armazem, BancoFora, hash_da_chave, pagina_de_json, pagina_para_json  # noqa: E402
from schemas import PaginaBusca, ReferenciaFipe  # noqa: E402
from sources import olx  # noqa: E402
from tests.apoio_banco import RelogioBanco, novo_armazem, zerar_banco_de_teste  # noqa: E402
from tests.test_olx import anuncio_cru  # noqa: E402

H = hash_da_chave("texto=gol|estado=mg|ordenar=recentes")


@pytest.fixture
def relogio():
    return RelogioBanco()


@pytest.fixture
def banco(relogio):
    zerar_banco_de_teste()
    a = novo_armazem(relogio)
    a.migrar()
    yield a
    a.fechar()


def epoch(dt: datetime) -> int:
    return int(dt.replace(tzinfo=timezone.utc).timestamp())


def anuncio(id_, quando=None, renovado=False):
    extra = {} if quando is None else {"date": epoch(quando), "lastBumpAgeSecs": "60" if renovado else "0"}
    if quando is None:
        extra = {"date": None}
    return olx.normalizar(anuncio_cru(str(id_), **extra))


def pagina(n, ids, total=10, parou=None):
    return PaginaBusca(
        fonte="olx", numero=n, anuncios=[anuncio(i) for i in ids], acumulado=n * len(ids), total_ads=total,
        parou_por=parou, coletados=len(ids), cortados_por_filtro={"km": 1}, na_origem=["estado"],
    )


def abrir_sessao(banco, usuario=""):
    return banco.criar_sessao(H, "texto=gol|estado=mg", '{"texto": "gol"}', usuario)


# --- Migrations ----------------------------------------------------------------


def test_migrations_rodam_na_ordem_e_so_uma_vez(relogio):
    zerar_banco_de_teste()
    a = novo_armazem(relogio)
    assert a.migrar() == ["001_cache_de_busca", "002_vistos", "003_fipe"]
    assert a.migrar() == []
    outro = novo_armazem(relogio)  # outro servidor subindo no mesmo banco
    assert outro.migrar() == []
    a.fechar(), outro.fechar()


def test_migration_fipe_cria_catalogo_casamentos_e_orcamento(relogio):
    zerar_banco_de_teste()
    a = novo_armazem(relogio)
    a.migrar()
    tabelas = a._usar(lambda cur: (
        cur.execute("SHOW TABLES LIKE 'fipe_%'"),
        {next(iter(linha.values())) for linha in cur.fetchall()},
    )[1])
    assert tabelas == {
        "fipe_ano", "fipe_cache_estado", "fipe_casamento", "fipe_marca",
        "fipe_modelo", "fipe_preco", "fipe_referencia", "fipe_requisicao_dia",
    }
    a.fechar()


def test_os_comandos_do_arquivo_sql_sao_separados_sem_os_comentarios():
    assert modulo._comandos("-- oi; tchau\nCREATE TABLE a (x INT); -- fim\nDROP TABLE a;\n") == [
        "CREATE TABLE a (x INT)", "DROP TABLE a",
    ]


# --- Página no banco -------------------------------------------------------------


def test_pagina_ida_e_volta_no_json_mantem_datas_novo_e_tira_o_item_cru():
    p = pagina(2, [1, 2])
    p.anuncios[0] = olx.normalizar(anuncio_cru("1", date=1791572438, lastBumpAgeSecs="0"))
    p.anuncios[0].novo = True
    p.anuncios[0].fipe = ReferenciaFipe("005384-8", 40000, 25, "outubro de 2026", "alta")
    p.anuncios[0].raw = {"segredo": 1}
    volta = pagina_de_json(pagina_para_json(p))
    assert volta.numero == 2 and volta.total_ads == 10 and volta.cortados_por_filtro == {"km": 1}
    assert [a.external_id for a in volta.anuncios] == ["1", "2"]
    assert volta.anuncios[0].novo is True and volta.anuncios[1].novo is False
    assert volta.anuncios[0].raw == {}
    assert volta.anuncios[0].fipe == p.anuncios[0].fipe
    assert volta.anuncios[0].publicado_em == p.anuncios[0].publicado_em and volta.anuncios[0].publicado_em.tzinfo


def test_guarda_e_carrega_paginas_total_hora_e_estado(banco, relogio):
    sessao_id, execucao, anterior = abrir_sessao(banco)
    assert anterior is None
    primeira = relogio.agora + timedelta(minutes=20)
    banco.salvar_pagina(sessao_id, pagina(1, [1, 2], total=7), 1.5, relogio.agora, {"numero": 1}, primeira)
    relogio.passar(seconds=30)
    banco.salvar_pagina(sessao_id, pagina(2, [3, 4], total=7), 2.5, relogio.agora, {"numero": 2}, primeira + timedelta(hours=9))
    g = banco.carregar_sessao(H)
    assert g.id == sessao_id and g.execucao_id == execucao and g.total_ads == 7
    assert g.estado_cursor == {"numero": 2}
    assert g.valida_ate == primeira  # só a 1ª página define a validade
    assert [(p.numero, t, q) for p, t, q in g.paginas] == [
        (1, 1.5, datetime(2026, 10, 10, 12, 0)), (2, 2.5, datetime(2026, 10, 10, 12, 0, 30)),
    ]
    assert [a.external_id for a in g.paginas[1][0].anuncios] == ["3", "4"]


def test_carregar_so_as_que_faltam_e_um_buraco_corta_a_lista(banco, relogio):
    sid, _, _ = abrir_sessao(banco)
    for n in (1, 2, 4):  # a 3 não foi gravada
        banco.salvar_pagina(sid, pagina(n, [n * 10]), 1.0, relogio.agora, {"numero": n}, relogio.agora)
    assert [p.numero for p, _, _ in banco.carregar_sessao(H).paginas] == [1, 2]
    assert [p.numero for p, _, _ in banco.carregar_sessao(H, depois_da_pagina=1).paginas] == [2]
    assert banco.carregar_sessao(H, depois_da_pagina=2).paginas == []


def test_sessao_vale_20_minutos_depois_da_primeira_pagina(banco, relogio):
    sid, _, _ = abrir_sessao(banco)
    assert banco.espiar(H, 1200)[0] == sid and banco.espiar(H, 1200)[1] is None  # lendo a 1ª ainda
    banco.salvar_pagina(sid, pagina(1, [1]), 1.0, relogio.agora, {}, relogio.agora + timedelta(seconds=1200))
    relogio.passar(seconds=1199)
    assert banco.espiar(H, 1200)[0] == sid
    relogio.passar(seconds=2)
    assert banco.espiar(H, 1200) is None


def test_sessao_sem_pagina_que_ficou_pendurada_nao_vale(banco, relogio):
    abrir_sessao(banco)
    relogio.passar(seconds=1201)
    assert banco.espiar(H, 1200) is None


def test_comecar_de_novo_troca_a_sessao_apaga_as_paginas_e_guarda_a_busca_anterior(banco, relogio):
    sid, e1, _ = abrir_sessao(banco)
    banco.salvar_pagina(sid, pagina(1, [1]), 1.0, relogio.agora, {}, relogio.agora + timedelta(minutes=20))
    inicio1 = relogio.agora
    relogio.passar(minutes=30)
    sid2, e2, anterior = abrir_sessao(banco)
    assert sid2 != sid and e2 > e1 and anterior == inicio1
    assert banco.carregar_sessao(H).paginas == []


def test_limpar_vencidas_apaga_sessao_e_paginas_e_guarda_o_que_a_busca_viu(banco, relogio):
    sid, _, _ = abrir_sessao(banco)
    ads = [anuncio(1), anuncio(2)]
    banco.marcar_vistos(H, 1, None, ads)
    banco.salvar_pagina(sid, pagina(1, [1, 2]), 1.0, relogio.agora, {}, relogio.agora + timedelta(minutes=20))
    assert banco.limpar_vencidas(1200) == 0
    relogio.passar(minutes=21)
    assert banco.limpar_vencidas(1200) == 1
    assert banco.carregar_sessao(H) is None
    assert banco._usar(lambda c: (c.execute("SELECT 1 FROM busca_pagina"), c.rowcount)[1]) == 0
    assert banco._usar(lambda c: (c.execute("SELECT 1 FROM busca_visto"), c.rowcount)[1]) == 2


def test_apagar_sessao_sem_anuncio_visto_desfaz_a_execucao(banco, relogio):
    sid, _, _ = abrir_sessao(banco)
    banco.apagar_sessao(sid)  # a 1ª página falhou
    _, _, anterior = abrir_sessao(banco)
    assert anterior is None  # a tentativa que falhou não conta como busca anterior


# --- Novo desde a última vez -------------------------------------------------------


def rodada(banco, relogio, anuncios, usuario=""):
    """Uma busca igual do zero que mostra `anuncios`. Devolve eles já marcados."""
    _, execucao, anterior = banco.criar_sessao(H, "texto=gol|estado=mg", "{}", usuario)
    banco.marcar_vistos(H, execucao, anterior, anuncios, usuario)
    return anuncios


def test_primeira_busca_ninguem_e_novo(banco, relogio):
    ads = rodada(banco, relogio, [anuncio(1, relogio.agora), anuncio(2, relogio.agora)])
    assert [a.novo for a in ads] == [False, False]


def test_na_segunda_so_o_que_nao_apareceu_e_foi_anunciado_depois_e_novo(banco, relogio):
    antigo = relogio.agora - timedelta(days=2)
    rodada(banco, relogio, [anuncio(1, antigo), anuncio(2, antigo)])
    relogio.passar(minutes=30)
    segunda = rodada(banco, relogio, [
        anuncio(9, relogio.agora - timedelta(minutes=5)),   # apareceu e é de depois da 1ª busca: novo
        anuncio(1, antigo),                                  # já tinha visto: não é novo
        anuncio(7, antigo),                                  # nunca visto, mas é antigo (estava no fundo da lista): não é novo
        anuncio(8, None),                                    # nunca visto e sem data: vale só o "não vi": novo
    ])
    assert {a.external_id: a.novo for a in segunda} == {"9": True, "1": False, "7": False, "8": True}


def test_anuncio_renovado_depois_da_ultima_busca_conta_como_novo(banco, relogio):
    antigo = relogio.agora - timedelta(days=9)
    rodada(banco, relogio, [anuncio(1, antigo)])
    relogio.passar(hours=1)
    renovado = anuncio(5, relogio.agora - timedelta(minutes=10), renovado=True)
    rodada(banco, relogio, [renovado])
    assert renovado.novo is True


def test_anuncio_visto_numa_busca_nao_volta_a_ser_novo_na_terceira(banco, relogio):
    rodada(banco, relogio, [anuncio(1, relogio.agora)])
    relogio.passar(hours=1)
    rodada(banco, relogio, [anuncio(2, relogio.agora - timedelta(minutes=1))])
    relogio.passar(hours=1)
    terceira = rodada(banco, relogio, [anuncio(2, relogio.agora - timedelta(hours=1, minutes=1)), anuncio(3, relogio.agora - timedelta(minutes=2))])
    assert [a.novo for a in terceira] == [False, True]


def test_buscas_diferentes_nao_misturam_o_que_viram(banco, relogio):
    rodada(banco, relogio, [anuncio(1, relogio.agora)])
    relogio.passar(hours=1)
    outra = hash_da_chave("texto=civic")
    _, e, ant = banco.criar_sessao(outra, "texto=civic", "{}")
    ads = [anuncio(1, relogio.agora - timedelta(minutes=1))]
    banco.marcar_vistos(outra, e, ant, ads)
    assert ant is None and ads[0].novo is False  # 1ª busca de "civic"


def test_o_visto_e_por_usuario_para_trocar_o_global_por_login_sem_refazer_o_banco(banco, relogio):
    """Hoje sempre vale o usuário vazio (global). Com um id de usuário, cada um tem o seu histórico."""
    rodada(banco, relogio, [anuncio(1, relogio.agora)], usuario="ana")
    relogio.passar(hours=1)
    bia = rodada(banco, relogio, [anuncio(2, relogio.agora - timedelta(minutes=1))], usuario="bia")
    assert bia[0].novo is False  # a Bia nunca buscou, 1ª busca dela
    relogio.passar(hours=1)
    ana = rodada(banco, relogio, [anuncio(2, relogio.agora - timedelta(minutes=70)), anuncio(1, relogio.agora)], usuario="ana")
    assert [a.novo for a in ana] == [True, False]  # a Ana nunca viu o 2


def test_muitos_anuncios_de_uma_vez(banco, relogio):
    rodada(banco, relogio, [anuncio(i, relogio.agora) for i in range(1, 451)])
    relogio.passar(hours=1)
    ads = rodada(banco, relogio, [anuncio(i, relogio.agora - timedelta(minutes=1)) for i in range(400, 501)])
    assert sum(a.novo for a in ads) == 50  # de 451 a 500


# --- Banco fora do ar --------------------------------------------------------------


def banco_fora(relogio):
    return Armazem("mysql://garimpo:x@127.0.0.1:1/garimpo_auto", agora=relogio, confere_segundos=0.05, timeout_segundos=0.5)


def test_banco_fora_levanta_na_hora_e_registra_uma_vez_no_log(relogio, caplog):
    a = banco_fora(relogio)
    caplog.set_level(logging.INFO, logger="garimpo.banco")
    with pytest.raises(BancoFora):
        a.espiar(H, 1200)
    assert a.fora
    inicio = time.monotonic()
    for _ in range(50):
        with pytest.raises(BancoFora):
            a.espiar(H, 1200)
    assert time.monotonic() - inicio < 0.5  # não tenta conectar a cada busca
    erros = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(erros) == 1 and "Banco fora do ar" in erros[0].getMessage() and "memória" in erros[0].getMessage()
    a.fechar()


def test_banco_volta_e_o_log_avisa(relogio, caplog, banco, monkeypatch):
    caplog.set_level(logging.INFO, logger="garimpo.banco")
    original = banco._conectar
    estado = {"caido": True, "tentativas": 0}

    def conectar(**kw):
        estado["tentativas"] += 1
        if estado["caido"]:
            raise modulo.pymysql.err.OperationalError(2003, "sem conexão")
        return original(**kw)

    monkeypatch.setattr(banco, "_conectar", conectar)
    with pytest.raises(BancoFora):
        banco.espiar(H, 1200)
    tentativas_ao_cair = estado["tentativas"]
    with pytest.raises(BancoFora):
        banco.espiar(H, 1200)
    assert estado["tentativas"] == tentativas_ao_cair  # nada de reconectar na busca
    estado["caido"] = False
    for _ in range(100):
        if not banco.fora:
            break
        time.sleep(0.05)
    assert not banco.fora
    assert banco.espiar(H, 1200) is None  # funciona de novo
    mensagens = [r.getMessage() for r in caplog.records]
    assert any("Banco fora do ar" in m for m in mensagens) and any("Banco voltou" in m for m in mensagens)


def test_url_ruim_e_recusada():
    for url in ("postgres://u:p@h/db", "mysql://u:p@h", "mysql:///db"):
        with pytest.raises(ValueError):
            modulo.banco_de_url(url)
    assert modulo.banco_de_url("mysql://garimpo:p%40ss@127.0.0.1:3390/garimpo_auto")["password"] == "p@ss"
