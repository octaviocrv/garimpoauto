"""Configuração fora do coletor. Os coletores (sources/) não têm número de limite nem padrão
de estado escritos dentro deles: estado vazio na busca significa Brasil todo, e os limites
vêm de LimitesBusca.

Cada limite tem um valor inicial, que uma variável de ambiente sobrescreve, e que o parâmetro
da busca sobrescreve por cima: LimitesBusca(max_paginas=3) usa 3 páginas e o resto do ambiente.
"""

import os
from typing import Callable

from pydantic import BaseModel, Field, model_validator

# Padrão de estado só para o server.py usar. O coletor nunca lê isto.
ESTADO_PADRAO = os.environ.get("GARIMPO_ESTADO_PADRAO", "mg")


def _do_ambiente(nome: str, padrao, converter: Callable):
    bruto = os.environ.get(nome)
    if bruto is None or not bruto.strip():
        return padrao
    try:
        return converter(bruto.strip())
    except ValueError as e:
        raise ValueError(f"{nome}={bruto!r} é inválida: {e}") from e


def _par(texto: str) -> tuple[float, float]:
    menor, maior = (float(x) for x in texto.split(","))
    return menor, maior


def _env_int(nome: str, padrao: int) -> Callable[[], int]:
    return lambda: _do_ambiente(nome, padrao, int)


def _env_float(nome: str, padrao: float) -> Callable[[], float]:
    return lambda: _do_ambiente(nome, padrao, float)


class LimitesBusca(BaseModel):
    """Limites de uma busca. Nenhum deles corta resultado em silêncio: quando a busca para por
    causa de um teto, o resultado diz qual (motivo_parada e avisos). `limiar_muitos_resultados`
    e `limiar_poucos_resultados` só geram aviso, nunca cortam nada.

    Variáveis de ambiente: GARIMPO_MAX_PAGINAS, GARIMPO_TEMPO_MAX_SEGUNDOS,
    GARIMPO_LIMIAR_MUITOS_RESULTADOS, GARIMPO_LIMIAR_POUCOS_RESULTADOS,
    GARIMPO_PAUSA_ENTRE_PAGINAS_SEGUNDOS (dois números, ex.: "6,14"),
    GARIMPO_TENTATIVAS_BLOQUEIO, GARIMPO_BACKOFF_BASE_SEGUNDOS, GARIMPO_TIMEOUT_REQUISICAO_SEGUNDOS.
    """

    max_paginas: int = Field(default_factory=_env_int("GARIMPO_MAX_PAGINAS", 8), ge=1)
    tempo_max_segundos: float = Field(default_factory=_env_float("GARIMPO_TEMPO_MAX_SEGUNDOS", 180.0), gt=0)
    limiar_muitos_resultados: int = Field(default_factory=_env_int("GARIMPO_LIMIAR_MUITOS_RESULTADOS", 500), ge=1)
    limiar_poucos_resultados: int = Field(default_factory=_env_int("GARIMPO_LIMIAR_POUCOS_RESULTADOS", 5), ge=0)
    pausa_entre_paginas_segundos: tuple[float, float] = Field(
        default_factory=lambda: _do_ambiente("GARIMPO_PAUSA_ENTRE_PAGINAS_SEGUNDOS", (6.0, 14.0), _par)
    )
    # Repetição depois de bloqueio (403, 429, página sem anúncios) e tempo de cada requisição.
    tentativas_bloqueio: int = Field(default_factory=_env_int("GARIMPO_TENTATIVAS_BLOQUEIO", 2), ge=0)
    backoff_base_segundos: float = Field(default_factory=_env_float("GARIMPO_BACKOFF_BASE_SEGUNDOS", 20.0), ge=0)
    timeout_requisicao_segundos: float = Field(
        default_factory=_env_float("GARIMPO_TIMEOUT_REQUISICAO_SEGUNDOS", 30.0), gt=0
    )

    @model_validator(mode="after")
    def _pausa_valida(self) -> "LimitesBusca":
        menor, maior = self.pausa_entre_paginas_segundos
        if menor < 0 or menor > maior:
            raise ValueError(f"pausa_entre_paginas_segundos inválida: {self.pausa_entre_paginas_segundos}")
        return self


# ---- Servidor (server.py) ----

# Quanto tempo uma busca pronta fica no cache em memória (20 minutos).
CACHE_TTL_SEGUNDOS = _do_ambiente("GARIMPO_CACHE_TTL_SEGUNDOS", 1200.0, float)
# Até que página o "Ver mais" vai numa busca só (a OLX mostra 50 anúncios por página).
MAX_PAGINAS_SOB_DEMANDA = _do_ambiente("GARIMPO_MAX_PAGINAS_SOB_DEMANDA", 70, int)
# Pausa entre páginas quando a pessoa clica em "Ver mais" (o clique já espaça os pedidos). Dois
# números, ex.: "2,4". A leitura de várias páginas seguidas (stream) usa a pausa de LimitesBusca.
PAUSA_VER_MAIS_SEGUNDOS = _do_ambiente("GARIMPO_PAUSA_VER_MAIS_SEGUNDOS", (2.0, 4.0), _par)
# Origens liberadas no CORS, separadas por vírgula. Por padrão só o Vite local.
CORS_ORIGENS = [
    o.strip()
    for o in os.environ.get("GARIMPO_CORS_ORIGENS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if o.strip()
]
