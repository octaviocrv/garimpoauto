"""Busca de carros na OLX usando o Scrapling.

Lê o array "ads" que a página de listagem já traz dentro do payload do Next.js
(self.__next_f.push), sem abrir anúncio por anúncio e sem navegador.

Uso:

    from schemas import Busca
    from sources.olx import buscar, buscar_paginas

    busca = Busca(texto="gol 2012", estado="sp")   # sem estado = Brasil todo
    resultado = buscar(busca)       # ResultadoBusca: anuncios, funil, motivo_parada, avisos
    for pagina in buscar_paginas(busca):   # ou página por página
        mostrar(pagina.anuncios)
        if pagina.ultima:
            print(pagina.parou_por, pagina.aviso)
"""

from __future__ import annotations

import json
import random
import re
import time
import unicodedata
from datetime import datetime, timezone
from typing import Any, Callable, Iterator, Optional
from urllib.parse import quote, urlencode

from scrapling.fetchers import FetcherSession
from scrapling.parser import Selector

from busca import filtrar_local_contando, montar_resultado
from config import LimitesBusca
from schemas import Anuncio, Busca, PaginaBusca, ResultadoBusca

FONTE = "olx"
URL_BASE = "https://www.olx.com.br/autos-e-pecas/carros-vans-e-utilitarios"

# Motivos de parada (PaginaBusca.parou_por)
TOTAL_ADS = "total_ads"
MAX_PAGINAS = "max_paginas"
PAGINA_VAZIA = "pagina_vazia"
BLOQUEIO = "bloqueio"
TEMPO_MAXIMO = "tempo_maximo"

# Códigos que a própria OLX usa nos filtros da listagem de carros.
_CAMBIO = {"manual": 1, "automatico": 2, "semi-automatico": 3, "automatizado": 4}
_COMBUSTIVEL = {"gasolina": 1, "alcool": 2, "flex": 3, "diesel": 5, "hibrido": 6, "eletrico": 7}
_ANUNCIANTE = {"particular": 0, "profissional": 1}
# Ordenação: só os códigos comprovados na prática. sp=price, sp=date e sp=2 a 4 não funcionam.
_ORDEM = {"recentes": ("sf", 1), "menor_preco": ("sp", 1)}

# Degraus de km que a OLX aceita em ms/me, lidos das opções do filtro "mileage" da própria listagem.
# Melhoria futura: filtrar marca e modelo na própria OLX (vb, vm, vv, com códigos numéricos).
_DEGRAUS_KM = (
    0, 5000, 10000, 20000, 30000, 40000, 60000, 80000, 100000,
    120000, 140000, 160000, 180000, 200000, 250000, 300000, 400000, 500000,
)
# Filtros da Busca que a URL aplica sem arredondar. O resto (marca, modelo, cidade, km_max) é local.
_FILTROS_NA_URL = ("estado", "ano_min", "ano_max", "preco_min", "preco_max")

_PREFIXO_PUSH = "self.__next_f.push("
_PREFIXOS_DATALAYER = "dataLayer.push("

# Chaves (ou nomes de propriedade) que identificam o anunciante e não podem ficar guardadas.
_TERMOS_ANUNCIANTE = (
    "sellername",
    "username",
    "advertisername",
    "contactname",
    "ownername",
    "phone",
    "telefone",
    "email",
    "whatsapp",
)


class PayloadSemAdsError(Exception):
    """A página veio sem o array "ads": bloqueio ou a OLX mudou o payload."""


# ---------------------------------------------------------------------------
# Leitura do payload
# ---------------------------------------------------------------------------


def _texto_do_next(sel: Selector) -> str:
    """Junta os pedaços de string que o Next manda em self.__next_f.push([1, "..."])."""
    partes: list[str] = []
    for script in sel.css("script"):
        texto = (script.text or "").strip().rstrip(";").rstrip()
        if not (texto.startswith(_PREFIXO_PUSH) and texto.endswith(")")):
            continue
        try:
            argumento = json.loads(texto[len(_PREFIXO_PUSH) : -1])
        except ValueError:
            continue
        if isinstance(argumento, list) and len(argumento) == 2 and argumento[0] == 1:
            if isinstance(argumento[1], str):
                partes.append(argumento[1])
    return "".join(partes)


