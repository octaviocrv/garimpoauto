"""Apoio dos testes que usam o banco. Eles rodam no banco de teste do container do Garimpo Auto
(docker-compose up -d banco, porta 3390) e são pulados se ele não estiver de pé. O banco de teste
é apagado e refeito a cada teste, e nunca é o garimpo_auto de verdade."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pymysql
import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import config  # noqa: E402,F401  (carrega o .env)
import os  # noqa: E402

from armazem import Armazem, banco_de_url  # noqa: E402

URL_TESTE = os.environ.get("GARIMPO_DATABASE_URL_TESTE")
TABELAS = ("busca_pagina", "busca_sessao", "busca_visto", "busca_execucao", "schema_migracoes")


class RelogioBanco:
    """Hora falsa do banco, em UTC. Anda só quando o teste manda."""

    def __init__(self) -> None:
        self.agora = datetime(2026, 10, 10, 12, 0, 0)

    def __call__(self) -> datetime:
        return self.agora

    def passar(self, **kw: float) -> None:
        self.agora += timedelta(**kw)


def zerar_banco_de_teste() -> None:
    if not URL_TESTE:
        pytest.skip("Falta GARIMPO_DATABASE_URL_TESTE no .env")
    dados = banco_de_url(URL_TESTE)
    assert dados["database"].endswith("_teste"), "os testes só mexem em banco que termina com _teste"
    try:
        con = pymysql.connect(**dados, connect_timeout=2)
    except pymysql.err.OperationalError:
        pytest.skip("Banco de teste fora do ar (docker-compose up -d banco)")
    with con, con.cursor() as cur:
        cur.execute("SET FOREIGN_KEY_CHECKS = 0")
        for t in TABELAS:
            cur.execute(f"DROP TABLE IF EXISTS {t}")
        cur.execute("SET FOREIGN_KEY_CHECKS = 1")


def novo_armazem(relogio: RelogioBanco) -> Armazem:
    return Armazem(URL_TESTE, agora=relogio, confere_segundos=0.05)
