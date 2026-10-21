"""Molde comum das fontes (OLX hoje; Mercado Livre e WebMotors depois).

Toda fonte recebe a mesma entrada (Busca, mais os limites) e devolve o mesmo resultado
(ResultadoBusca). É um módulo ou objeto com o nome da fonte e uma função buscar, sem
classe base, fábrica ou registro.

Opcional: `detalhar(external_id, url, limites, *, repeticoes, espera_repeticao)` lê a página de um
anúncio e devolve um DetalheAnuncio (veja sources/olx.py). O servidor só oferece o detalhe para a
fonte que tem essa função.
"""

from __future__ import annotations

from typing import Iterator, Optional, Protocol, runtime_checkable

from config import LimitesBusca
from schemas import Busca, PaginaBusca, ResultadoBusca


@runtime_checkable
class Cursor(Protocol):
    """Uma busca que anda uma página por chamada. `esperar()` faz a pausa entre pedidos (a 1ª
    página não espera) e `proxima()` lê a página seguinte. Página com parou_por "bloqueio" não
    avança, então chamar de novo tenta a mesma. Depois de uma página com parou_por (que não seja
    bloqueio), `terminou` fica True."""

    terminou: bool

    def esperar(self, pausa: Optional[tuple[float, float]] = None) -> None: ...

    def proxima(
        self, repeticoes: Optional[int] = None, espera_repeticao: Optional[tuple[float, float]] = None,
    ) -> PaginaBusca: ...


@runtime_checkable
class Fonte(Protocol):
    FONTE: str  # nome curto, ex.: "olx"

    def buscar(self, busca: Busca, limites: Optional[LimitesBusca] = None) -> ResultadoBusca:
        """Busca e devolve tudo junto. Nunca levanta erro por falha da fonte no meio da
        coleta: devolve o que juntou com motivo_parada "falha_fonte" e um aviso."""
        ...

    def abrir(self, busca: Busca, limites: Optional[LimitesBusca] = None, *, teto: Optional[int] = None) -> Cursor:
        """Busca página por página sob demanda (é o que o servidor usa). `teto` é a última página
        que entrega. A 1ª sai sem pausa."""
        ...

    def buscar_paginas(self, busca: Busca, limites: Optional[LimitesBusca] = None) -> Iterator[PaginaBusca]:
        """Mesma busca, uma página por vez (já com filtro local e sem repetidos). A última
        página traz `parou_por` preenchido."""
        ...
