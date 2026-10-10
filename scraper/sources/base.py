"""Molde comum das fontes (OLX hoje; Mercado Livre e WebMotors depois).

Toda fonte recebe a mesma entrada (Busca, mais os limites) e devolve o mesmo resultado
(ResultadoBusca). É um módulo ou objeto com o nome da fonte e uma função buscar, sem
classe base, fábrica ou registro.
"""

from __future__ import annotations

from typing import Iterator, Optional, Protocol, runtime_checkable

from config import LimitesBusca
from schemas import Busca, PaginaBusca, ResultadoBusca


@runtime_checkable
class Fonte(Protocol):
    FONTE: str  # nome curto, ex.: "olx"

    def buscar(self, busca: Busca, limites: Optional[LimitesBusca] = None) -> ResultadoBusca:
        """Busca e devolve tudo junto. Nunca levanta erro por falha da fonte no meio da
        coleta: devolve o que juntou com motivo_parada "falha_fonte" e um aviso."""
        ...

    def buscar_paginas(self, busca: Busca, limites: Optional[LimitesBusca] = None) -> Iterator[PaginaBusca]:
        """Mesma busca, uma página por vez (já com filtro local e sem repetidos). A última
        página traz `parou_por` preenchido."""
        ...