def _achar_array_ads(texto: str) -> Optional[list[dict]]:
    """Procura o array "ads" com parse de JSON de verdade. None se não existir."""
    decoder = json.JSONDecoder()
    marcador = '"ads":'
    achou_vazio = False
    pos = texto.find(marcador)
    while pos != -1:
        try:
            valor, _ = decoder.raw_decode(texto, pos + len(marcador))
        except ValueError:
            valor = None
        if isinstance(valor, list):
            if not valor:
                achou_vazio = True
            elif all(isinstance(x, dict) for x in valor) and any(
                "listId" in x or "advertisingId" in x for x in valor
            ):
                return valor
        pos = texto.find(marcador, pos + 1)
    return [] if achou_vazio else None


def _total_ads(sel: Selector) -> Optional[int]:
    """Lê o totalOfAds do dataLayer da página."""
    for script in sel.css("script"):
        texto = script.text or ""
        pos = texto.find(_PREFIXOS_DATALAYER)
        if pos == -1 or "totalOfAds" not in texto:
            continue
        try:
            dados, _ = json.JSONDecoder().raw_decode(texto, pos + len(_PREFIXOS_DATALAYER))
            total = dados["page"]["detail"]["totalOfAds"]
            return int(total)
        except (ValueError, KeyError, TypeError):
            return None
    return None


def extrair_pagina(html: str) -> tuple[list[dict], Optional[int]]:
    """Devolve (itens crus com listId, totalOfAds). Os itens de propaganda ficam de fora.

    Levanta PayloadSemAdsError se o array "ads" não existir. Se existir vazio,
    devolve lista vazia (busca sem resultado ou página depois da última).
    """
    sel = Selector(content=html)
    ads = _achar_array_ads(_texto_do_next(sel))
    if ads is None:
        raise PayloadSemAdsError(
            'A página veio sem o array "ads". Ou a OLX bloqueou a requisição, '
            "ou a OLX mudou o payload (self.__next_f) e o extrator precisa de ajuste."
        )
    reais = [a for a in ads if "listId" in a]
    return reais, _total_ads(sel)


# ---------------------------------------------------------------------------
# Normalização
# ---------------------------------------------------------------------------


def _numero(texto: Any) -> Optional[int]:
    """"R$ 107.900" -> 107900. "118000" -> 118000. Sem dígito -> None."""
    if texto is None:
        return None
    parte_inteira = str(texto).split(",")[0]
    digitos = re.sub(r"\D", "", parte_inteira)
    return int(digitos) if digitos else None


def _texto(valor: Any) -> Optional[str]:
    if valor is None:
        return None
    limpo = str(valor).strip()
    return limpo or None


def _tira_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def _nome_de_anunciante(nome: Any) -> bool:
    return isinstance(nome, str) and any(t in nome.lower() for t in _TERMOS_ANUNCIANTE)


def _sem_dados_de_anunciante(valor: Any) -> Any:
    """Copia o item removendo nome e telefone de anunciante, em qualquer nível."""
    if isinstance(valor, dict):
        return {
            k: _sem_dados_de_anunciante(v) for k, v in valor.items() if not _nome_de_anunciante(k)
        }
    if isinstance(valor, list):
        return [
            _sem_dados_de_anunciante(v)
            for v in valor
            if not (isinstance(v, dict) and _nome_de_anunciante(v.get("name")))
        ]
    return valor


def _propriedades(ad: dict) -> dict[str, Optional[str]]:
    props: dict[str, Optional[str]] = {}
    for p in ad.get("properties") or []:
        if isinstance(p, dict) and p.get("name") and not _nome_de_anunciante(p["name"]):
            props[p["name"]] = _texto(p.get("value"))
    return props


def _data(timestamp: Any) -> Optional[datetime]:
    try:
        return datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _imagens(ad: dict) -> list[str]:
    links = []
    for img in ad.get("images") or []:
        if isinstance(img, dict):
            link = img.get("original") or img.get("originalWebp")
            if link:
                links.append(link)
    return links


def _nota_do_anunciante(ad: dict, profissional: Optional[bool]) -> Optional[float]:
    """Nota do Google do anunciante (de 0 a 5). Só vale para anunciante profissional.
    De particular, ou se o valor não for um número entre 0 e 5, devolve None."""
    nota = ad.get("userGoogleRating")
    if profissional is not True or isinstance(nota, bool) or not isinstance(nota, (int, float)):
        return None
    return float(nota) if 0 <= nota <= 5 else None


