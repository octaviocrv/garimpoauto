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

from busca import filtrar_local_contando, filtros_locais, marcar_repetidos, montar_resultado, normalizar_texto
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


def _datas(ad: dict) -> tuple[Optional[datetime], Optional[datetime]]:
    """(publicado_em, renovado_em). O "date" da OLX é a publicação se lastBumpAgeSecs for "0"
    (nunca renovado) e a renovação se for outro número. Sem esse campo não dá para saber, então
    nenhuma das duas é preenchida."""
    data, renovacao = _data(ad.get("date")), ad.get("lastBumpAgeSecs")
    if data is None or renovacao is None:
        return None, None
    try:
        nunca_renovado = int(str(renovacao).strip()) == 0
    except ValueError:
        return None, None
    return (data, None) if nunca_renovado else (None, data)


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
    publicado_em, renovado_em = _datas(ad)
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
        publicado_em=publicado_em,
        renovado_em=renovado_em,
        em_destaque=bool(ad.get("isFeatured") or ad.get("fixedOnTop")),
        anunciante_profissional=profissional,
        nota_anunciante=_nota_do_anunciante(ad, profissional),
        imagens=_imagens(ad),
        raw=raw,
    )
    return anuncio.marcar_completude()



# ---------------------------------------------------------------------------
# Códigos de marca, modelo e versão (filtros vb, vm, vv da própria OLX)
# ---------------------------------------------------------------------------

URL_FILTROS = "https://www.olx.com.br/api/filters/v1/attributes"
TTL_CODIGOS = 12 * 3600  # as listas de marca, modelo e versão mudam pouco
_CODIGOS: dict[str, tuple[float, list[dict]]] = {}


def limpar_cache_codigos() -> None:
    _CODIGOS.clear()


def _sem_simbolos(texto: Optional[str]) -> str:
    """'HR-V' e 'hrv' ficam iguais."""
    return re.sub(r"[^a-z0-9]", "", normalizar_texto(texto))


def achar_marca(texto: str, lista: list[dict]) -> Optional[dict]:
    """Casa o texto com o nome da marca ou com uma palavra do endereço dela ('vw' acha Volkswagen).
    Se mais de uma marca servir, devolve None: melhor filtrar por aqui do que chutar."""
    alvo, sem = normalizar_texto(texto), _sem_simbolos(texto)
    servem = [
        i for i in lista
        if normalizar_texto(i["label"]) == alvo
        or _sem_simbolos(i["label"]) == sem
        or alvo in (i.get("extraData", {}).get("friendlyPath") or "").split("-")
        or _sem_simbolos(i.get("extraData", {}).get("friendlyPath")) == sem
    ]
    return servem[0] if len(servem) == 1 else None


def achar_modelo(texto: str, lista: list[dict]) -> tuple[Optional[dict], str]:
    """Modelo exato, ou o maior modelo que abre o texto ('civic touring' acha Civic e sobra
    'touring'). Devolve (modelo, o que sobrou)."""
    alvo, sem = normalizar_texto(texto), _sem_simbolos(texto)
    for i in lista:
        if normalizar_texto(i["label"]) == alvo or _sem_simbolos(i["label"]) == sem:
            return i, ""
    abre = [i for i in lista if alvo.startswith(normalizar_texto(i["label"]) + " ")]
    if not abre:
        return None, ""
    melhor = max(abre, key=lambda i: len(i["label"]))
    return melhor, alvo[len(normalizar_texto(melhor["label"])):].strip()


def achar_versao(texto: str, lista: list[dict]) -> Optional[dict]:
    """Versão de nome igual, ou a única que tem todas as palavras do texto."""
    alvo = normalizar_texto(texto)
    for i in lista:
        if normalizar_texto(i["label"]) == alvo:
            return i
    palavras = alvo.split()
    servem = [i for i in lista if palavras and all(p in normalizar_texto(i["label"]).split() for p in palavras)]
    return servem[0] if len(servem) == 1 else None


class _Ritmo:
    """Mesma pausa das páginas, também entre as consultas de código e a primeira página."""

    def __init__(self, pausa: tuple[float, float], dormir: Callable[[float], None]) -> None:
        self.pausa, self.dormir, self.fez_requisicao = pausa, dormir, False

    def esperar(self) -> None:
        if self.fez_requisicao:
            self.dormir(random.uniform(*self.pausa))
        self.fez_requisicao = True


