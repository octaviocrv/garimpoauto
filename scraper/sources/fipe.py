"""Contrato da fonte FIPE e cliente da fipe.online."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import threading
import time
from typing import Callable, Optional, Protocol

import httpx


class LimiteFipeAtingido(Exception):
    """O orçamento local acabou antes da próxima chamada."""


class FonteFipeIndisponivel(Exception):
    """A fonte não respondeu depois das poucas tentativas permitidas."""


@dataclass(frozen=True)
class ReferenciaFonte:
    codigo: str
    mes: str


@dataclass(frozen=True)
class OpcaoFonte:
    codigo: str
    nome: str


@dataclass(frozen=True)
class AnoFonte:
    codigo: str
    nome: str
    ano_modelo: Optional[int]
    combustivel_codigo: Optional[str]
    combustivel: Optional[str]


@dataclass(frozen=True)
class PrecoFonte:
    codigo_fipe: str
    preco: Decimal
    mes_referencia: str
    marca: str
    modelo: str
    ano_modelo: int
    combustivel: str


class FonteFipe(Protocol):
    def referencias(self) -> list[ReferenciaFonte]: ...
    def marcas(self, referencia: str) -> list[OpcaoFonte]: ...
    def modelos(self, referencia: str, marca: str) -> list[OpcaoFonte]: ...
    def anos(self, referencia: str, marca: str, modelo: str) -> list[AnoFonte]: ...
    def preco(self, referencia: str, marca: str, modelo: str, ano: str) -> PrecoFonte: ...


def _preco_brasileiro(valor: str) -> Decimal:
    limpo = valor.replace("R$", "").replace(".", "").replace(",", ".").strip()
    return Decimal(limpo)


def _ano(item: dict) -> AnoFonte:
    codigo = str(item["code"])
    nome = str(item["name"])
    partes_codigo = codigo.rsplit("-", 1)
    partes_nome = nome.split(" ", 1)
    ano_modelo = int(partes_codigo[0]) if partes_codigo[0].isdigit() else None
    return AnoFonte(
        codigo=codigo,
        nome=nome,
        ano_modelo=ano_modelo,
        combustivel_codigo=partes_codigo[1] if len(partes_codigo) == 2 else None,
        combustivel=partes_nome[1].strip() if len(partes_nome) == 2 else None,
    )


class FipeOnline:
    BASE_URL = "https://fipe.parallelum.com.br/api/v2"

    def __init__(
        self, *, token: Optional[str] = None, timeout: float = 10.0, repeticoes: int = 1,
        backoff: float = 1.0, pausa: float = 0.2, reservar: Callable[[], bool],
        cliente: Optional[httpx.Client] = None, dormir: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        headers = {"X-Subscription-Token": token} if token else {}
        self.cliente = cliente or httpx.Client(base_url=self.BASE_URL, timeout=timeout, headers=headers)
        self.repeticoes, self.backoff, self.pausa = repeticoes, backoff, pausa
        self.reservar, self.dormir, self.monotonic = reservar, dormir, monotonic
        self._trava_pausa = threading.Lock()
        self._ultima = 0.0

    def _esperar(self) -> None:
        with self._trava_pausa:
            falta = self.pausa - (self.monotonic() - self._ultima)
            if falta > 0:
                self.dormir(falta)
            self._ultima = self.monotonic()

    def _get(self, caminho: str, referencia: Optional[str] = None):
        erro: Optional[BaseException] = None
        for tentativa in range(self.repeticoes + 1):
            self._esperar()
            if not self.reservar():
                raise LimiteFipeAtingido()
            try:
                resposta = self.cliente.get(caminho, params={"reference": referencia} if referencia else None)
                if resposta.status_code == 429:
                    erro = FonteFipeIndisponivel("A fonte FIPE limitou as chamadas")
                else:
                    resposta.raise_for_status()
                    return resposta.json()
            except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as exc:
                erro = exc
            if tentativa < self.repeticoes:
                self.dormir(self.backoff * (2 ** tentativa))
        raise FonteFipeIndisponivel("A fonte FIPE não respondeu") from erro

    def referencias(self) -> list[ReferenciaFonte]:
        return [ReferenciaFonte(str(x["code"]), str(x["month"])) for x in self._get("/references")]

    def marcas(self, referencia: str) -> list[OpcaoFonte]:
        return [OpcaoFonte(str(x["code"]), str(x["name"])) for x in self._get("/cars/brands", referencia)]

    def modelos(self, referencia: str, marca: str) -> list[OpcaoFonte]:
        caminho = f"/cars/brands/{marca}/models"
        return [OpcaoFonte(str(x["code"]), str(x["name"])) for x in self._get(caminho, referencia)]

    def anos(self, referencia: str, marca: str, modelo: str) -> list[AnoFonte]:
        caminho = f"/cars/brands/{marca}/models/{modelo}/years"
        return [_ano(x) for x in self._get(caminho, referencia)]

    def preco(self, referencia: str, marca: str, modelo: str, ano: str) -> PrecoFonte:
        caminho = f"/cars/brands/{marca}/models/{modelo}/years/{ano}"
        x = self._get(caminho, referencia)
        return PrecoFonte(
            codigo_fipe=str(x["codeFipe"]),
            preco=_preco_brasileiro(str(x["price"])),
            mes_referencia=str(x["referenceMonth"]),
            marca=str(x["brand"]),
            modelo=str(x["model"]),
            ano_modelo=int(x["modelYear"]),
            combustivel=str(x["fuel"]),
        )
