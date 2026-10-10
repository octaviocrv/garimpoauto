"""Partes da busca que não dependem da fonte: chave de cache e filtro local.

O filtro local roda depois da coleta, sobre os Anuncio já normalizados. Qualquer fonte
(OLX, Mercado Livre, WebMotors) usa a mesma função e diz quais filtros já foram
aplicados na URL, para não repetir.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from typing import Iterable, Optional, Sequence

from config import LimitesBusca
from schemas import Anuncio, Aviso, Busca, Funil, ResultadoBusca

# Ordem fixa dos filtros na chave de busca.
_ORDEM_CHAVE = (
    "texto", "marca", "modelo", "versao", "ano_min", "ano_max",
    "preco_min", "preco_max", "km_min", "km_max", "cambio", "combustivel", "anunciante",
    "estado", "regiao", "cidade", "ordenar",
)
FILTROS = _ORDEM_CHAVE[1:]


def normalizar_texto(texto: Optional[str]) -> str:
    """Minúscula, sem acento, espaços únicos."""
    if not texto:
        return ""
    sem_acento = "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
    return " ".join(sem_acento.lower().split())


def chave_busca(busca: Busca) -> str:
    """Texto estável para cache: mesmo pedido, mesma chave, mesmo com outra caixa, acento
    ou espaços. Só entram os filtros preenchidos, sempre na mesma ordem."""
    partes = []
    for campo in _ORDEM_CHAVE:
        valor = getattr(busca, campo)
        if valor is None:
            continue
        partes.append(f"{campo}={normalizar_texto(valor) if isinstance(valor, str) else valor}")
    return "|".join(partes)


def _contem(procurado: str, valor: Optional[str]) -> bool:
    """Palavra inteira: 'up' não casa com 'upgrade'. 'volkswagen' casa com 'VW - VolksWagen'."""
    alvo = normalizar_texto(valor)
    return bool(alvo) and re.search(rf"(?<!\w){re.escape(procurado)}(?!\w)", alvo) is not None


def _tem_todas(procuradas: str, valor: Optional[str]) -> bool:
    """Todas as palavras de `procuradas` aparecem no texto (cada uma inteira)."""
    return bool(valor) and all(_contem(p, valor) for p in procuradas.split())


def filtrar_local_contando(
    anuncios: Iterable[Anuncio], busca: Busca, ignorar: Iterable[str] = ()
) -> tuple[list[Anuncio], dict[str, int]]:
    """Como filtrar_local, mas devolve também quantos anúncios cada filtro cortou. Só entram
    os filtros ativos (marca, modelo, cidade, estado, ano, preco, km). Cada anúncio cortado
    conta no primeiro filtro que o reprova, nesta ordem, então a soma dos cortes é exata."""
    ignorar = set(ignorar)
    ativos = {f for f in FILTROS if getattr(busca, f) is not None and f not in ignorar}
    marca = normalizar_texto(busca.marca)
    modelo = normalizar_texto(busca.modelo)
    versao = normalizar_texto(busca.versao)
    cidade = normalizar_texto(busca.cidade)

    def faixa(a: Anuncio, atributo: str, minimo: Optional[str], maximo: str) -> bool:
        """True se o anúncio passa. Campo vazio não passa por filtro que o usa."""
        usa_min, usa_max = minimo in ativos, maximo in ativos  # minimo None nunca está em ativos
        if not (usa_min or usa_max):
            return True
        valor = getattr(a, atributo)
        if valor is None:
            return False
        if usa_min and valor < getattr(busca, minimo):
            return False
        return not (usa_max and valor > getattr(busca, maximo))

    testes = (
        ("marca", "marca" in ativos, lambda a: _contem(marca, a.marca)),
        ("modelo", "modelo" in ativos, lambda a: _contem(modelo, a.modelo_original or a.modelo)),
        ("versao", "versao" in ativos, lambda a: _tem_todas(versao, " ".join(filter(None, [a.modelo_original, a.titulo])))),
        ("cidade", "cidade" in ativos, lambda a: normalizar_texto(a.cidade) == cidade),
        ("estado", "estado" in ativos, lambda a: (a.estado or "").upper() == busca.estado),
        ("ano", bool(ativos & {"ano_min", "ano_max"}), lambda a: faixa(a, "ano", "ano_min", "ano_max")),
        ("preco", bool(ativos & {"preco_min", "preco_max"}), lambda a: faixa(a, "preco", "preco_min", "preco_max")),
        ("km", bool(ativos & {"km_min", "km_max"}), lambda a: faixa(a, "km", "km_min", "km_max")),
    )
    testes = [(nome, fn) for nome, ligado, fn in testes if ligado]
    cortados = {nome: 0 for nome, _ in testes}
    aprovados = []
    for a in anuncios:
        reprovou = next((nome for nome, fn in testes if not fn(a)), None)
        if reprovou is None:
            aprovados.append(a)
        else:
            cortados[reprovou] += 1
    return aprovados, cortados


def filtrar_local(
    anuncios: Iterable[Anuncio], busca: Busca, ignorar: Iterable[str] = ()
) -> list[Anuncio]:
    """Mantém só os anúncios que cumprem os filtros da busca. `ignorar` lista os filtros que
    a fonte já aplicou na URL. Anúncio com o campo vazio não passa por filtro que o usa:
    não dá para confirmar, e nada é inventado. regiao não é checada aqui (não existe no anúncio)."""
    return filtrar_local_contando(anuncios, busca, ignorar)[0]


# ---------------------------------------------------------------------------
# Resultado e avisos (iguais para todas as fontes)
# ---------------------------------------------------------------------------


def _avisos(
    fonte: str, funil: Funil, motivo: str, paginas: int, tempo: float,
    limites: LimitesBusca, detalhe_falha: Optional[str], nao_resolvidos: Sequence[str] = (),
) -> list[Aviso]:
    nome = fonte.upper()
    execucao = f"parou em {paginas} paginas, teto {limites.max_paginas}, tempo {tempo:.0f}s de {limites.tempo_max_segundos:.0f}s"
    cortes = sum(funil.cortados_por_filtro.values())
    avisos: list[Aviso] = []
    if motivo == "teto_paginas":
        avisos.append(Aviso(
            codigo="teto_paginas",
            mensagem=f"A busca parou no limite de páginas, então pode haver mais anúncios na {nome}. Refine com estado, ano ou preço.",
            detalhe_tecnico=f"{execucao}, coletados {funil.coletados}, total na fonte {funil.total_na_fonte}",
        ))
    elif motivo == "teto_tempo":
        avisos.append(Aviso(
            codigo="teto_tempo",
            mensagem=f"A busca parou no tempo máximo, então pode haver mais anúncios na {nome}. Tente de novo ou refine a busca.",
            detalhe_tecnico=f"{execucao}, coletados {funil.coletados}, total na fonte {funil.total_na_fonte}",
        ))
    elif motivo == "falha_fonte":
        avisos.append(Aviso(
            codigo="fonte_parcial",
            mensagem=(
                f"A {nome} não respondeu direito no meio da busca, então a lista pode estar incompleta."
                if funil.coletados
                else f"A {nome} não respondeu a essa busca."
            ),
            detalhe_tecnico=f"{execucao}, coletados {funil.coletados}. {detalhe_falha or 'sem detalhe'}",
        ))
    if nao_resolvidos:
        quais = " e ".join(nao_resolvidos)
        avisos.append(Aviso(
            codigo="filtro_aproximado",
            mensagem=f"Não achei {quais} na lista da {nome}, então filtrei por aqui. Pode ter ficado algum carro de fora.",
            detalhe_tecnico=(
                f"sem código na {nome} para: {quais}. Filtro aplicado só depois da coleta, "
                f"nas {paginas} páginas lidas (teto {limites.max_paginas})"
            ),
        ))
    referencia = funil.total_na_fonte if funil.total_na_fonte is not None else funil.coletados
    if referencia > limites.limiar_muitos_resultados:
        avisos.append(Aviso(
            codigo="muitos_resultados",
            mensagem="Essa busca tem muitos resultados. Refine com estado, ano ou preço para ver os mais relevantes.",
            detalhe_tecnico=(
                f"{referencia} resultados ({'total na fonte' if funil.total_na_fonte is not None else 'coletados'}), "
                f"limiar {limites.limiar_muitos_resultados}, coletados {funil.coletados}"
            ),
        ))
    if motivo != "falha_fonte" and funil.finais < limites.limiar_poucos_resultados:
        avisos.append(Aviso(
            codigo="poucos_resultados",
            mensagem="Sobraram poucos anúncios depois dos filtros. Tente afrouxar marca, modelo, cidade ou km.",
            detalhe_tecnico=(
                f"finais {funil.finais}, limiar {limites.limiar_poucos_resultados}, coletados {funil.coletados}, "
                f"cortados {cortes} {funil.cortados_por_filtro}"
            ),
        ))
    return avisos


def _chave_do_carro(a: Anuncio) -> Optional[tuple]:
    """Mesmo carro anunciado de novo: marca, modelo, ano, km, preço e cidade iguais. Só vale com
    preço e km, senão qualquer par pareceria igual."""
    if a.preco is None or a.km is None:
        return None
    return (
        normalizar_texto(a.marca), normalizar_texto(a.modelo_original or a.modelo), a.ano, a.km, a.preco,
        normalizar_texto(a.cidade),
    )


def marcar_repetidos(anuncios: Iterable[Anuncio], vistos: dict[tuple, str]) -> None:
    """Marca em `repetido_de` o id do primeiro anúncio igual. Nada é apagado. `vistos` guarda o
    primeiro de cada carro e vale para a busca inteira (páginas diferentes)."""
    for a in anuncios:
        chave = _chave_do_carro(a)
        if chave is None:
            continue
        primeiro = vistos.setdefault(chave, a.external_id)
        if primeiro != a.external_id:
            a.repetido_de = primeiro


def filtros_locais(busca: Busca, na_origem: Iterable[str]) -> list[str]:
    """Filtros pedidos que a fonte não aplicou e que, por isso, só valem depois da coleta."""
    feitos = set(na_origem)
    pedidos = [
        ("marca", busca.marca), ("modelo", busca.modelo), ("versao", busca.versao),
        ("cidade", busca.cidade), ("km", busca.km_min if busca.km_min is not None else busca.km_max),
    ]
    return [n for n, v in pedidos if v is not None and n not in feitos]


def montar_resultado(
    fonte: str, anuncios: list[Anuncio], paginas_lidas: int, tempo: float,
    total_na_fonte: Optional[int], coletados: int, cortados: dict[str, int],
    motivo: str, limites: LimitesBusca, detalhe_falha: Optional[str] = None,
    na_origem: Sequence[str] = (), nao_resolvidos: Sequence[str] = (), locais: Sequence[str] = (),
    busca: Optional[Busca] = None,
) -> ResultadoBusca:
    """Fecha a busca: monta o funil e os avisos. Qualquer fonte usa esta mesma função."""
    funil = Funil(
        total_na_fonte=total_na_fonte, coletados=coletados,
        cortados_por_filtro=cortados, finais=len(anuncios),
    )
    return ResultadoBusca(
        fonte=fonte, anuncios=anuncios, paginas_lidas=paginas_lidas, tempo_segundos=tempo,
        funil=funil, motivo_parada=motivo,
        avisos=_avisos(fonte, funil, motivo, paginas_lidas, tempo, limites, detalhe_falha, nao_resolvidos),
        filtros_na_origem=list(na_origem), filtros_locais=list(locais),
        busca=busca, coletado_em=datetime.now(timezone.utc),
    )
