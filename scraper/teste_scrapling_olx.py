"""Teste real da busca na OLX. Uso: python teste_scrapling_olx.py "texto da busca" [filtros] [--salvar arquivo.json]

Os limites vêm de config.LimitesBusca (variáveis GARIMPO_*); --max-paginas sobrescreve só esta rodada.
"""

import argparse
import json
from pathlib import Path

from config import LimitesBusca
from schemas import Busca
from sources.olx import buscar

parser = argparse.ArgumentParser()
parser.add_argument("texto")
parser.add_argument("--marca")
parser.add_argument("--modelo")
parser.add_argument("--ano-min", type=int)
parser.add_argument("--ano-max", type=int)
parser.add_argument("--preco-min", type=int)
parser.add_argument("--preco-max", type=int)
parser.add_argument("--km-max", type=int)
parser.add_argument("--estado", help="sigla; sem isso a busca é no Brasil todo")
parser.add_argument("--regiao", help="slug da OLX, exige --estado")
parser.add_argument("--cidade")
parser.add_argument("--max-paginas", type=int, help="sobrescreve o limite só desta rodada")
parser.add_argument("--salvar", help="nome do JSON a salvar em dados/")
args = parser.parse_args()

campos = {k: v for k, v in vars(args).items() if k not in ("salvar", "max_paginas")}
busca = Busca(**campos)
limites = LimitesBusca(**({"max_paginas": args.max_paginas} if args.max_paginas else {}))

res = buscar(busca, limites)
f = res.funil
print(f"Busca: {busca.model_dump(exclude_none=True)}")
print(f"Limites: {limites.model_dump()}")
print(f"Páginas lidas: {res.paginas_lidas} | tempo: {res.tempo_segundos:.1f}s | motivo_parada: {res.motivo_parada}")
print(f"Funil: total na fonte {f.total_na_fonte} -> coletados {f.coletados} -> cortes {f.cortados_por_filtro} -> finais {f.finais}")
for a in res.avisos:
    print(f"Aviso [{a.codigo}] {a.mensagem}\n    técnico: {a.detalhe_tecnico}")
incompletos = [a for a in res.anuncios if a.incompleto]
print(f"Incompletos: {len(incompletos)}")
for a in incompletos:
    print("  incompleto:", a.external_id, a.titulo, "falta", a.campos_faltando)

if args.salvar and res.anuncios:
    destino = Path(__file__).resolve().parent.parent / "dados" / args.salvar
    leves = []
    for a in res.anuncios:
        d = a.to_dict(com_raw=False)
        d["imagens"] = d["imagens"][:1]  # só o link da primeira foto
        leves.append(d)
    crus = [{k: v for k, v in a.raw.items() if k != "images"} for a in res.anuncios]
    meta = res.model_dump(exclude={"anuncios"})
    destino.write_text(
        json.dumps(
            {"busca": busca.model_dump(), "resultado": meta, "anuncios": leves, "crus": crus},
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    print("salvo em", destino)