def normalizar(ad: dict) -> Anuncio:
    """Item cru da OLX -> modelo único. Campo vazio vira None, nada é inventado."""
    props = _propriedades(ad)
    local = ad.get("locationDetails") if isinstance(ad.get("locationDetails"), dict) else {}

    cidade = _texto(local.get("municipality"))
    bairro = _texto(local.get("neighbourhood"))
    if cidade is None and bairro is None and ad.get("location"):
        cidade, _, resto = str(ad["location"]).partition(",")
        cidade, bairro = _texto(cidade), _texto(resto)

    portas = _numero(props.get("doors"))
    profissional = ad.get("professionalAd") if isinstance(ad.get("professionalAd"), bool) else None
    raw = _sem_dados_de_anunciante(ad)
    if profissional is not True:
        raw.pop("userGoogleRating", None)  # nota de particular não é guardada, nem no item cru
    anuncio = Anuncio(
        source=FONTE,
        external_id=str(ad["listId"]),
        url=ad.get("url"),
        titulo=_texto(ad.get("subject")),
        marca=props.get("vehicle_brand"),
        modelo=props.get("vehicle_model"),
        modelo_original=props.get("vehicle_model"),
        ano=_numero(props.get("regdate")),
        km=_numero(props.get("mileage")),
        preco=_numero(ad.get("priceValue")) if ad.get("priceValue") else _numero(ad.get("price")),
        cambio=props.get("gearbox"),
        combustivel=props.get("fuel"),
        cor=props.get("carcolor"),
        portas=portas,
        cidade=cidade,
        bairro=bairro,
        estado=_texto(local.get("uf")),
        publicado_em=_data(ad.get("date")),
        anunciante_profissional=profissional,
        nota_anunciante=_nota_do_anunciante(ad, profissional),
        imagens=_imagens(ad),
        raw=raw,
    )
    return anuncio.marcar_completude()


# ---------------------------------------------------------------------------
# URL e filtros
# ---------------------------------------------------------------------------


def _codigo(tabela: dict[str, int], valor: Any, nome: str) -> int:
    if isinstance(valor, int):
        return valor
    chave = _tira_acento(str(valor)).lower().strip().replace(" ", "-")
    if chave not in tabela:
        raise ValueError(f"{nome} desconhecido: {valor!r}. Opções: {', '.join(tabela)}")
    return tabela[chave]


def _degrau_km(km: int) -> Optional[int]:
    """Menor degrau da OLX que cobre `km`. None se for maior que o último degrau conhecido
    (nesse caso não manda km_max e deixa o filtro local fazer o corte)."""
    return next((d for d in _DEGRAUS_KM if d >= km), None)


def montar_url(
    busca: Busca,
    pagina: int = 1,
    *,
    km_min: Optional[int] = None,
    cambio: Optional[str] = None,
    combustivel: Optional[str] = None,
    anunciante: Optional[str] = None,
    ordenar: Optional[str] = None,
) -> str:
    """Monta a URL de listagem só com os filtros da Busca que a OLX aceita (estado, região, ano,
    preço e km). Marca, modelo e cidade ficam para filtrar_local. O km_max vai como o degrau
    mais próximo que cobre o pedido (a OLX só aceita degraus) e o valor exato é aplicado
    depois. km_min precisa ser um degrau. Parâmetros da OLX: q, o, ps/pe, rs/re, ms/me, gb, fu, f, sp/sf."""
    caminho = URL_BASE
    if busca.estado:
        caminho += f"/estado-{busca.estado.lower()}"
        if busca.regiao:
            caminho += f"/{busca.regiao.strip('/')}"

    km_max = _degrau_km(busca.km_max) if busca.km_max is not None else None
    params: list[tuple[str, Any]] = [("q", busca.texto)]
    if pagina > 1:
        params.append(("o", pagina))
    opcionais = [
        ("ps", busca.preco_min),
        ("pe", busca.preco_max),
        ("rs", busca.ano_min),
        ("re", busca.ano_max),
        ("ms", km_min),
        ("me", km_max),
    ]
    params += [(k, v) for k, v in opcionais if v is not None]
    if cambio is not None:
        params.append(("gb", _codigo(_CAMBIO, cambio, "cambio")))
    if combustivel is not None:
        params.append(("fu", _codigo(_COMBUSTIVEL, combustivel, "combustivel")))
    if anunciante is not None:
        params.append(("f", _codigo(_ANUNCIANTE, anunciante, "anunciante")))
    if ordenar is not None and ordenar != "relevancia":
        if ordenar not in _ORDEM:
            raise ValueError(f"ordenar desconhecido: {ordenar!r}. Opções: relevancia, {', '.join(_ORDEM)}")
        params.append(_ORDEM[ordenar])
    return f"{caminho}?{urlencode(params, quote_via=quote)}"


