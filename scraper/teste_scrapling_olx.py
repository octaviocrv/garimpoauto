"""Teste real da busca na OLX. Uso: python teste_scrapling_olx.py "civic 2018" [--salvar]"""

import argparse
import json
import time
from pathlib import Path

from sources.olx import buscar

parser = argparse.ArgumentParser()
parser.add_argument("query", nargs="?", default="civic 2018")
parser.add_argument("--estado", default="mg")
parser.add_argument("--max-resultados", type=int, default=200)
parser.add_argument("--max-paginas", type=int, default=4)
parser.add_argument("--salvar", help="caminho do JSON de exemplo a salvar em dados/")
args = parser.parse_args()

inicio = time.monotonic()
anuncios = []
paginas = 0
ultima = None

for pagina in buscar(args.query, args.estado, args.max_resultados, args.max_paginas):
    if pagina.parou_por != "bloqueio":
        paginas += 1
    anuncios.extend(pagina.anuncios)
    ultima = pagina
    print(
        f"[{time.monotonic() - inicio:5.1f}s] pagina {pagina.numero}: +{len(pagina.anuncios)} "
        f"| juntou {pagina.acumulado} | totalOfAds {pagina.total_ads} "
        f"| parou_por {pagina.parou_por}",
        flush=True,
    )
    if pagina.aviso:
        print("  aviso:", pagina.aviso)

incompletos = [a for a in anuncios if a.incompleto]
print(
    f"\nPaginas: {paginas} | anuncios: {len(anuncios)} | incompletos: {len(incompletos)} "
    f"| tempo: {time.monotonic() - inicio:.1f}s | parou por: {ultima.parou_por if ultima else None}"
)
for a in incompletos:
    print("  incompleto:", a.external_id, a.titulo, "falta", a.campos_faltando)

if args.salvar and anuncios:
    destino = Path(__file__).resolve().parent.parent / "dados" / args.salvar
    leves = []
    for a in anuncios:
        d = a.to_dict(com_raw=False)
        d["imagens"] = d["imagens"][:1]  # só o link da primeira foto
        leves.append(d)
    crus = [{k: v for k, v in a.raw.items() if k != "images"} for a in anuncios]
    destino.write_text(
        json.dumps(
            {"busca": args.query, "estado": args.estado, "anuncios": leves, "crus": crus},
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    print("salvo em", destino)
