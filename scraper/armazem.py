"""Banco do Garimpo Auto (MariaDB ou MySQL): o cache de busca compartilhado e o que cada busca já viu.

O servidor funciona sem o banco. Se ele cair, as operações levantam BancoFora na hora (sem esperar),
o servidor segue só com a memória, e uma thread confere de tempos em tempos se o banco voltou.
Tudo é gravado em UTC.

Migrations: arquivos migracoes/NNN_nome.sql, aplicados em ordem e uma vez só. Rodam sozinhos na primeira
conexão, ou à mão com  .venv/bin/python migrar.py
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Optional
from urllib.parse import unquote, urlparse

import pymysql

from schemas import Anuncio, PaginaBusca

log = logging.getLogger("garimpo.banco")
if not logging.getLogger().handlers and not log.handlers:  # fora do uvicorn, ainda assim aparece
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    log.addHandler(_h)
    log.setLevel(logging.INFO)

PASTA_MIGRACOES = Path(__file__).resolve().parent / "migracoes"
ERROS_DE_BANCO_FORA = (pymysql.err.OperationalError, pymysql.err.InterfaceError, OSError)


class BancoFora(Exception):
    """O banco não respondeu. Quem chama segue sem ele."""


def agora_utc() -> datetime:
    """Agora em UTC, sem fuso (é assim que o banco guarda)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hash_da_chave(chave: str) -> str:
    return hashlib.sha256(chave.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Página <-> JSON (sem o item cru da fonte, que o servidor nunca devolve)
# ---------------------------------------------------------------------------

_DATAS = ("publicado_em", "renovado_em")


def pagina_para_json(p: PaginaBusca) -> str:
    d = asdict(p)
    for a in d["anuncios"]:
        a["raw"] = {}
        for campo in _DATAS:
            if a[campo] is not None:
                a[campo] = a[campo].isoformat()
    return json.dumps(d, ensure_ascii=False)


def pagina_de_json(texto: str) -> PaginaBusca:
    d = json.loads(texto)
    anuncios = []
    for a in d.pop("anuncios"):
        for campo in _DATAS:
            if a[campo] is not None:
                a[campo] = datetime.fromisoformat(a[campo])
        anuncios.append(Anuncio(**a))
    return PaginaBusca(anuncios=anuncios, **d)


class SessaoGuardada:
    """Uma sessão de busca como está no banco."""

    def __init__(self, linha: dict[str, Any], paginas: list[tuple[PaginaBusca, float, datetime]]) -> None:
        self.id: int = linha["id"]
        self.chave: str = linha["chave"]
        self.valida_ate: Optional[datetime] = linha["valida_ate"]
        self.execucao_id: int = linha["execucao_id"]
        self.anterior_em: Optional[datetime] = linha["anterior_em"]
        self.total_ads: Optional[int] = linha["total_ads"]
        self.estado_cursor: Optional[dict[str, Any]] = (
            json.loads(linha["estado_cursor"]) if linha["estado_cursor"] else None
        )
        self.paginas = paginas  # (página, segundos que levou, hora da coleta em UTC)


def banco_de_url(url: str) -> dict[str, Any]:
    u = urlparse(url)
    if u.scheme not in ("mysql", "mariadb") or not u.hostname or not u.path.strip("/"):
        raise ValueError("GARIMPO_DATABASE_URL deve ser mysql://usuario:senha@host:porta/banco")
    return {
        "host": u.hostname, "port": u.port or 3306, "user": unquote(u.username or ""),
        "password": unquote(u.password or ""), "database": u.path.strip("/"),
    }


class Armazem:
    def __init__(
        self, url: str, *, confere_segundos: float = 30.0, agora: Callable[[], datetime] = agora_utc,
        timeout_segundos: float = 3.0,
    ) -> None:
        self._dados = banco_de_url(url)
        self.confere_segundos, self.agora, self.timeout = confere_segundos, agora, timeout_segundos
        self._fora = False
        self._migrado = False
        self._ultimas: list[str] = []
        self._trava = threading.Lock()
        self._parar = threading.Event()
        self._vigia: Optional[threading.Thread] = None

    # -- conexão e tolerância ------------------------------------------------

    @property
    def fora(self) -> bool:
        return self._fora

    def _conectar(self, **extra: Any) -> pymysql.connections.Connection:
        return pymysql.connect(
            **self._dados, charset="utf8mb4", connect_timeout=self.timeout, read_timeout=self.timeout * 2,
            write_timeout=self.timeout * 2, autocommit=False, cursorclass=pymysql.cursors.DictCursor, **extra,
        )

    def _caiu(self, erro: BaseException) -> None:
        with self._trava:
            if self._fora:
                return
            self._fora = True
            self._parar.clear()
            log.error(
                "Banco fora do ar (%s: %s). A busca segue só na memória e o servidor confere de novo a cada %.0f s.",
                type(erro).__name__, erro, self.confere_segundos,
            )
            self._vigia = threading.Thread(target=self._vigiar, name="garimpo-banco-vigia", daemon=True)
            self._vigia.start()

    def _vigiar(self) -> None:
        while not self._parar.wait(self.confere_segundos):
            try:
                with self._conectar() as con, con.cursor() as cur:
                    cur.execute("SELECT 1")
            except ERROS_DE_BANCO_FORA:
                continue
            with self._trava:
                self._fora = False
            log.warning("Banco voltou. A busca guarda no banco de novo.")
            return

    def fechar(self) -> None:
        """Para a thread que confere o banco (os testes usam)."""
        self._parar.set()
        if self._vigia is not None:
            self._vigia.join(timeout=2)

    def _usar(self, fn: Callable[[Any], Any]) -> Any:
        """Roda `fn(cursor)` numa transação. Banco fora: BancoFora na hora, sem tentar conectar."""
        if self._fora:
            raise BancoFora()
        try:
            con = self._conectar()
        except ERROS_DE_BANCO_FORA as e:
            self._caiu(e)
            raise BancoFora() from e
        try:
            if not self._migrado:
                self._migrar(con)
            with con.cursor() as cur:
                resultado = fn(cur)
            con.commit()
            return resultado
        except ERROS_DE_BANCO_FORA as e:
            self._caiu(e)
            raise BancoFora() from e
        except Exception:
            con.rollback()
            raise
        finally:
            try:
                con.close()
            except Exception:  # a conexão já caiu
                pass

    # -- migrations ----------------------------------------------------------

    def migrar(self) -> list[str]:
        """Aplica as migrations que faltam e devolve os nomes aplicados agora. Levanta BancoFora se não conectar."""
        self._ultimas = []
        self._usar(lambda cur: None)  # a primeira conexão já migra
        return list(self._ultimas)

    def _migrar(self, con: pymysql.connections.Connection) -> None:
        with con.cursor() as cur:
            cur.execute("SELECT GET_LOCK('garimpo_migracao', 20) AS ok")
            if not cur.fetchone()["ok"]:
                raise pymysql.err.OperationalError(0, "outra migração está rodando")
            try:
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS schema_migracoes ("
                    "versao VARCHAR(100) NOT NULL PRIMARY KEY, aplicada_em DATETIME(3) NOT NULL"
                    ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
                )
                cur.execute("SELECT versao FROM schema_migracoes")
                feitas = {r["versao"] for r in cur.fetchall()}
                novas: list[str] = []
                for arquivo in sorted(PASTA_MIGRACOES.glob("*.sql")):
                    if arquivo.stem in feitas:
                        continue
                    for comando in _comandos(arquivo.read_text(encoding="utf-8")):
                        cur.execute(comando)
                    cur.execute(
                        "INSERT INTO schema_migracoes (versao, aplicada_em) VALUES (%s, %s)", (arquivo.stem, self.agora())
                    )
                    con.commit()
                    novas.append(arquivo.stem)
                    log.info("Migração %s aplicada.", arquivo.stem)
                self._ultimas = novas
            finally:
                cur.execute("SELECT RELEASE_LOCK('garimpo_migracao')")
        self._migrado = True

    # -- sessões de busca ----------------------------------------------------

    def espiar(self, chave_hash: str, ttl_orfa: float) -> Optional[tuple[int, Optional[datetime]]]:
        """(id, valida_ate) da sessão guardada que ainda vale, ou None. Sessão sem página há mais de
        `ttl_orfa` segundos é de uma coleta que morreu no meio e não vale."""
        agora = self.agora()

        def f(cur: Any) -> Optional[tuple[int, Optional[datetime]]]:
            cur.execute("SELECT id, valida_ate, criada_em FROM busca_sessao WHERE chave_hash = %s", (chave_hash,))
            r = cur.fetchone()
            if r is None:
                return None
            if r["valida_ate"] is not None:
                return (r["id"], r["valida_ate"]) if r["valida_ate"] > agora else None
            return (r["id"], None) if r["criada_em"] > agora - timedelta(seconds=ttl_orfa) else None

        return self._usar(f)

    def carregar_sessao(self, chave_hash: str, depois_da_pagina: int = 0) -> Optional[SessaoGuardada]:
        """A sessão com as páginas de número maior que `depois_da_pagina`, em ordem. Só entram páginas
        em sequência: um buraco corta a lista ali."""

        def f(cur: Any) -> Optional[SessaoGuardada]:
            cur.execute("SELECT * FROM busca_sessao WHERE chave_hash = %s", (chave_hash,))
            linha = cur.fetchone()
            if linha is None:
                return None
            cur.execute(
                "SELECT numero, conteudo, tempo_segundos, coletada_em FROM busca_pagina "
                "WHERE sessao_id = %s AND numero > %s ORDER BY numero",
                (linha["id"], depois_da_pagina),
            )
            paginas, esperado = [], depois_da_pagina + 1
            for r in cur.fetchall():
                if r["numero"] != esperado:
                    break
                paginas.append((pagina_de_json(r["conteudo"]), r["tempo_segundos"], r["coletada_em"]))
                esperado += 1
            return SessaoGuardada(linha, paginas)

        return self._usar(f)

    def criar_sessao(self, chave_hash: str, chave: str, busca_json: str, usuario: str = "") -> tuple[int, int, Optional[datetime]]:
        """Abre uma sessão nova no lugar da que existir para a mesma busca e conta uma execução nova.
        Devolve (id da sessão, id da execução, início da execução anterior ou None se for a 1ª)."""
        agora = self.agora()

        def f(cur: Any) -> tuple[int, int, Optional[datetime]]:
            cur.execute("DELETE FROM busca_sessao WHERE chave_hash = %s", (chave_hash,))
            cur.execute(
                "SELECT iniciada_em FROM busca_execucao WHERE usuario = %s AND chave_hash = %s ORDER BY id DESC LIMIT 1",
                (usuario, chave_hash),
            )
            anterior = cur.fetchone()
            anterior_em = anterior["iniciada_em"] if anterior else None
            cur.execute(
                "INSERT INTO busca_execucao (usuario, chave_hash, iniciada_em) VALUES (%s, %s, %s)", (usuario, chave_hash, agora)
            )
            execucao = cur.lastrowid
            cur.execute(
                "INSERT INTO busca_sessao (chave_hash, chave, busca, execucao_id, anterior_em, criada_em) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (chave_hash, chave, busca_json, execucao, anterior_em, agora),
            )
            return cur.lastrowid, execucao, anterior_em

        return self._usar(f)

    def apagar_sessao(self, sessao_id: int) -> None:
        """Apaga a sessão e as páginas. A execução dela também, se nunca chegou a mostrar anúncio."""

        def f(cur: Any) -> None:
            cur.execute("DELETE FROM busca_sessao WHERE id = %s", (sessao_id,))
            cur.execute(_APAGAR_EXECUCOES_VAZIAS)

        self._usar(f)

    def salvar_pagina(
        self, sessao_id: int, pagina: PaginaBusca, tempo: float, quando: datetime, estado_cursor: dict[str, Any],
        valida_ate: Optional[datetime],
    ) -> None:
        """Grava a página e o ponto de onde a busca continua, juntos. `valida_ate` só vale na 1ª página."""
        conteudo = pagina_para_json(pagina)
        estado = json.dumps(estado_cursor, ensure_ascii=False)

        def f(cur: Any) -> None:
            cur.execute(
                "INSERT INTO busca_pagina (sessao_id, numero, conteudo, tempo_segundos, coletada_em) "
                "VALUES (%s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE conteudo = VALUES(conteudo), "
                "tempo_segundos = VALUES(tempo_segundos), coletada_em = VALUES(coletada_em)",
                (sessao_id, pagina.numero, conteudo, tempo, quando),
            )
            cur.execute(
                "UPDATE busca_sessao SET estado_cursor = %s, total_ads = %s, valida_ate = COALESCE(valida_ate, %s) WHERE id = %s",
                (estado, pagina.total_ads, valida_ate, sessao_id),
            )

        self._usar(f)

    def limpar_vencidas(self, ttl_orfa: float) -> int:
        """Apaga as sessões vencidas (e as páginas junto). Os vistos e as execuções que mostraram anúncio ficam."""
        agora = self.agora()

        def f(cur: Any) -> int:
            apagadas = cur.execute(
                "DELETE FROM busca_sessao WHERE (valida_ate IS NOT NULL AND valida_ate <= %s) "
                "OR (valida_ate IS NULL AND criada_em <= %s)",
                (agora, agora - timedelta(seconds=ttl_orfa)),
            )
            cur.execute(_APAGAR_EXECUCOES_VAZIAS)
            return apagadas

        return self._usar(f)

    # -- o que a busca já viu ------------------------------------------------

    def marcar_vistos(
        self, chave_hash: str, execucao_id: int, anterior_em: Optional[datetime], anuncios: Iterable[Anuncio],
        usuario: str = "",
    ) -> None:
        """Marca `novo` em cada anúncio e guarda que a busca viu todos.

        Novo é: existe uma busca igual anterior, o anúncio não apareceu em nenhuma busca anterior e
        ele foi anunciado (ou renovado) depois do início daquela busca. Sem data do anúncio vale só o
        "não apareceu antes". Na 1ª busca ninguém é novo, não há com o que comparar."""
        anuncios = list(anuncios)
        if not anuncios:
            return
        agora = self.agora()

        def f(cur: Any) -> list[bool]:
            ids = [(a.source, a.external_id) for a in anuncios]
            conhecidos: dict[tuple[str, str], int] = {}
            for i in range(0, len(ids), 200):
                lote = ids[i : i + 200]
                cur.execute(
                    "SELECT fonte, external_id, execucao_id FROM busca_visto WHERE usuario = %s AND chave_hash = %s AND ("
                    + " OR ".join(["(fonte = %s AND external_id = %s)"] * len(lote)) + ")",
                    [usuario, chave_hash] + [x for par in lote for x in par],
                )
                for r in cur.fetchall():
                    conhecidos[(r["fonte"], r["external_id"])] = r["execucao_id"]
            cur.executemany(
                "INSERT IGNORE INTO busca_visto (usuario, chave_hash, fonte, external_id, execucao_id, visto_em) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                [(usuario, chave_hash, fonte, id_, execucao_id, agora) for fonte, id_ in ids],
            )
            return [conhecidos.get(par, execucao_id) == execucao_id for par in ids]  # nunca vistos antes desta execução

        primeiros = self._usar(f)
        for a, primeiro in zip(anuncios, primeiros):
            data = a.anunciado_em
            if data is not None and data.tzinfo is not None:
                data = data.astimezone(timezone.utc).replace(tzinfo=None)
            a.novo = bool(
                anterior_em is not None and primeiro and (data is None or data > anterior_em)
            )


# Execução que não tem sessão nem anúncio visto não conta como "busca anterior".
_APAGAR_EXECUCOES_VAZIAS = (
    "DELETE FROM busca_execucao WHERE NOT EXISTS (SELECT 1 FROM busca_visto v WHERE v.execucao_id = busca_execucao.id) "
    "AND NOT EXISTS (SELECT 1 FROM busca_sessao s WHERE s.execucao_id = busca_execucao.id)"
)


def _comandos(sql: str) -> list[str]:
    """Separa um arquivo de migration em comandos (um por ponto e vírgula no fim da linha)."""
    sem_comentarios = "\n".join(l.split("--")[0] for l in sql.splitlines())
    return [c.strip() for c in sem_comentarios.split(";") if c.strip()]