# ---------------------------------------------------------------------------
# Busca
# ---------------------------------------------------------------------------


def _baixar_com_cuidado(
    sessao: Any,
    url: str,
    *,
    inicio: float,
    tempo_max: float,
    tentativas_bloqueio: int,
    backoff_base: float,
    dormir: Callable[[float], None],
    relogio: Callable[[], float],
) -> tuple[Optional[list[dict]], Optional[int], Optional[str]]:
    """Baixa uma página. Em 403, 429 ou página sem "ads", espera cada vez mais e tenta de novo,
    no máximo `tentativas_bloqueio` vezes. Devolve (itens, totalOfAds, erro)."""
    erro = "sem resposta"
    for tentativa in range(tentativas_bloqueio + 1):
        if tentativa > 0:
            espera = backoff_base * (2 ** (tentativa - 1)) * random.uniform(1.0, 1.5)
            if relogio() - inicio + espera > tempo_max:
                return None, None, f"{erro} (sem tempo para tentar de novo)"
            dormir(espera)
        try:
            resposta = sessao.get(url)
        except Exception as e:  # falha de rede, timeout, etc.
            erro = f"falha de rede ({type(e).__name__})"
            continue
        status = resposta.status
        if status == 404:
            return [], None, None  # página depois da última
        if status != 200:
            erro = f"HTTP {status}"
            continue
        try:
            itens, total = extrair_pagina(resposta.html_content)
        except PayloadSemAdsError as e:
            erro = str(e)
            continue
        return itens, total, None
    return None, None, erro


def buscar_paginas(
    busca: Busca,
    limites: Optional[LimitesBusca] = None,
    *,
    km_min: Optional[int] = None,
    cambio: Optional[str] = None,
    combustivel: Optional[str] = None,
    anunciante: Optional[str] = None,
    ordenar: Optional[str] = None,
    sessao: Any = None,
    dormir: Callable[[float], None] = time.sleep,
    relogio: Callable[[], float] = time.monotonic,
) -> Iterator[PaginaBusca]:
    """Busca carros na OLX e devolve uma página de cada vez (gerador). Quem não precisa disso
    usa `buscar`, que junta tudo e devolve o ResultadoBusca com funil e avisos.

    Para quando acontecer o primeiro destes: chegou no totalOfAds, a página veio vazia ou só
    com repetidos, bateu `limites.max_paginas`, passou de `limites.tempo_max_segundos`, ou
    houve bloqueio. A última página devolvida traz `parou_por` preenchido. Nenhum limite
    descarta anúncio: só decide quando parar de pedir páginas.

    Uma página por vez, nunca em paralelo, com pausa aleatória (`limites.pausa_entre_paginas_segundos`)
    e a mesma sessão (cookies) do começo ao fim. Depois de um bloqueio, não insiste: espera e
    tenta de novo até `limites.tentativas_bloqueio` vezes e então para, devolvendo o que já juntou.

    Os filtros que a OLX não aceita ou arredonda (marca, modelo, cidade, km exato) são aplicados
    por filtrar_local em cada página: `anuncios` traz só os que passam, enquanto `acumulado`
    conta o que veio da OLX, antes desse filtro.
    """
    limites = limites or LimitesBusca()
    filtros = dict(
        km_min=km_min,
        cambio=cambio,
        combustivel=combustivel,
        anunciante=anunciante,
        ordenar=ordenar,
    )
    montar_url(busca, 1, **filtros)  # valida os argumentos antes de bater na OLX

    inicio = relogio()
    vistos: set[str] = set()
    acumulado = 0
    total_ads: Optional[int] = None

    gerenciador = None
    if sessao is None:
        # retries=1: o Scrapling não repete sozinho. Quem decide repetir sou eu, com backoff.
        gerenciador = FetcherSession(
            impersonate="chrome", stealthy_headers=True,
            timeout=limites.timeout_requisicao_segundos, retries=1,
        )
        sessao = gerenciador.__enter__()
    try:
        pagina = 1
        while True:
            url = montar_url(busca, pagina, **filtros)
            itens, total, erro = _baixar_com_cuidado(
                sessao,
                url,
                inicio=inicio,
                tempo_max=limites.tempo_max_segundos,
                tentativas_bloqueio=limites.tentativas_bloqueio,
                backoff_base=limites.backoff_base_segundos,
                dormir=dormir,
                relogio=relogio,
            )
            if itens is None:
                yield PaginaBusca(
                    fonte=FONTE,
                    numero=pagina,
                    anuncios=[],
                    acumulado=acumulado,
                    total_ads=total_ads,
                    parou_por=BLOQUEIO,
                    aviso=f"Parou por bloqueio na página {pagina}: {erro}. "
                    f"Devolvi os {acumulado} anúncios que já tinha.",
                )
                return

            if total is not None and (total > 0 or total_ads is None):
                total_ads = total  # uma página vazia com total 0 não apaga o total já visto
            novos: list[Anuncio] = []
            for item in itens:
                id_ = str(item["listId"])
                if id_ in vistos:
                    continue
                vistos.add(id_)
                novos.append(normalizar(item))
            acumulado += len(novos)

            aviso = None
            parou_por = None
            if not novos:
                parou_por = PAGINA_VAZIA
                aviso = (
                    "A página só tinha anúncios repetidos."
                    if itens
                    else "A página veio sem anúncios."
                )
            elif total_ads is not None and len(vistos) >= total_ads:
                parou_por = TOTAL_ADS
            elif pagina >= limites.max_paginas:
                parou_por = MAX_PAGINAS

            espera = random.uniform(*limites.pausa_entre_paginas_segundos)
            if parou_por is None and relogio() - inicio + espera > limites.tempo_max_segundos:
                parou_por = TEMPO_MAXIMO
                aviso = f"Parou no tempo máximo de {limites.tempo_max_segundos:.0f}s da busca."

            aprovados, cortados = filtrar_local_contando(novos, busca, ignorar=_FILTROS_NA_URL)
            yield PaginaBusca(
                fonte=FONTE,
                numero=pagina,
                anuncios=aprovados,
                acumulado=acumulado,
                total_ads=total_ads,
                parou_por=parou_por,
                aviso=aviso,
                coletados=len(novos),
                cortados_por_filtro=cortados,
            )
            if parou_por is not None:
                return
            dormir(espera)
            pagina += 1
    finally:
        if gerenciador is not None:
            gerenciador.__exit__(None, None, None)


