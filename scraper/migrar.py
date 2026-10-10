"""Aplica as migrations do banco (migracoes/*.sql) que ainda não rodaram.

Uso:  .venv/bin/python migrar.py            (usa GARIMPO_DATABASE_URL do .env)
O servidor também migra sozinho na primeira conexão, então rodar à mão é opcional.
"""

import sys

import config
from armazem import Armazem, BancoFora

if __name__ == "__main__":
    if not config.DATABASE_URL:
        sys.exit("Falta GARIMPO_DATABASE_URL no .env (modelo em .env.example).")
    try:
        aplicadas = Armazem(config.DATABASE_URL).migrar()
    except BancoFora:
        sys.exit("Não consegui falar com o banco. Ele está de pé? (docker-compose up -d banco)")
    print("Migrações aplicadas:", ", ".join(aplicadas) if aplicadas else "nenhuma, já estava em dia.")