def _listar(sessao: Any, caminho: str, ritmo: _Ritmo, relogio: Callable[[], float]) -> Optional[list[dict]]:
    """Lista de marcas, modelos ou versões da OLX, guardada em memória. None se não deu para ler
    (rede, bloqueio, formato diferente): quem chamou cai no filtro local e o resultado avisa."""
    guardado = _CODIGOS.get(caminho)
    if guardado and relogio() - guardado[0] < TTL_CODIGOS:
        return guardado[1]
    ritmo.esperar()
    try:
        resposta = sessao.get(f"{URL_FILTROS}/{caminho}", headers={"Accept": "application/json"})
        if resposta.status != 200:
            return None
        achou = re.search(r"<body>(.*)</body>", resposta.html_content, re.S)
        lista = json.loads(achou.group(1) if achou else resposta.html_content)
    except Exception:
        return None
    if not isinstance(lista, list) or not all(isinstance(i, dict) and "value" in i and "label" in i for i in lista):
        return None
    _CODIGOS[caminho] = (relogio(), lista)
    return lista


def resolver_codigos(
    sessao: Any, busca: Busca, ritmo: _Ritmo, relogio: Callable[[], float],
) -> tuple[dict[str, str], set[str], list[str]]:
    """Acha os códigos que a OLX usa para a marca, o modelo e a versão pedidos.
    Devolve (códigos vb/vm/vv, filtros resolvidos de vez, o que não foi entendido).
    Um filtro "resolvido de vez" não precisa mais do filtro local."""
    codigos: dict[str, str] = {}
    resolvidos: set[str] = set()
    nao: list[str] = []

    if busca.marca:
        lista = _listar(sessao, "carbrand", ritmo, relogio)
        item = achar_marca(busca.marca, lista) if lista else None
        if item:
            codigos["vb"] = str(item["value"])
            resolvidos.add("marca")
        else:
            nao.append(f"a marca {busca.marca}")

    versao_texto = busca.versao
    if busca.modelo:
        item, resto = None, ""
        if "vb" in codigos:
            lista = _listar(sessao, f"carmodel?carbrand={codigos['vb']}", ritmo, relogio)
            item, resto = achar_modelo(busca.modelo, lista) if lista else (None, "")
        if item:
            codigos["vm"] = str(item["value"])
            if resto and not versao_texto:
                versao_texto = resto  # 'civic touring': o Civic vai na OLX e o resto tenta virar versão
            elif not resto:
                resolvidos.add("modelo")
        else:
            nao.append(f"o modelo {busca.modelo}")

    if versao_texto:
        item = None
        if "vm" in codigos:
            lista = _listar(sessao, f"carversion?carbrand={codigos['vb']}&carmodel={codigos['vm']}", ritmo, relogio)
            item = achar_versao(versao_texto, lista) if lista else None
        if item:
            codigos["vv"] = str(item["value"])
            resolvidos.add("versao")
            if busca.modelo:
                resolvidos.add("modelo")
        else:
            nao.append(f"a versão {versao_texto}")
    return codigos, resolvidos, nao


# ---------------------------------------------------------------------------
# URL e filtros
# ---------------------------------------------------------------------------


def _degrau_km(km: int) -> Optional[int]:
    """Menor degrau da OLX que cobre `km`. None se for maior que o último degrau conhecido
    (nesse caso não manda km_max e deixa o filtro local fazer o corte)."""
    return next((d for d in _DEGRAUS_KM if d >= km), None)


def _degrau_km_min(km: int) -> Optional[int]:
    """Maior degrau da OLX que não passa de `km` (assim a OLX nunca esconde um carro que serve;
    o corte exato fica para o filtro local)."""
    return max((d for d in _DEGRAUS_KM if d <= km), default=None)


