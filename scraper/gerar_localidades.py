"""Baixa os sitemaps da OLX e monta a árvore de locais (estado > região > zona > cidade ou bairro) que
a OLX aceita na URL. Grava em dados_olx/localidades.json. É lento de propósito (27 arquivos, pausa
entre eles) e só precisa rodar de vez em quando, quando a OLX cadastrar local novo.

Uso:
    .venv/bin/python gerar_localidades.py [UF ...]          baixa a árvore (sem UF, todos os estados)
    .venv/bin/python gerar_localidades.py --nomes [UF ...]  guarda o nome de cada região, com acento,
                                                            lido do título da página da própria OLX
"""

import json
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from scrapling.fetchers import FetcherSession

UFS = "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split()
DESTINO = Path(__file__).parent / "dados_olx" / "localidades.json"


def arvore_do_estado(xml: str, uf: str) -> dict[str, dict[str, list[str]]]:
    """{região: {zona: [cidades e bairros]}} lido das URLs de local sem categoria."""
    padrao = re.compile(rf"https://www\.olx\.com\.br/estado-{uf.lower()}(?:/([^/?]+)(?:/([^/?]+)(?:/([^/?]+))?)?)?")
    arvore: dict[str, dict[str, list[str]]] = {}
    for url in re.findall(r"<loc>([^<]+)</loc>", xml):
        m = padrao.fullmatch(url)
        if not m or not m.group(1):
            continue
        regiao, zona, local = m.groups()
        zonas = arvore.setdefault(regiao, {})
        if zona:
            locais = zonas.setdefault(zona, [])
            if local and local not in locais:
                locais.append(local)
    return arvore


def nomes(ufs: list[str]) -> None:
    """Uma página de cada região (com uma busca sem resultado, que é leve) para ler o nome dela no título."""
    resultado = json.loads(DESTINO.read_text(encoding="utf-8"))
    guardados = resultado.setdefault("nomes", {})
    primeiro = True
    with FetcherSession(impersonate="chrome", stealthy_headers=True, timeout=60, retries=1) as s:
        for uf in ufs:
            for slug in resultado["estados"].get(uf, {}):
                if slug in guardados.get(uf, {}):
                    continue
                if not primeiro:
                    time.sleep(random.uniform(5, 9))
                primeiro = False
                url = f"https://www.olx.com.br/autos-e-pecas/carros-vans-e-utilitarios/estado-{uf.lower()}/{slug}?q=xqzwvkjhpqrt"
                r = s.get(url)
                titulo = re.search(r"<title>([^<]*)", r.html_content)
                achou = re.search(rf"à venda (?:em|no|na|nos|nas) (.+), {uf}\s*$", titulo.group(1)) if titulo else None
                if r.status != 200 or not achou:
                    print(uf, slug, "sem nome (HTTP", r.status, ")", flush=True)
                    continue
                guardados.setdefault(uf, {})[slug] = achou.group(1).strip()
                print(uf, slug, "=", achou.group(1).strip(), flush=True)
                DESTINO.write_text(json.dumps(resultado, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


def main() -> None:
    if sys.argv[1:2] == ["--nomes"]:
        return nomes([u.upper() for u in sys.argv[2:]] or UFS)
    ufs = [u.upper() for u in sys.argv[1:]] or UFS
    resultado = json.loads(DESTINO.read_text(encoding="utf-8")) if DESTINO.exists() else {"estados": {}}
    with FetcherSession(impersonate="chrome", stealthy_headers=True, timeout=90, retries=1) as s:
        for i, uf in enumerate(ufs):
            if i:
                time.sleep(random.uniform(5, 9))
            r = s.get(f"https://www.olx.com.br/{uf.lower()}/sitemap1.xml")
            if r.status != 200:
                print(uf, "HTTP", r.status, "pulei", flush=True)
                continue
            arvore = arvore_do_estado(r.html_content, uf)
            resultado["estados"][uf] = arvore
            zonas = sum(len(z) for z in arvore.values())
            locais = sum(len(v) for z in arvore.values() for v in z.values())
            print(f"{uf}: {len(arvore)} regiões, {zonas} zonas, {locais} cidades ou bairros", flush=True)
    resultado["gerado_em"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    resultado["fonte"] = "https://www.olx.com.br/{uf}/sitemap1.xml"
    DESTINO.write_text(json.dumps(resultado, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    print("salvo em", DESTINO)


if __name__ == "__main__":
    main()
