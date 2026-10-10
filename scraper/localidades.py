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
    return _nome_do_endereco(slug)


def _nome_do_endereco(slug: str) -> str:
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


def _zonas_validas(uf: str, regiao: str) -> list[str]:
    """Zonas da região que a OLX serve de verdade. O sitemap traz zonas que a OLX responde com o Brasil todo,
    então nos estados já conferidos (gerar_localidades.py --zonas) só valem as que têm nome coletado.
    Nos outros estados a lista é a do sitemap, e a conferência da primeira página protege a busca."""
    todas = list(_arvore(uf).get(regiao, {}))
    if uf.upper() not in _dados().get("zonas_conferidas", []):
        return todas
    nomes = _dados().get("nomes_zonas", {}).get(uf.upper(), {}).get(regiao, {})
    return [z for z in todas if z in nomes]


def nome_zona(uf: str, regiao: str, slug: str) -> str:
    """Nome da zona para mostrar. Vem do título da OLX quando já foi coletado (gerar_localidades.py
    --zonas); senão é montado a partir do endereço, às vezes sem acento."""
    return _dados().get("nomes_zonas", {}).get(uf.upper(), {}).get(regiao, {}).get(slug) or _nome_do_endereco(slug)


def zonas(uf: str, regiao: str) -> list[dict[str, str]]:
    """As zonas que a OLX tem dentro de uma região, para o seletor da tela."""
    return sorted(
        ({"slug": z, "nome": nome_zona(uf, regiao, z)} for z in _zonas_validas(uf, regiao)),
        key=lambda z: _sem_simbolos(z["nome"]),
    )


def achar_zona(uf: Optional[str], regiao: str, texto: str) -> Optional[str]:
    """O endereço da zona (slug) dentro da região, pelo slug ou pelo nome. None se a região não tem essa zona."""
    alvo = _sem_simbolos(texto)
    if not alvo:
        return None
    for slug in _zonas_validas(uf or "", regiao):
        if alvo in (_sem_simbolos(slug), _sem_simbolos(nome_zona(uf or "", regiao, slug))):
            return slug
    return None
