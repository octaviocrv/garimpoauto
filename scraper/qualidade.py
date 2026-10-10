"""Relatório de qualidade dos dados da OLX. Só lê e conta, não corrige nada.

Lê os itens crus salvos em dados/, passa cada um pelo mesmo normalizar() do coletor
e mostra quanto de cada campo veio preenchido. Com mais de um arquivo, mostra um relatório
por busca e depois o total. Uso: python qualidade.py arquivo.json [outro.json ...]
"""

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Optional

from schemas import CAMPOS_OBRIGATORIOS, Anuncio
from sources.olx import normalizar

# Campos do relatório. "versao" não existe no schema: a versão vem junta no modelo.
CAMPOS_RELATORIO = ["preco", "ano", "km", "marca", "modelo", "versao", "cidade", "estado", "foto", "nota_anunciante"]

# Campos usados para achar os piores anúncios. A nota fica de fora porque só profissional tem.
CAMPOS_RANKING = [
    "titulo", "marca", "modelo", "ano", "km", "preco", "cambio", "combustivel", "cor",
    "portas", "cidade", "bairro", "estado", "publicado_em", "imagens", "anunciante_profissional",
]


def vazio(valor) -> bool:
    return valor is None or valor == "" or valor == []


def carregar(caminho: Path) -> tuple[list[Anuncio], Optional[dict]]:
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    anuncios = []
    for cru, salvo in zip(dados["crus"], dados["anuncios"]):
        # O exemplo salvo tira as fotos do item cru para ficar leve e guarda só a primeira
        # no anúncio já tratado. Devolvo esse link para o normalizar() ver se tinha foto.
        if salvo.get("imagens"):
            cru = {**cru, "images": [{"original": salvo["imagens"][0]}]}
        anuncios.append(normalizar(cru))
    return anuncios, dados.get("resultado")


def pct(parte: int, total: int) -> str:
    return f"{100 * parte / total:5.1f}%" if total else "  n/a"


def chave_duplicado(a: Anuncio):
    """Mesmo carro anunciado duas vezes: marca, modelo, ano, km, preço e cidade iguais.
    Só vale se preço e km existem (sem eles qualquer par pareceria igual)."""
    if a.preco is None or a.km is None:
        return None
    return (a.marca, a.modelo_original, a.ano, a.km, a.preco, a.cidade)


def mostrar_execucao(meta: dict) -> None:
    """Dados da coleta guardados no arquivo (arquivos antigos não têm)."""
    f = meta["funil"]
    print(f"0) Coleta: páginas lidas {meta['paginas_lidas']} | tempo {meta['tempo_segundos']:.1f}s"
          f" | motivo_parada {meta['motivo_parada']}")
    print(f"   funil: total na fonte {f['total_na_fonte']} -> coletados {f['coletados']}"
          f" -> cortes {f['cortados_por_filtro']} -> finais {f['finais']}")
    for a in meta["avisos"]:
        print(f"   aviso [{a['codigo']}] {a['mensagem']}")
        print(f"      técnico: {a['detalhe_tecnico']}")
    if not meta["avisos"]:
        print("   avisos: nenhum")
    print()


