"""Locais que a OLX aceita na URL: estado > região > zona > cidade (ou bairro).

Os dados vêm de dados_olx/localidades.json, gerado por gerar_localidades.py a partir dos sitemaps
da própria OLX. A OLX só tem página de busca para parte das cidades (em MG são cerca de 150 de 850),
então cidade fora da lista continua sendo filtrada depois da coleta. Região desconhecida nunca vai
para a URL: a OLX responde "Brasil todo" quando o nome da região não existe, sem avisar.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

from busca import normalizar_texto

ARQUIVO = Path(__file__).parent / "dados_olx" / "localidades.json"


@lru_cache(maxsize=1)
def _dados() -> dict:
    try:
        return json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"estados": {}, "nomes": {}}


def recarregar() -> None:
    _dados.cache_clear()


def _arvore(uf: Optional[str]) -> dict[str, dict[str, list[str]]]:
    return _dados().get("estados", {}).get((uf or "").upper(), {})


def tem_dados(uf: Optional[str]) -> bool:
    return bool(_arvore(uf))


def _sem_simbolos(texto: Optional[str]) -> str:
    return re.sub(r"[^a-z0-9]", "", normalizar_texto(texto))


def nome_regiao(uf: str, slug: str) -> str:
    """Nome para mostrar no seletor. Vem do título da própria OLX (com acento). Sem ele, monta a
    partir do endereço."""
    nome = _dados().get("nomes", {}).get(uf.upper(), {}).get(slug)
    if nome:
        return nome
    minusculas = {"e", "de", "da", "do", "das", "dos"}
    palavras = ["região" if p == "regiao" else p for p in slug.split("-")]
    return " ".join(p if (p in minusculas or p == "região") and i else p.capitalize() for i, p in enumerate(palavras))


def regioes(uf: str) -> list[dict[str, str]]:
    """As regiões que a OLX tem no estado, para o seletor da tela."""
    return sorted(
        ({"slug": slug, "nome": nome_regiao(uf, slug)} for slug in _arvore(uf)),
        key=lambda r: _sem_simbolos(r["nome"]),
    )


def achar_regiao(uf: Optional[str], texto: str) -> Optional[str]:
    """O endereço da região (slug) a partir do que a pessoa digitou: o próprio slug, o nome da OLX
    ou o nome sem acento. None se a OLX não tem essa região no estado."""
    alvo = _sem_simbolos(texto)
    if not alvo:
        return None
    for slug in _arvore(uf):
        if alvo in (_sem_simbolos(slug), _sem_simbolos(nome_regiao(uf or "", slug))):
            return slug
    # "Belo Horizonte" serve para "Belo Horizonte e região", se for a única que começa assim
    parecidas = [
        slug for slug in _arvore(uf)
        if alvo in (_sem_simbolos(re.sub(r"(^regiao-de-|-e-regiao$)", "", slug)),)
    ]
    return parecidas[0] if len(parecidas) == 1 else None


def achar_cidade(uf: Optional[str], texto: str) -> Optional[tuple[str, str, str]]:
    """(região, zona, cidade) da cidade na árvore da OLX, ou None se ela não tem página própria ou se o
    nome serve para mais de um lugar do estado (melhor filtrar depois do que chutar)."""
    alvo = _sem_simbolos(texto)
    if not alvo:
        return None
    achados = [
        (regiao, zona, local)
        for regiao, zonas in _arvore(uf).items()
        for zona, locais in zonas.items()
        for local in locais
        if _sem_simbolos(local) == alvo
    ]
    return achados[0] if len(achados) == 1 else None