_MOTIVOS = {
    TOTAL_ADS: "acabaram_paginas",
    PAGINA_VAZIA: "acabaram_paginas",
    MAX_PAGINAS: "teto_paginas",
    TEMPO_MAXIMO: "teto_tempo",
    BLOQUEIO: "falha_fonte",
}


def buscar(
    busca: Busca,
    limites: Optional[LimitesBusca] = None,
    *,
    relogio: Callable[[], float] = time.monotonic,
    **kwargs: Any,
) -> ResultadoBusca:
    """Busca na OLX e devolve o ResultadoBusca completo (anúncios, funil, motivo de parada e
    avisos). Aceita os mesmos extras de `buscar_paginas` (km_min, cambio, combustivel,
    anunciante, ordenar, sessao, dormir). Se algo falhar no meio, devolve o que já juntou
    com motivo_parada "falha_fonte" em vez de levantar erro."""
    limites = limites or LimitesBusca()
    inicio = relogio()
    anuncios: list[Anuncio] = []
    cortados: dict[str, int] = {}
    paginas = coletados = 0
    total_na_fonte: Optional[int] = None
    motivo = "falha_fonte"
    detalhe_falha: Optional[str] = "a busca terminou sem motivo registrado"
    try:
        for pag in buscar_paginas(busca, limites, relogio=relogio, **kwargs):
            if pag.parou_por != BLOQUEIO:
                paginas += 1
            anuncios.extend(pag.anuncios)
            coletados += pag.coletados
            for nome, qtd in pag.cortados_por_filtro.items():
                cortados[nome] = cortados.get(nome, 0) + qtd
            if pag.total_ads is not None:
                total_na_fonte = pag.total_ads
            if pag.parou_por is not None:
                motivo = _MOTIVOS[pag.parou_por]
                detalhe_falha = pag.aviso
    except Exception as e:  # resposta estranha, falha de rede fora do retry, etc.
        motivo = "falha_fonte"
        detalhe_falha = f"erro inesperado na pagina {paginas + 1} ({type(e).__name__}: {e})"
    return montar_resultado(
        FONTE, anuncios, paginas, relogio() - inicio, total_na_fonte, coletados, cortados,
        motivo, limites, detalhe_falha,
    )


def buscar_tudo(*args: Any, **kwargs: Any) -> ResultadoBusca:
    """Nome antigo de `buscar`, que agora já devolve tudo junto."""
    return buscar(*args, **kwargs)