def relatorio(titulo: str, anuncios: list[Anuncio], meta: Optional[dict] = None) -> None:
    total = len(anuncios)
    print(f"=== {titulo} | anúncios: {total} ===\n")
    if meta:
        mostrar_execucao(meta)
    if not total:
        print("   sem anúncios\n")
        return

    print("1) Preenchimento por campo")
    for campo in CAMPOS_RELATORIO:
        if campo == "versao":
            print(f"   {campo:<16} não existe como campo (a versão vem dentro de 'modelo'; o texto original fica em 'modelo_original')")
            continue
        atributo = "imagens" if campo == "foto" else campo
        cheios = sum(1 for a in anuncios if not vazio(getattr(a, atributo)))
        extra = ""
        if campo == "nota_anunciante":
            prof = [a for a in anuncios if a.anunciante_profissional is True]
            com_nota = sum(1 for a in prof if a.nota_anunciante is not None)
            extra = f"  (só entre profissionais: {com_nota}/{len(prof)} = {pct(com_nota, len(prof)).strip()})"
        print(f"   {campo:<16} {cheios:>3}/{total}  {pct(cheios, total)}{extra}")

    completos = [a for a in anuncios if not any(vazio(getattr(a, c)) for c in CAMPOS_OBRIGATORIOS)]
    incompletos = [a for a in anuncios if a.incompleto]
    print(f"\n2) Campos essenciais ({', '.join(CAMPOS_OBRIGATORIOS)})")
    print(f"   com todos os essenciais:        {len(completos)}/{total}")
    print(f"   marcados como incompletos:      {len(incompletos)}/{total}  (regra atual)")
    print("   descartados pela regra atual:   0  (a regra só marca, nunca descarta)")
    for a in incompletos:
        print(f"     incompleto: {a.external_id} falta {a.campos_faltando}")

    prof = sum(1 for a in anuncios if a.anunciante_profissional is True)
    part = sum(1 for a in anuncios if a.anunciante_profissional is False)
    sem_tipo = total - prof - part
    print("\n3) Tipo de anunciante")
    print(f"   profissional: {prof} ({pct(prof, total).strip()}) | particular: {part} ({pct(part, total).strip()})"
          + (f" | sem informação: {sem_tipo}" if sem_tipo else ""))

    print("\n4) Duplicados dentro da OLX (mesmo carro, anúncios diferentes)")
    grupos = Counter(k for k in map(chave_duplicado, anuncios) if k is not None)
    repetidos = {k: n for k, n in grupos.items() if n > 1}
    print(f"   grupos de duplicados: {len(repetidos)} | anúncios envolvidos: {sum(repetidos.values())}"
          f" | anúncios que sobrariam sem a repetição: {total - sum(n - 1 for n in repetidos.values())}")

    print(f"\n5) Os 5 piores (mais campos vazios entre {len(CAMPOS_RANKING)} campos, sem contar a nota)")
    ranking = []
    for a in anuncios:
        faltando = [c for c in CAMPOS_RANKING if vazio(getattr(a, c))]
        ranking.append((len(faltando), a.external_id, faltando))
    ranking.sort(key=lambda r: (-r[0], r[1]))
    for qtd, id_, faltando in ranking[:5]:
        print(f"   {id_}  {qtd} vazios: {', '.join(faltando) if faltando else '-'}")
    print()


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("Uso: python qualidade.py arquivo.json [outro.json ...]")
    caminhos = [Path(a) for a in sys.argv[1:]]
    por_busca = [(c.name, *carregar(c)) for c in caminhos]
    for nome, anuncios, meta in por_busca:
        relatorio(nome, anuncios, meta)
    if len(por_busca) > 1:
        vistos: dict[str, Anuncio] = {}
        for _, anuncios, _ in por_busca:
            for a in anuncios:
                vistos.setdefault(a.external_id, a)
        soma = sum(len(an) for _, an, _ in por_busca)
        print(f"(o mesmo anúncio apareceu em mais de uma busca: {soma - len(vistos)} repetições; "
              f"no total ele conta uma vez só)\n")
        metas = [m for _, _, m in por_busca if m]
        if metas:
            motivos = Counter(m["motivo_parada"] for m in metas)
            print(f"Coleta somada: páginas lidas {sum(m['paginas_lidas'] for m in metas)}"
                  f" | tempo {sum(m['tempo_segundos'] for m in metas):.1f}s"
                  f" | coletados {sum(m['funil']['coletados'] for m in metas)}"
                  f" | finais {sum(m['funil']['finais'] for m in metas)}"
                  f" | motivos de parada {dict(motivos)}\n")
        relatorio(f"TOTAL de {len(por_busca)} buscas", list(vistos.values()))


if __name__ == "__main__":
    main()