def montar_url(busca: Busca, pagina: int = 1, *, codigos: Optional[dict[str, str]] = None) -> str:
    """Monta a URL de listagem só com os filtros da Busca que a OLX aceita: estado, região, ano,
    preço, km, câmbio, combustível, tipo de anunciante, ordenação e (com `codigos`) marca, modelo
    e versão. Cidade fica para filtrar_local. O km vai como o degrau da OLX que cobre o pedido (a OLX só
    aceita degraus) e o valor exato é aplicado depois. Parâmetros da OLX: q, o, vb/vm/vv, ps/pe,
    rs/re, ms/me, gb, fu, f, sp/sf."""
    caminho = URL_BASE
    if busca.estado:
        caminho += f"/estado-{busca.estado.lower()}"
        if busca.regiao:
            caminho += f"/{busca.regiao.strip('/')}"

    km_max = _degrau_km(busca.km_max) if busca.km_max is not None else None
    km_min = (_degrau_km_min(busca.km_min) or None) if busca.km_min else None  # degrau 0 não filtra nada
    params: list[tuple[str, Any]] = [("q", busca.texto)]
    params += [(k, v) for k, v in (codigos or {}).items()]  # vb, vm, vv
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
    if busca.cambio:
        params.append(("gb", _CAMBIO[busca.cambio]))
    if busca.combustivel:
        params.append(("fu", _COMBUSTIVEL[busca.combustivel]))
    if busca.anunciante:
        params.append(("f", _ANUNCIANTE[busca.anunciante]))
    if busca.ordenar in _ORDEM:
        params.append(_ORDEM[busca.ordenar])  # relevância não manda nada
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
    filtros: dict[str, Any] = {}

    inicio = relogio()
    vistos: set[str] = set()
    carros_vistos: dict[tuple, str] = {}
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
        ritmo = _Ritmo(limites.pausa_entre_paginas_segundos, dormir)
        codigos, resolvidos, nao_resolvidos = resolver_codigos(sessao, busca, ritmo, relogio)
        filtros["codigos"] = codigos
        ignorar = (*_FILTROS_NA_URL, *resolvidos)
        na_origem = _filtros_na_origem(busca, resolvidos)
        if ritmo.fez_requisicao:
            dormir(random.uniform(*limites.pausa_entre_paginas_segundos))  # entre a consulta de códigos e a 1ª página
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
                    na_origem=na_origem,
                    nao_resolvidos=nao_resolvidos,
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
            marcar_repetidos(novos, carros_vistos)
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

            aprovados, cortados = filtrar_local_contando(novos, busca, ignorar=ignorar)
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
                na_origem=na_origem,
                nao_resolvidos=nao_resolvidos,
            )
            if parou_por is not None:
                return
            dormir(espera)
            pagina += 1
    finally:
        if gerenciador is not None:
            gerenciador.__exit__(None, None, None)


class _SemPausa:
    """Consulta de códigos sem pausa: são respostas pequenas e ficam em memória por horas."""

    fez_requisicao = False

    def esperar(self) -> None:
        self.fez_requisicao = True


class CursorOlx:
    """Uma busca da OLX que anda uma página por chamada (o servidor pagina "Ver mais" em cima disto).

    `proxima()` lê a página seguinte e devolve a PaginaBusca já normalizada, sem repetido e com o
    filtro local. A 1ª página sai sem pausa nenhuma. Da 2ª em diante, `esperar()` garante o mesmo
    intervalo aleatório de sempre desde o último pedido à OLX, descontando o tempo que a pessoa já
    levou para clicar (quem chama decide se espera fora de uma trava). Se a página não veio
    (bloqueio), devolve uma PaginaBusca com parou_por="bloqueio" e NÃO avança: chamar de novo tenta
    a mesma página. Depois de uma página com parou_por preenchido (que não seja bloqueio) a busca
    acabou. `teto` é a última página que ele entrega (padrão: limites.max_paginas)."""

    def __init__(
        self, busca: Busca, limites: Optional[LimitesBusca] = None, *, teto: Optional[int] = None,
        sessao: Any = None, dormir: Callable[[float], None] = time.sleep,
        relogio: Callable[[], float] = time.monotonic,
    ) -> None:
        self.busca, self.limites = busca, limites or LimitesBusca()
        self.teto = teto or self.limites.max_paginas
        self._sessao_externa, self._dormir, self._relogio = sessao, dormir, relogio
        self.numero = 0  # última página entregue
        self.terminou = False
        self._vistos: set[str] = set()
        self._carros: dict[tuple, str] = {}
        self._acumulado = 0
        self._total_ads: Optional[int] = None
        self._ultimo_pedido: Optional[float] = None
        self._codigos: Optional[dict[str, str]] = None
        self._ignorar: tuple[str, ...] = ()
        self._na_origem: list[str] = []
        self._nao_resolvidos: list[str] = []

    def esperar(self) -> None:
        """Pausa da 2ª página em diante. A 1ª não espera."""
        if self._ultimo_pedido is None:
            return
        alvo = random.uniform(*self.limites.pausa_entre_paginas_segundos)
        falta = alvo - (self._relogio() - self._ultimo_pedido)
        if falta > 0:
            self._dormir(falta)

    def proxima(self) -> PaginaBusca:
        if self.terminou:
            raise RuntimeError("a busca já acabou")
        pagina = self.numero + 1
        gerenciador = None
        sessao = self._sessao_externa
        if sessao is None:
            gerenciador = FetcherSession(
                impersonate="chrome", stealthy_headers=True,
                timeout=self.limites.timeout_requisicao_segundos, retries=1,
            )
            sessao = gerenciador.__enter__()
        try:
            if self._codigos is None:
                codigos, resolvidos, self._nao_resolvidos = resolver_codigos(
                    sessao, self.busca, _SemPausa(), self._relogio  # type: ignore[arg-type]
                )
                self._codigos, self._ignorar = codigos, (*_FILTROS_NA_URL, *resolvidos)
                self._na_origem = _filtros_na_origem(self.busca, resolvidos)
            itens, total, erro = _baixar_com_cuidado(
                sessao, montar_url(self.busca, pagina, codigos=self._codigos),
                inicio=self._relogio(), tempo_max=self.limites.tempo_max_segundos,
                tentativas_bloqueio=self.limites.tentativas_bloqueio,
                backoff_base=self.limites.backoff_base_segundos,
                dormir=self._dormir, relogio=self._relogio,
            )
        finally:
            self._ultimo_pedido = self._relogio()
            if gerenciador is not None:
                gerenciador.__exit__(None, None, None)

        if itens is None:
            return PaginaBusca(
                fonte=FONTE, numero=pagina, anuncios=[], acumulado=self._acumulado, total_ads=self._total_ads,
                parou_por=BLOQUEIO,
                aviso=f"Parou por bloqueio na página {pagina}: {erro}. Devolvi os {self._acumulado} anúncios que já tinha.",
                na_origem=self._na_origem, nao_resolvidos=self._nao_resolvidos,
            )
        if total is not None and (total > 0 or self._total_ads is None):
            self._total_ads = total
        novos: list[Anuncio] = []
        for item in itens:
            id_ = str(item["listId"])
            if id_ in self._vistos:  # anúncio que entrou no ar e empurrou a lista: já vimos, não repete
                continue
            self._vistos.add(id_)
            novos.append(normalizar(item))
        marcar_repetidos(novos, self._carros)
        self._acumulado += len(novos)

        parou_por, aviso = None, None
        if not novos:
            parou_por = PAGINA_VAZIA
            aviso = "A página só tinha anúncios repetidos." if itens else "A página veio sem anúncios."
        elif self._total_ads is not None and len(self._vistos) >= self._total_ads:
            parou_por = TOTAL_ADS
        elif pagina >= self.teto:
            parou_por = MAX_PAGINAS
        aprovados, cortados = filtrar_local_contando(novos, self.busca, ignorar=self._ignorar)
        self.numero, self.terminou = pagina, parou_por is not None
        return PaginaBusca(
            fonte=FONTE, numero=pagina, anuncios=aprovados, acumulado=self._acumulado,
            total_ads=self._total_ads, parou_por=parou_por, aviso=aviso, coletados=len(novos),
            cortados_por_filtro=cortados, na_origem=self._na_origem, nao_resolvidos=self._nao_resolvidos,
        )


