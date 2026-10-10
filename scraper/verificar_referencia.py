"""Roda as buscas de referencia (referencia/buscas.json) na OLX de verdade e confere o que dá para
medir sozinho dos criterios de referencia/criterios.md. É lento (cada busca nova leva uns 90 s) e
bate na OLX no ritmo normal, então rode de vez em quando, não em laço.

Uso:  .venv/bin/python verificar_referencia.py [numero ...]    (sem número, roda as cinco)
"""

import json
import sys
import time
from pathlib import Path

from busca import chave_busca
from config import LimitesBusca
from schemas import Busca
from server import Servico
from sources import olx

AQUI = Path(__file__).parent
CAMPOS_PRINCIPAIS = ("preco", "ano", "km", "cidade", "modelo")


def dentro_dos_filtros(r) -> tuple[bool, str]:
    """Critério 2: tudo o que chegou respeita o que foi pedido (marca, modelo, ano, preço, km)."""
    b = r.busca
    for a in r.anuncios:
        if b.marca and (a.marca or "").lower().find(b.marca.lower()) < 0:
            return False, f"marca {a.marca!r} no anúncio {a.external_id}"
        if b.modelo and b.modelo.lower() not in (a.modelo_original or "").lower():
            return False, f"modelo {a.modelo_original!r} no anúncio {a.external_id}"
        for nome, minimo, maximo in (("ano", b.ano_min, b.ano_max), ("preco", b.preco_min, b.preco_max), ("km", b.km_min, b.km_max)):
            v = getattr(a, nome)
            if (minimo is not None or maximo is not None) and (v is None or (minimo is not None and v < minimo) or (maximo is not None and v > maximo)):
                return False, f"{nome} {v} no anúncio {a.external_id}"
        if b.estado and (a.estado or "").upper() != b.estado:
            return False, f"estado {a.estado} no anúncio {a.external_id}"
    return True, ""


def conferir(nome: str, busca: Busca) -> dict:
    servico = Servico(olx, ttl=600.0)
    inicio = time.monotonic()
    coleta, _ = servico.obter(busca)
    with coleta.cond:
        coleta.cond.wait_for(lambda: coleta.terminou)
    r = coleta.resultado
    segundos = time.monotonic() - inicio

    t0 = time.monotonic()
    servico.obter(busca)
    repetida = time.monotonic() - t0  # critério 7: volta do cache

    n = len(r.anuncios)
    ids = [a.external_id for a in r.anuncios]
    f = r.funil
    ok_filtro, onde = dentro_dos_filtros(r)
    cheios = {c: (sum(getattr(a, c) is not None for a in r.anuncios) / n if n else 1.0) for c in CAMPOS_PRINCIPAIS}
    datas = [a.publicado_em or a.renovado_em for a in r.anuncios]
    datas = [d for d in datas if d]
    decrescente = all(x >= y for x, y in zip(datas, datas[1:]))
    parou_antes = r.motivo_parada in ("teto_paginas", "teto_tempo", "falha_fonte")
    resultado = {
        "busca": nome,
        "c1_total_da_olx": f.total_na_fonte,
        "c1_ids_no_site": "manual",
        "c2_dentro_dos_filtros": ok_filtro or f"FALHOU: {onde}",
        "c3_funil_fecha": f.coletados - sum(f.cortados_por_filtro.values()) == f.finais == n,
        "c3_parcial_avisado": (not parou_antes) or any(a.codigo in ("teto_paginas", "teto_tempo", "fonte_parcial") for a in r.avisos),
        "c4_ids_repetidos": n - len(set(ids)),
        "c4_marcados_como_repetido": sum(1 for a in r.anuncios if a.repetido_de),
        "c5_campos_cheios": {c: round(v, 3) for c, v in cheios.items()},
        "c7_segundos_no_cache": round(repetida, 4),
        "c8_segundos_busca_nova": round(segundos, 1),
        "c9_informa_estado_ordem_e_hora": bool(r.busca and r.coletado_em and r.busca.ordenar),
        "extra_datas_em_ordem_decrescente": decrescente,
        "extra": {
            "anuncios": n, "paginas": r.paginas_lidas, "motivo_parada": r.motivo_parada,
            "filtros_na_origem": r.filtros_na_origem, "filtros_locais": r.filtros_locais,
            "em_destaque": sum(a.em_destaque for a in r.anuncios),
            "mais_antigo": min(datas).isoformat() if datas else None,
            "mais_novo": max(datas).isoformat() if datas else None,
            "avisos": [a.codigo for a in r.avisos],
        },
    }
    return resultado


def main() -> None:
    buscas = json.loads((AQUI / "referencia" / "buscas.json").read_text(encoding="utf-8"))
    escolha = [int(x) for x in sys.argv[1:]] or list(range(1, len(buscas) + 1))
    saida = []
    for i in escolha:
        item = buscas[i - 1]
        print(f"\n[{i}] {item['nome']}", flush=True)
        res = conferir(item["nome"], Busca(**item["busca"]))
        print(json.dumps(res, ensure_ascii=False, indent=2), flush=True)
        saida.append(res)
    destino = AQUI.parent / "dados" / "referencia_ultima.json"
    destino.parent.mkdir(exist_ok=True)
    destino.write_text(json.dumps(saida, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSalvo em {destino}")


if __name__ == "__main__":
    main()