def abrir(
    busca: Busca, limites: Optional[LimitesBusca] = None, *, teto: Optional[int] = None, **kwargs: Any
) -> CursorOlx:
    """Abre uma busca que anda uma página por vez (veja CursorOlx). Não faz pedido nenhum ainda."""
    return CursorOlx(busca, limites, teto=teto, **kwargs)


def _filtros_na_origem(busca: Busca, resolvidos: set[str]) -> list[str]:
    """Nomes dos filtros pedidos que a OLX aplicou na própria busca."""
    pedidos = [
        ("estado", busca.estado), ("regiao", busca.regiao),
        ("ano", busca.ano_min if busca.ano_min is not None else busca.ano_max),
        ("preco", busca.preco_min if busca.preco_min is not None else busca.preco_max),
        ("cambio", busca.cambio), ("combustivel", busca.combustivel), ("anunciante", busca.anunciante),
    ]
    return [n for n, v in pedidos if v is not None] + sorted(resolvidos)


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
    avisos). Aceita os mesmos extras de `buscar_paginas` (sessao, dormir, relogio). Se algo falhar no meio, devolve o que já juntou
    com motivo_parada "falha_fonte" em vez de levantar erro."""
    limites = limites or LimitesBusca()
    inicio = relogio()
    anuncios: list[Anuncio] = []
    cortados: dict[str, int] = {}
    paginas = coletados = 0
    total_na_fonte: Optional[int] = None
    na_origem: list[str] = []
    nao_resolvidos: list[str] = []
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
            na_origem, nao_resolvidos = pag.na_origem, pag.nao_resolvidos
            if pag.parou_por is not None:
                motivo = _MOTIVOS[pag.parou_por]
                detalhe_falha = pag.aviso
    except Exception as e:  # resposta estranha, falha de rede fora do retry, etc.
        motivo = "falha_fonte"
        detalhe_falha = f"erro inesperado na pagina {paginas + 1} ({type(e).__name__}: {e})"
    return montar_resultado(
        FONTE, anuncios, paginas, relogio() - inicio, total_na_fonte, coletados, cortados,
        motivo, limites, detalhe_falha, na_origem, nao_resolvidos, filtros_locais(busca, na_origem),
        busca,
    )


def buscar_tudo(*args: Any, **kwargs: Any) -> ResultadoBusca:
    """Nome antigo de `buscar`, que agora já devolve tudo junto."""
    return buscar(*args, **kwargs)
