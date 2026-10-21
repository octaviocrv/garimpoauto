"""Todos os filtros da busca, de ponta a ponta e offline.

O pedido entra pela API, a fonte OLX de verdade resolve os códigos e monta a URL, e uma OLX simulada
responde só os carros do catálogo que casam com aquela URL, usando os códigos que a OLX real usa
(conferidos ao vivo). O resultado é comparado com um gabarito escrito sem o código do Garimpo. Assim,
um código errado na URL ou um filtro daqui quebrado aparece como carro a mais ou a menos.

O único teste que fala com a OLX real roda só com OLX_LIVE=1.
"""

import json
import os
import random
import re
import sys
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, unquote, urlsplit

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import localidades  # noqa: E402
import server  # noqa: E402
from busca import _contem, _tem_todas, filtrar_local_contando, filtros_locais, texto_informacao  # noqa: E402
from config import LimitesBusca  # noqa: E402
from schemas import ANUNCIANTES, CAMBIOS, COMBUSTIVEIS, ESTADOS, ORDEM_PADRAO, ORDENS, Busca  # noqa: E402
from sources import olx  # noqa: E402
from tests.test_olx import Relogio, RespostaFalsa, html_com_ads, limites  # noqa: E402

FIXTURES = RAIZ / "tests" / "fixtures"


def _lista(nome):
    return json.loads((FIXTURES / f"olx_api_{nome}.json").read_text(encoding="utf-8"))


MODELOS_HONDA, VERSOES_CIVIC = _lista("modelos_honda"), _lista("versoes_civic")
API = {
    "carbrand": _lista("marcas"),
    "carmodel?carbrand=33": MODELOS_HONDA,
    "carversion?carbrand=33&carmodel=3": VERSOES_CIVIC,
}

# Códigos da OLX conferidos ao vivo em outubro de 2026. Ficam aqui, separados do olx.py, de propósito: se o
# olx.py mandar outro código, a OLX simulada devolve outros carros e o teste quebra.
CAMBIO_OLX = {"1": "Manual", "2": "Automático", "3": "Semi-Automático", "4": "Automatizado"}
COMBUSTIVEL_OLX = {"1": "Gasolina", "2": "Álcool", "3": "Flex", "5": "Diesel", "6": "Híbrido", "7": "Elétrico"}
PROFISSIONAL_OLX = "c"  # f=c traz só profissional e qualquer outro valor de f traz só particular (até f=1)
DEGRAUS_KM = {
    0, 5000, 10000, 20000, 30000, 40000, 60000, 80000, 100000,
    120000, 140000, 160000, 180000, 200000, 250000, 300000, 400000, 500000,
}
POR_PAGINA = 50

CAMBIO = {"manual": "Manual", "automatico": "Automático", "semi-automatico": "Semi-Automático", "automatizado": "Automatizado"}
COMBUSTIVEL = {
    "gasolina": "Gasolina", "alcool": "Álcool", "flex": "Flex", "diesel": "Diesel", "hibrido": "Híbrido", "eletrico": "Elétrico",
}

BH, JF = "belo-horizonte-e-regiao", "regiao-de-juiz-de-fora"
LOCAIS = {  # uf, cidade, caminho na OLX depois de /estado-xx
    "barreiro": ("MG", "Belo Horizonte", (BH, "barreiro")),
    "pampulha": ("MG", "Belo Horizonte", (BH, "pampulha")),
    "contagem": ("MG", "Contagem", (BH, "grande-belo-horizonte", "contagem")),
    "betim": ("MG", "Betim", (BH, "grande-belo-horizonte", "betim")),
    "jf": ("MG", "Juiz de Fora", (JF, JF, "juiz-de-fora")),
    "sjdr": ("MG", "São João del-Rei", (JF, JF)),  # sem página própria na OLX, igual a Belo Horizonte
    "sp": ("SP", "São Paulo", ()),
    "rj": ("RJ", "Rio de Janeiro", ()),
}
MARCAS = {  # como vem no anúncio, como vem no título, código da OLX (vb)
    "honda": ("Honda", "Honda", "33"),
    "vw": ("VW - VolksWagen", "Volkswagen", "75"),
    "gm": ("GM - Chevrolet", "Chevrolet", "29"),
    "toyota": ("Toyota", "Toyota", "73"),
    "fiat": ("Fiat", "Fiat", "25"),
    "byd": ("BYD", "BYD", "103"),
    "mercedes": ("Mercedes-Benz", "Mercedes-Benz", "55"),
}


def simples(texto):
    sem_acento = "".join(c for c in unicodedata.normalize("NFD", texto or "") if unicodedata.category(c) != "Mn")
    return " ".join(sem_acento.lower().split())


def compacto(texto):
    return re.sub(r"[^a-z0-9]", "", simples(texto))


def alfanum(texto):
    return re.findall(r"[a-z0-9]+", simples(texto))


@dataclass
class Carro:
    id: int
    marca: str
    modelo: str
    versao: str
    ano: Optional[int]
    km: Optional[int]
    preco: Optional[int]
    cambio: Optional[str]
    combustivel: Optional[str]
    onde: str
    profissional: Optional[bool]
    data: Optional[int] = None

    def __post_init__(self):
        if self.data is None:
            self.data = 1_790_000_000 - ((self.id * 7919) % 97) * 3600  # datas diferentes e fora da ordem do id

    @property
    def uf(self):
        return LOCAIS[self.onde][0]

    @property
    def cidade(self):
        return LOCAIS[self.onde][1]

    @property
    def caminho(self):
        return LOCAIS[self.onde][2]

    @property
    def vb(self):
        return MARCAS[self.marca][2]

    @property
    def vm(self):
        if self.marca != "honda":
            return None
        return next((m["value"] for m in MODELOS_HONDA if m["label"] == self.modelo), None)

    @property
    def vv(self):
        if self.marca != "honda" or self.modelo != "Civic":
            return None
        return next((v["value"] for v in VERSOES_CIVIC if v["label"] == self.versao), None)

    def cru(self):
        """O anúncio no formato da listagem da OLX. Campo que o carro não tem nem aparece."""
        nome, titulo, _ = MARCAS[self.marca]
        props = {
            "vehicle_brand": nome, "vehicle_model": f"{self.modelo} {self.versao}", "regdate": self.ano,
            "mileage": self.km, "gearbox": self.cambio, "fuel": self.combustivel,
        }
        ad = {
            "listId": self.id,
            "subject": " ".join(str(p) for p in (titulo, self.modelo, self.versao, self.ano) if p is not None),
            "url": f"https://{self.uf.lower()}.olx.com.br/autos-e-pecas/carros-vans-e-utilitarios/carro-{self.id}",
            "date": self.data,
            "lastBumpAgeSecs": "0",
            "locationDetails": {"municipality": self.cidade, "neighbourhood": "Centro", "uf": self.uf},
            "properties": [{"name": k, "value": str(v)} for k, v in props.items() if v is not None],
        }
        if self.preco is not None:
            ad["priceValue"] = "R$ " + f"{self.preco:,}".replace(",", ".")
        if self.profissional is not None:
            ad["professionalAd"] = self.profissional
        return ad

    @property
    def palavras(self):
        """O que a busca por texto da OLX encontra (simplificado): as palavras do título, da marca e do modelo."""
        nome, _, _ = MARCAS[self.marca]
        return set(simples(" ".join([self.cru()["subject"], nome, f"{self.modelo} {self.versao}"])).split())


C = Carro
BASE = [
    C(1, "honda", "Civic", "Sedan EXL 2.0 Flex 16V Aut.4p", 2018, 80000, 105000, "Automático", "Flex", "barreiro", False),
    C(2, "honda", "Civic", "Sedan Touring 1.5 Turbo 16V Aut.4p", 2019, 45000, 139900, "Automático", "Gasolina", "pampulha", True),
    C(3, "honda", "Civic", "Sedan LXR 2.0 Flexone 16V Aut. 4P", 2016, 98000, 82000, "Automático", "Flex", "contagem", False),
    C(4, "honda", "Civic", "Sedan EX 2.0 Flex 16V Aut.4p", 2017, 72000, 92500, "Automático", "Flex", "betim", True),
    C(5, "honda", "Civic", "Sedan Sport 2.0 Flex 16V Mec.4p", 2018, 60000, 99000, "Manual", "Flex", "jf", False),
    C(6, "honda", "Civic", "Sed.touring 2.0 16V Aut. (híbrido)", 2025, 5000, 265000, "Automático", "Híbrido", "sp", True),
    C(7, "honda", "Civic", "Sedan LXS 1.8/1.8 Flex 16V Mec. 4P", 2012, 150000, 52000, "Manual", "Flex", "sjdr", False),
    C(8, "honda", "Civic", "Sedan EXL 2.0 Flex 16V Aut.4p", 2020, 30000, 129000, "Automático", "Flex", "rj", False),
    C(9, "honda", "HR-V", "EXL 1.8 CVT", 2021, 40000, 125000, "Automático", "Flex", "contagem", True),
    C(10, "honda", "CR-V", "EXL 2.0 4x4", 2014, 120000, 78000, "Automático", "Gasolina", "barreiro", False),
    C(11, "honda", "Fit", "LX 1.4 Mec.", 2015, 95000, 55000, "Manual", "Flex", "pampulha", False),
    C(12, "honda", "City", "EXL 1.5 CVT", 2022, 25000, 110000, "Automático", "Flex", "sp", True),
    C(13, "vw", "T-Cross", "Highline 250 TSI", 2022, 35000, 135000, "Automático", "Flex", "contagem", True),
    C(14, "vw", "T-Cross", "Sense 200 TSI", 2020, 58000, 95000, "Automático", "Flex", "barreiro", False),
    C(15, "vw", "Gol", "1.0 MPI", 2014, 140000, 28000, "Manual", "Flex", "betim", False),
    C(16, "vw", "Golf", "GTI 2.0 TSI", 2015, 90000, 98000, "Automatizado", "Gasolina", "pampulha", True),
    C(17, "vw", "up!", "take 1.0 I-Motion", 2016, 70000, 42000, "Semi-Automático", "Flex", "jf", False),
    C(18, "vw", "Amarok", "Highline CD 2.0 4x4", 2019, 110000, 175000, "Automático", "Diesel", "sjdr", True),
    C(19, "vw", "Gol", "GL 1.6", 1995, 250000, 9000, "Manual", "Álcool", "barreiro", False),
    C(20, "gm", "Onix", "LT 1.0", 2020, 55000, 68000, "Manual", "Flex", "contagem", False),
    C(21, "gm", "Bolt", "EV Premier", 2021, 20000, 190000, "Automático", "Elétrico", "sp", True),
    C(22, "gm", "S10", "LTZ 2.8 4x4 CD", 2017, 160000, 140000, "Automático", "Diesel", "jf", True),
    C(23, "toyota", "Corolla", "XEi 2.0", 2019, 65000, 100000, "Automático", "Flex", "betim", True),
    C(24, "toyota", "Corolla", "Altis Hybrid 1.8", 2023, 15000, 180000, "Automático", "Híbrido", "betim", False),
    C(25, "toyota", "Hilux", "SRV 2.8 4x4", 2016, 180000, 165000, "Automático", "Diesel", "rj", True),
    C(26, "toyota", "Yaris", "XS 1.5 CVT", 2025, 0, 115990, "Automático", "Flex", "pampulha", True),
    C(27, "fiat", "Uno", "Way 1.0", 2012, 130000, None, "Manual", "Flex", "contagem", False),
    C(28, "fiat", "Toro", "Volcano 2.0 Diesel 4x4", 2021, 70000, 145000, "Automático", "Diesel", "barreiro", True),
    C(29, "fiat", "Mobi", "Drive 1.0 GSR", 2019, 50000, 52000, "Automatizado", "Flex", "betim", False),
    C(30, "byd", "Dolphin", "EV 95cv", 2024, 10000, 149000, "Automático", "Elétrico", "contagem", True),
    C(31, "mercedes", "C 180", "Avantgarde 1.6 Turbo", 2018, 75000, 155000, "Automático", "Gasolina", "pampulha", True),
    C(32, "fiat", "Palio", "Fire 1.0", 2010, None, 25000, "Manual", "Flex", "barreiro", False),
    C(33, "gm", "Celta", "Life 1.0", 2008, 160000, 15000, None, None, "jf", None),
    C(34, "vw", "Fusca", "1300", None, 99000, 30000, "Manual", "Gasolina", "sjdr", False),
    C(35, "honda", "Civic", "Touring", 2018, 52000, 129000, "Automático", "Gasolina", "betim", True),
]
# 55 Uno mais novos que todo o resto: com eles a busca de MG tem 2 páginas e a 1ª fica só com Uno.
ENCHIMENTO = [
    C(1000 + i, "fiat", "Uno", "Mille Fire 1.0", 2005 + i % 10, 100000 + i * 1000, 12000 + i * 100, "Manual", "Flex",
      "contagem" if i % 2 else "betim", i % 3 == 0, data=1_800_000_000 - i * 60)
    for i in range(55)
]
GRANDE = BASE + ENCHIMENTO


def params(url):
    return {k: v[0] for k, v in parse_qs(urlsplit(url).query, keep_blank_values=True).items()}


def caminho(url):
    base = urlsplit(olx.URL_BASE).path
    return [p for p in unquote(urlsplit(url).path)[len(base):].split("/") if p]


def _faixa(valor, de, ate):
    if de is None and ate is None:
        return True
    return valor is not None and (de is None or valor >= de) and (ate is None or valor <= ate)


class OlxSimulada:
    """Responde como a OLX: a listagem só com os carros que casam com o caminho e os parâmetros da URL, na
    ordem pedida e 50 por página, e a API de marca, modelo e versão com as listas reais salvas."""

    def __init__(self, catalogo, api=None):
        self.catalogo = list(catalogo)
        self.api = API if api is None else api
        self.urls = []

    @property
    def urls_de_listagem(self):
        return [u for u in self.urls if "/api/filters/" not in u]

    def get(self, url, **kw):
        self.urls.append(url)
        if "/api/filters/" in url:
            for trecho, lista in self.api.items():
                if url.endswith(trecho):
                    return RespostaFalsa(200, "<html><body>" + json.dumps(lista) + "</body></html>")
            return RespostaFalsa(404, "")
        achados = self.listar(url)
        n = int(params(url).get("o", "1"))
        fatia = achados[(n - 1) * POR_PAGINA : n * POR_PAGINA]
        return RespostaFalsa(200, html_com_ads([c.cru() for c in fatia], len(achados)))

    def listar(self, url):
        p, partes = params(url), caminho(url)
        achados = [c for c in self.catalogo if self._casa(c, partes, p)]
        if p.get("sf") == "1":
            achados.sort(key=lambda c: -c.data)
        elif p.get("sp") == "1":
            achados.sort(key=lambda c: (c.preco is None, c.preco or 0))
        return achados

    @staticmethod
    def _casa(c, partes, p):
        if partes and (partes[0] != f"estado-{c.uf.lower()}" or tuple(partes[1:]) != c.caminho[: len(partes) - 1]):
            return False
        if "q" in p and not set(simples(p["q"]).split()) <= c.palavras:
            return False
        if any(k in p and p[k] != v for k, v in (("vb", c.vb), ("vm", c.vm), ("vv", c.vv))):
            return False

        def numero(k):
            return int(p[k]) if k in p else None

        # km: a OLX só entende os degraus dela e ignora qualquer outro valor sem avisar
        ms, me = (v if v in DEGRAUS_KM else None for v in (numero("ms"), numero("me")))
        if not (
            _faixa(c.preco, numero("ps"), numero("pe")) and _faixa(c.ano, numero("rs"), numero("re")) and _faixa(c.km, ms, me)
        ):
            return False
        if "gb" in p and c.cambio != CAMBIO_OLX.get(p["gb"]):
            return False
        if "fu" in p and c.combustivel != COMBUSTIVEL_OLX.get(p["fu"]):
            return False
        return not ("f" in p and c.profissional is not (p["f"] == PROFISSIONAL_OLX))


class FonteSimulada:
    """A fonte OLX de verdade (códigos, URL, cursor e filtro daqui), com a rede trocada pela OLX simulada."""

    FONTE = "olx"

    def __init__(self, sim):
        self.sim, self.relogio, self.abertas = sim, Relogio(), 0

    def abrir(self, busca, limites=None, *, teto=None):
        self.abertas += 1
        return olx.abrir(busca, limites, teto=teto, sessao=self.sim, dormir=self.relogio.dormir, relogio=self.relogio)


@pytest.fixture(autouse=True)
def _sem_cache_de_codigos():
    olx.limpar_cache_codigos()
    yield
    olx.limpar_cache_codigos()


def cliente(catalogo=BASE):
    sim = OlxSimulada(catalogo)
    fonte = FonteSimulada(sim)
    app = server.criar_app(fonte, ttl=60.0, estado_padrao="mg", limites=LimitesBusca())
    return TestClient(app), sim, fonte


def pagina(c, **pedido):
    pedido.setdefault("texto", "")
    pedido.setdefault("pagina", 1)
    return c.get("/buscar/pagina", params=pedido)


def todas(c, **pedido):
    """Segue o Ver mais até acabar. Devolve os ids na ordem em que chegaram e as respostas."""
    ids, respostas, n = [], [], 1
    while n:
        r = pagina(c, pagina=n, **pedido)
        assert r.status_code == 200, r.text
        j = r.json()
        assert not j["falhou"]
        respostas.append(j)
        ids += [int(a["external_id"]) for a in j["anuncios"]]
        n = j["proxima_pagina"]
        assert len(respostas) < 10
    return ids, respostas


def gabarito(catalogo=BASE, *, estado="MG", regiao=None, zona=None, cidade=None, marca=None, modelo=None,
             versao=None, texto=None, ano=(None, None), preco=(None, None), km=(None, None), cambio=None,
             combustivel=None, anunciante=None):
    """O que a busca tem que trazer, escrito sem o código do Garimpo. Campo vazio nunca passa num filtro ligado."""
    ids = set()
    for c in catalogo:
        if (
            (estado and c.uf != estado)
            or (regiao and c.caminho[:1] != (regiao,))
            or (zona and c.caminho[1:2] != (zona,))
            or (cidade and compacto(c.cidade) != compacto(cidade))
            or (marca and c.marca != marca)
            or (modelo and compacto(c.modelo) != compacto(modelo))
            or (versao and not set(alfanum(versao)) <= set(alfanum(c.versao)))
            or (texto and not set(simples(texto).split()) <= c.palavras)
            or not (_faixa(c.ano, *ano) and _faixa(c.preco, *preco) and _faixa(c.km, *km))
            or (cambio and c.cambio != CAMBIO[cambio])
            or (combustivel and c.combustivel != COMBUSTIVEL[combustivel])
            or (anunciante and c.profissional is not (anunciante == "profissional"))
        ):
            continue
        ids.add(c.id)
    return ids


def url_da_olx(local="estado-mg", **ps):
    """A URL que a OLX tem que receber. `ps` na ordem em que o olx.py monta."""
    q = "&".join(f"{k}={v}" for k, v in ps.items())
    return f"{olx.URL_BASE}/{local}?{q}" if local else f"{olx.URL_BASE}?{q}"


def codigos(r):
    return [a["codigo"] for a in r["avisos"]]


MG = gabarito()


def test_o_catalogo_cobre_o_que_os_testes_precisam():
    assert len(BASE) == 35 and len(MG) == 30 and len(gabarito(GRANDE)) == 85
    assert all(gabarito(cambio=o) for o in CAMBIOS) and all(gabarito(combustivel=o) for o in COMBUSTIVEIS)
    assert all(gabarito(anunciante=o) for o in ANUNCIANTES)
    assert [c.vv for c in BASE if c.marca == "honda" and c.modelo == "Civic"] == ["34", "37", "30", "33", "36", "45", "25", "34", "42"]


# ---------------------------------------------------------------------------
# Sem filtro, estado, região, zona e cidade
# ---------------------------------------------------------------------------


def test_sem_filtro_traz_o_estado_padrao_inteiro():
    c, sim, _ = cliente()
    ids, (j,) = todas(c)
    assert set(ids) == MG and len(ids) == 30
    assert sim.urls_de_listagem == [url_da_olx(sf=1)]
    assert j["estado_aplicado"] == "MG" and j["filtros_na_origem"] == ["estado"]
    assert j["filtros_locais"] == [] and j["cortados_por_filtro"] == {} and j["avisos"] == []
    assert j["informacao"] == "Achei 30 carros. Esses são todos."


@pytest.mark.parametrize("estado,uf", [("SP", "SP"), ("rj", "RJ"), (" Mg ", "MG"), ("", "MG")])
def test_estado(estado, uf):
    c, sim, _ = cliente()
    ids, (j,) = todas(c, estado=estado)
    assert set(ids) == gabarito(estado=uf) and ids
    assert sim.urls_de_listagem == [url_da_olx(f"estado-{uf.lower()}", sf=1)]
    assert j["estado_aplicado"] == uf


@pytest.mark.parametrize("estado", ["todos", "Todos", " TODOS "])
def test_estado_todos_busca_o_brasil_inteiro(estado):
    c, sim, _ = cliente()
    ids, (j,) = todas(c, estado=estado)
    assert set(ids) == gabarito(estado=None) and len(ids) == 35
    assert sim.urls_de_listagem == [url_da_olx(None, sf=1)]
    assert j["estado_aplicado"] == "todos" and j["filtros_na_origem"] == []


@pytest.mark.parametrize("regiao,slug", [
    (BH, BH), ("Belo Horizonte e região", BH), ("belo horizonte e regiao", BH), (JF, JF), ("Região de Juiz de Fora", JF),
])
def test_regiao(regiao, slug):
    c, sim, _ = cliente()
    ids, (j,) = todas(c, regiao=regiao)
    assert set(ids) == gabarito(regiao=slug) and ids and set(ids) < MG
    assert sim.urls_de_listagem == [url_da_olx(f"estado-mg/{slug}", sf=1)]
    assert "regiao" in j["filtros_na_origem"] and j["busca"]["regiao"] == slug and j["avisos"] == []


@pytest.mark.parametrize("zona,slug", [
    ("barreiro", "barreiro"), ("Pampulha", "pampulha"), ("grande-belo-horizonte", "grande-belo-horizonte"),
])
def test_zona(zona, slug):
    c, sim, _ = cliente()
    ids, (j,) = todas(c, regiao=BH, zona=zona)
    assert set(ids) == gabarito(regiao=BH, zona=slug) and ids
    assert sim.urls_de_listagem == [url_da_olx(f"estado-mg/{BH}/{slug}", sf=1)]
    assert {"regiao", "zona"} <= set(j["filtros_na_origem"]) and j["avisos"] == []


@pytest.mark.parametrize("cidade,onde", [("Contagem", "contagem"), ("juiz de fora", "jf"), ("BETIM", "betim")])
def test_cidade_com_pagina_na_olx_vai_no_caminho(cidade, onde):
    c, sim, _ = cliente()
    ids, (j,) = todas(c, cidade=cidade)
    assert set(ids) == gabarito(cidade=LOCAIS[onde][1]) and ids
    assert sim.urls_de_listagem == [url_da_olx("estado-mg/" + "/".join(LOCAIS[onde][2]), sf=1)]
    assert "cidade" in j["filtros_na_origem"] and "cidade" not in j["filtros_locais"]
    assert j["avisos"] == [] and j["cortados_por_filtro"] == {}


@pytest.mark.parametrize("cidade,nome", [
    ("Belo Horizonte", "Belo Horizonte"), ("belo horizonte", "Belo Horizonte"), ("BELO-HORIZONTE", "Belo Horizonte"),
    ("São João del-Rei", "São João del-Rei"), ("sao joao del rei", "São João del-Rei"), ("Sao Joao Del Rei", "São João del-Rei"),
])
def test_cidade_sem_pagina_na_olx_filtra_aqui_escrita_de_qualquer_jeito(cidade, nome):
    c, sim, _ = cliente()
    ids, (j,) = todas(c, cidade=cidade)
    assert set(ids) == gabarito(cidade=nome) and ids
    assert sim.urls_de_listagem == [url_da_olx(sf=1)]
    assert "cidade" in j["filtros_locais"] and codigos(j) == ["filtro_aproximado"]
    assert j["cortados_por_filtro"] == {"cidade": 30 - len(ids)}


def test_cidade_fora_da_regiao_escolhida_nao_traz_carro_de_outro_lugar():
    c, sim, _ = cliente()
    ids, (j,) = todas(c, regiao=JF, cidade="Contagem")
    assert ids == [] and sim.urls_de_listagem == [url_da_olx(f"estado-mg/{JF}", sf=1)]
    assert "cidade" in j["filtros_locais"]
    assert j["informacao"] == "Não achei nenhum carro com esses filtros. Que tal afrouxar algum?"


def test_cidade_no_brasil_todo_filtra_aqui():
    c, sim, _ = cliente()
    ids, (j,) = todas(c, estado="todos", cidade="rio de janeiro")
    assert set(ids) == gabarito(estado=None, cidade="Rio de Janeiro") == {8, 25}
    assert sim.urls_de_listagem == [url_da_olx(None, sf=1)] and "cidade" in j["filtros_locais"]


# ---------------------------------------------------------------------------
# Ano, preço e km
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("filtro,de,ate", [
    ("ano", 2018, None), ("ano", None, 2015), ("ano", 2016, 2019), ("ano", 1995, 1995),
    ("preco", 100000, None), ("preco", None, 50000), ("preco", 60000, 130000), ("preco", 100000, 100000),
])
def test_ano_e_preco_vao_na_olx_e_valem_com_as_bordas(filtro, de, ate):
    c, sim, _ = cliente()
    pedido = {k: v for k, v in ((f"{filtro}_min", de), (f"{filtro}_max", ate)) if v is not None}
    ids, (j,) = todas(c, **pedido)
    assert set(ids) == gabarito(**{filtro: (de, ate)}) and ids
    p = params(sim.urls_de_listagem[0])
    nome_de, nome_ate = {"ano": ("rs", "re"), "preco": ("ps", "pe")}[filtro]
    assert p.get(nome_de) == (str(de) if de is not None else None)
    assert p.get(nome_ate) == (str(ate) if ate is not None else None)
    assert filtro in j["filtros_na_origem"] and j["cortados_por_filtro"] == {}


def test_ano_igual_e_preco_igual_trazem_so_o_carro_exato():
    c, _, _ = cliente()
    assert todas(c, ano_min=1995, ano_max=1995)[0] == [19]
    assert todas(c, preco_min=100000, preco_max=100000)[0] == [23]


def test_ano_e_preco_deixam_de_fora_o_anuncio_sem_esse_dado():
    c, _, _ = cliente()
    assert 34 not in todas(c, ano_min=1900)[0]  # o Fusca não diz o ano
    assert 27 not in todas(c, preco_max=10**9)[0]  # o Uno não diz o preço


@pytest.mark.parametrize("km_min,km_max,ms,me", [
    (None, 55000, None, "60000"),  # a OLX só aceita degraus: pede o de cima e corta aqui o que passou
    (45000, None, "40000", None),  # no mínimo, o degrau de baixo
    (None, 0, None, "0"),
    (60000, 60000, "60000", "60000"),
    (None, 500000, None, "500000"),
    (None, 500001, None, None),  # acima do último degrau só daqui
    (None, 900000, None, None),
    (0, None, None, None),  # mínimo 0 não filtra nada na OLX
])
def test_km_vai_no_degrau_da_olx_e_o_valor_exato_vale_aqui(km_min, km_max, ms, me):
    c, sim, _ = cliente()
    pedido = {k: v for k, v in (("km_min", km_min), ("km_max", km_max)) if v is not None}
    ids, (j,) = todas(c, **pedido)
    assert set(ids) == gabarito(km=(km_min, km_max)) and ids
    p = params(sim.urls_de_listagem[0])
    assert p.get("ms") == ms and p.get("me") == me
    da_olx = gabarito(km=(int(ms) if ms else None, int(me) if me else None))
    assert j["cortados_por_filtro"] == {"km": len(da_olx - set(ids))}
    assert "km" in j["filtros_locais"]


def test_km_cortado_aqui_e_contado_certo():
    c, _, _ = cliente()
    ids, (j,) = todas(c, km_max=55000)
    assert 20 in ids and 14 not in ids and 5 not in ids  # 55 mil passa, 58 mil e 60 mil não
    assert j["cortados_por_filtro"] == {"km": 2}
    ids, (j,) = todas(c, km_min=45000)
    assert 2 in ids and 9 not in ids  # 45 mil passa, 40 mil não
    assert todas(c, km_max=0)[0] == [26] and todas(c, km_min=60000, km_max=60000)[0] == [5]


# ---------------------------------------------------------------------------
# Câmbio, combustível e anunciante
# ---------------------------------------------------------------------------


def _codigo(mapa, rotulo):
    return next(k for k, v in mapa.items() if v == rotulo)


@pytest.mark.parametrize("opcao", CAMBIOS)
def test_cambio(opcao):
    c, sim, _ = cliente()
    ids, (j,) = todas(c, cambio=opcao)
    assert set(ids) == gabarito(cambio=opcao) and ids
    assert params(sim.urls_de_listagem[0])["gb"] == _codigo(CAMBIO_OLX, CAMBIO[opcao])
    assert "cambio" in j["filtros_na_origem"] and "cambio" not in j["filtros_locais"]


@pytest.mark.parametrize("opcao", COMBUSTIVEIS)
def test_combustivel(opcao):
    c, sim, _ = cliente()
    ids, (j,) = todas(c, combustivel=opcao)
    assert set(ids) == gabarito(combustivel=opcao) and ids
    assert params(sim.urls_de_listagem[0])["fu"] == _codigo(COMBUSTIVEL_OLX, COMBUSTIVEL[opcao])
    assert "combustivel" in j["filtros_na_origem"] and "combustivel" not in j["filtros_locais"]


@pytest.mark.parametrize("opcao", ANUNCIANTES)
def test_anunciante(opcao):
    c, sim, _ = cliente()
    ids, (j,) = todas(c, anunciante=opcao)
    assert set(ids) == gabarito(anunciante=opcao) and ids
    assert params(sim.urls_de_listagem[0])["f"] == ("c" if opcao == "profissional" else "p")
    assert "anunciante" in j["filtros_na_origem"] and "anunciante" not in j["filtros_locais"]


def test_particular_e_profissional_nunca_se_misturam():
    c, _, _ = cliente()
    particular, profissional = set(todas(c, anunciante="particular")[0]), set(todas(c, anunciante="profissional")[0])
    assert particular and profissional and not particular & profissional
    assert particular | profissional == MG - {33}  # o Celta não diz quem anuncia, então não entra em nenhum


@pytest.mark.parametrize("campo,escrito,opcao", [
    ("cambio", "Automático", "automatico"), ("cambio", " semi automatico ", "semi-automatico"),
    ("cambio", "SEMI-AUTOMÁTICO", "semi-automatico"), ("combustivel", "Álcool", "alcool"),
    ("combustivel", "Elétrico", "eletrico"), ("combustivel", "HÍBRIDO", "hibrido"), ("anunciante", "Profissional", "profissional"),
])
def test_opcao_escrita_de_outro_jeito_vale_igual(campo, escrito, opcao):
    c, _, fonte = cliente()
    ids, (j,) = todas(c, **{campo: escrito})
    assert set(ids) == gabarito(**{campo: opcao}) and j["busca"][campo] == opcao
    assert todas(c, **{campo: opcao})[1][0]["do_cache"] is True and fonte.abertas == 1  # mesma busca, mesmo cache


# ---------------------------------------------------------------------------
# Marca, modelo, versão e texto
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("marca,chave", [
    ("Honda", "honda"), ("volkswagen", "vw"), ("GM", "gm"), ("chevrolet", "gm"), ("Toyota", "toyota"),
    ("BYD", "byd"), ("mercedes", "mercedes"), ("  FIAT ", "fiat"),
])
def test_marca_que_a_olx_conhece_vai_pelo_codigo(marca, chave):
    c, sim, _ = cliente()
    ids, (j,) = todas(c, marca=marca)
    assert set(ids) == gabarito(marca=chave) and ids
    p = params(sim.urls_de_listagem[0])
    assert p["vb"] == MARCAS[chave][2] and "q" not in p
    assert "marca" in j["filtros_na_origem"] and "marca" not in j["filtros_locais"] and j["avisos"] == []


def test_marca_ambigua_filtra_aqui_e_avisa():
    c, sim, _ = cliente()
    ids, (j,) = todas(c, marca="VW")  # a OLX tem 'VW' e 'Volkswagen'
    assert set(ids) == gabarito(marca="vw") and ids
    assert "vb" not in params(sim.urls_de_listagem[0])
    assert "marca" in j["filtros_locais"] and codigos(j) == ["filtro_aproximado"]
    assert "a marca VW" in j["avisos"][0]["mensagem"]


def test_marca_que_nao_existe_nao_traz_nada_e_avisa():
    c, _, _ = cliente()
    ids, (j,) = todas(c, marca="Ferrari do Paraguai")
    assert ids == [] and codigos(j) == ["filtro_aproximado"]
    assert j["informacao"] == "Não achei nenhum carro com esses filtros. Que tal afrouxar algum?"


@pytest.mark.parametrize("modelo,rotulo,vm", [
    ("Civic", "Civic", "3"), ("hrv", "HR-V", "9"), ("hr-v", "HR-V", "9"), ("HR V", "HR-V", "9"),
    ("cr-v", "CR-V", "4"), ("FIT", "Fit", "5"),
])
def test_modelo_com_marca_vai_pelo_codigo(modelo, rotulo, vm):
    c, sim, _ = cliente()
    ids, (j,) = todas(c, marca="Honda", modelo=modelo)
    assert set(ids) == gabarito(marca="honda", modelo=rotulo) and ids
    p = params(sim.urls_de_listagem[0])
    assert (p["vb"], p["vm"]) == ("33", vm) and "q" not in p
    assert j["filtros_locais"] == [] and j["avisos"] == []


@pytest.mark.parametrize("modelo,esperado,qs", [
    ("Civic", gabarito(modelo="Civic"), ["Civic"]),
    ("Corolla", {23, 24}, ["Corolla"]),
    ("hrv", {9}, ["hrv", None]),  # a OLX não acha 'hrv' no texto (só 'hr-v'): pede de novo sem ele e filtra aqui
    ("up", {17}, ["up", None]),  # o anúncio diz 'up!'
])
def test_modelo_sem_marca_vai_como_texto_e_volta_sem_ele_se_nao_achar(modelo, esperado, qs):
    c, sim, _ = cliente()
    ids, (j,) = todas(c, modelo=modelo)
    assert set(ids) == esperado
    assert [params(u).get("q") for u in sim.urls_de_listagem] == qs
    assert "modelo" in j["filtros_locais"] and codigos(j) == ["filtro_aproximado"]


@pytest.mark.parametrize("modelo,qs", [("T-Cross", ["T-Cross"]), ("tcross", ["tcross", None]), ("t cross", ["t cross", None])])
def test_marca_e_modelo_que_a_olx_nao_resolve_vao_como_texto_e_filtro_daqui(modelo, qs):
    c, sim, _ = cliente()
    ids, (j,) = todas(c, marca="VW", modelo=modelo)
    assert set(ids) == gabarito(marca="vw", modelo="T-Cross") == {13, 14}
    assert [params(u).get("q") for u in sim.urls_de_listagem] == qs
    assert {"marca", "modelo"} <= set(j["filtros_locais"])


def test_versao_pelo_nome_exato_vai_pelo_codigo():
    c, sim, _ = cliente()
    versao = "Sedan EXL 2.0 Flex 16V Aut.4p"
    ids, (j,) = todas(c, marca="Honda", modelo="Civic", versao=versao)
    assert set(ids) == gabarito(marca="honda", modelo="Civic", versao=versao) == {1}
    assert params(sim.urls_de_listagem[0])["vv"] == "34" and j["filtros_locais"] == []
    c, _, _ = cliente()
    assert set(todas(c, marca="Honda", modelo="Civic", versao=versao, estado="todos")[0]) == {1, 8}


def test_versao_que_serve_pra_varias_filtra_aqui_e_avisa():
    c, sim, _ = cliente()
    ids, (j,) = todas(c, marca="Honda", modelo="Civic", versao="exl")
    assert set(ids) == gabarito(marca="honda", modelo="Civic", versao="exl") == {1}
    assert "vv" not in params(sim.urls_de_listagem[0]) and "versao" in j["filtros_locais"]
    assert codigos(j) == ["filtro_aproximado"] and "a versão exl" in j["avisos"][0]["mensagem"]


def test_versao_sem_modelo_filtra_aqui():
    c, _, _ = cliente()
    ids, (j,) = todas(c, versao="touring")
    assert set(ids) == gabarito(versao="touring") == {2, 35}
    assert "versao" in j["filtros_locais"]


def test_modelo_com_versao_no_mesmo_campo_usa_o_nome_exato_da_olx():
    """'civic touring' acha o Civic e a versão chamada exatamente Touring. O Sedan Touring fica de fora: é a
    regra de não chutar quando a versão bate com um nome da lista."""
    c, sim, _ = cliente()
    ids, (j,) = todas(c, marca="Honda", modelo="civic touring")
    assert set(ids) == {35}
    p = params(sim.urls_de_listagem[0])
    assert (p["vm"], p["vv"]) == ("3", "42") and j["filtros_locais"] == []


@pytest.mark.parametrize("texto,q,esperado", [
    ("civic", "civic", gabarito(texto="civic")),
    ("  Civic   EXL ", "Civic EXL", {1}),
    ("corolla hybrid", "corolla hybrid", {24}),
    ("palavra que nenhum carro tem", "palavra que nenhum carro tem", set()),
])
def test_texto_vai_na_olx(texto, q, esperado):
    c, sim, _ = cliente()
    ids, (j,) = todas(c, texto=texto)
    assert set(ids) == esperado
    assert [params(u)["q"] for u in sim.urls_de_listagem] == [q]  # o texto da pessoa nunca é trocado
    assert j["busca"]["texto"] == q


# ---------------------------------------------------------------------------
# Ordenação e Ver mais
# ---------------------------------------------------------------------------


def test_ordenacao_muda_a_ordem_e_manda_o_codigo_certo():
    ordens = {}
    for ordenar, esperado in (("recentes", {"sf": "1"}), ("menor_preco", {"sp": "1"}), ("relevancia", {})):
        c, sim, _ = cliente()
        ids, _ = todas(c, ordenar=ordenar)
        assert set(ids) == MG
        p = params(sim.urls_de_listagem[0])
        assert {k: v for k, v in p.items() if k in ("sf", "sp")} == esperado
        ordens[ordenar] = ids
    por_id = {c.id: c for c in BASE}
    assert ordens["recentes"] == sorted(MG, key=lambda i: -por_id[i].data)
    precos = [por_id[i].preco for i in ordens["menor_preco"]]
    assert precos[-1] is None and precos[:-1] == sorted(precos[:-1])  # sem preço vai pro fim
    assert ordens["relevancia"] == [c.id for c in BASE if c.id in MG]
    assert len({tuple(v) for v in ordens.values()}) == 3


@pytest.mark.parametrize("ordenar,codigo", [("", "sf"), ("Menor_Preco", "sp"), (" RECENTES ", "sf")])
def test_ordenacao_escrita_de_outro_jeito(ordenar, codigo):
    c, sim, _ = cliente()
    todas(c, ordenar=ordenar)
    assert params(sim.urls_de_listagem[0])[codigo] == "1"


def test_ver_mais_vai_ate_o_fim_sem_repetir_e_sem_perder_carro():
    c, sim, _ = cliente(GRANDE)
    ids, (j1, j2) = todas(c)
    assert len(ids) == len(set(ids)) == 85 and set(ids) == gabarito(GRANDE)
    assert [len(j1["anuncios"]), len(j2["anuncios"])] == [50, 35]
    assert params(sim.urls_de_listagem[1])["o"] == "2"
    assert j1["tem_mais"] and j1["proxima_pagina"] == 2 and not j2["tem_mais"]
    assert j1["informacao"] == "Mostrando 50 de 85 carros. Toca em Ver mais pra ver o resto."
    assert j2["informacao"] == "Achei 85 carros. Esses são todos."


def test_pagina_sem_carro_que_sirva_ainda_deixa_procurar_no_resto():
    c, _, _ = cliente(GRANDE)
    ids, (j1, j2) = todas(c, cidade="Belo Horizonte")  # a 1ª página da OLX só tem Uno de Contagem e Betim
    assert j1["anuncios"] == [] and j1["tem_mais"] and j1["proxima_pagina"] == 2
    assert j1["informacao"] == "Ainda não achei carro com esses filtros. Toca em Ver mais pra procurar no resto."
    assert set(ids) == gabarito(GRANDE, cidade="Belo Horizonte") and len(ids) == 11
    assert j2["cortados_por_filtro"] == {"cidade": 35 - 11}


def test_modelo_sem_marca_e_procurado_em_todas_as_paginas():
    c, sim, _ = cliente(GRANDE)
    ids, (j1, j2) = todas(c, modelo="hrv")
    assert ids == [9] and j1["anuncios"] == [] and j1["tem_mais"]
    assert [(params(u).get("q"), params(u).get("o")) for u in sim.urls_de_listagem] == [("hrv", None), (None, None), (None, "2")]


def test_filtros_valem_igual_no_buscar_de_uma_vez():
    c, _, _ = cliente(GRANDE)
    pedido = {"texto": "", "regiao": BH, "cambio": "manual", "anunciante": "profissional", "km_max": 130000}
    j = c.get("/buscar", params=pedido).json()
    esperado = gabarito(GRANDE, regiao=BH, cambio="manual", anunciante="profissional", km=(None, 130000))
    assert {int(a["external_id"]) for a in j["anuncios"]} == esperado and esperado
    assert set(todas(cliente(GRANDE)[0], **{k: v for k, v in pedido.items() if k != "texto"})[0]) == esperado


# ---------------------------------------------------------------------------
# Vários filtros juntos
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("pedido,esperado", [
    (
        {"regiao": BH, "cambio": "automatico", "combustivel": "flex", "anunciante": "profissional",
         "preco_max": 140000, "ano_min": 2017},
        {4, 9, 13, 23, 26},
    ),
    ({"marca": "Honda", "modelo": "Civic", "ano_min": 2016, "ano_max": 2020, "km_max": 90000, "estado": "todos"}, {1, 2, 4, 5, 8, 35}),
    ({"cidade": "Belo Horizonte", "cambio": "manual", "km_max": 100000}, {11}),
    ({"regiao": BH, "zona": "barreiro", "anunciante": "particular", "combustivel": "flex"}, {1, 14, 32}),
    ({"texto": "civic", "cambio": "manual"}, {5, 7}),
    ({"marca": "VW", "combustivel": "alcool"}, {19}),
    ({"marca": "Toyota", "cidade": "Betim", "preco_min": 100000, "preco_max": 180000}, {23, 24}),
    ({"regiao": JF, "combustivel": "diesel", "anunciante": "profissional", "ano_max": 2018}, {22}),
    ({"anunciante": "particular", "combustivel": "eletrico"}, set()),
])
def test_combinacoes(pedido, esperado):
    c, _, _ = cliente()
    ids, respostas = todas(c, **pedido)
    assert set(ids) == esperado and len(ids) == len(set(ids))
    if not esperado:
        assert respostas[-1]["informacao"] == "Não achei nenhum carro com esses filtros. Que tal afrouxar algum?"


def test_combinacoes_batem_com_o_gabarito():
    casos = [
        dict(regiao=BH, cambio="automatico", combustivel="flex", anunciante="profissional", preco=(None, 140000), ano=(2017, None)),
        dict(estado=None, marca="honda", modelo="Civic", ano=(2016, 2020), km=(None, 90000)),
        dict(cidade="Belo Horizonte", cambio="manual", km=(None, 100000)),
        dict(regiao=BH, zona="barreiro", anunciante="particular", combustivel="flex"),
        dict(texto="civic", cambio="manual"),
        dict(marca="vw", combustivel="alcool"),
    ]
    assert [gabarito(**k) for k in casos] == [{4, 9, 13, 23, 26}, {1, 2, 4, 5, 8, 35}, {11}, {1, 14, 32}, {5, 7}, {19}]


def test_menor_preco_com_filtros_sai_em_ordem():
    c, _, _ = cliente()
    ids, _ = todas(c, regiao=BH, anunciante="profissional", ordenar="menor_preco")
    por_id = {c.id: c for c in BASE}
    assert set(ids) == gabarito(regiao=BH, anunciante="profissional")
    assert [por_id[i].preco for i in ids] == sorted(por_id[i].preco for i in ids)


# ---------------------------------------------------------------------------
# Campos vazios, valores inválidos e casos extremos
# ---------------------------------------------------------------------------

VAZIOS = {
    "marca": "", "modelo": " ", "versao": "  ", "cidade": "", "regiao": " ", "zona": "", "cambio": "",
    "combustivel": " ", "anunciante": "", "ordenar": "", "estado": "", "ano_min": "", "ano_max": " ",
    "preco_min": "", "preco_max": "", "km_min": "", "km_max": " ",
}


def test_campos_vazios_valem_como_nao_preenchidos():
    c, sim, fonte = cliente()
    sem_filtro = pagina(c).json()
    j = pagina(c, texto="   ", **VAZIOS).json()
    assert j["busca"] == sem_filtro["busca"] and j["do_cache"] is True and fonte.abertas == 1
    assert {int(a["external_id"]) for a in j["anuncios"]} == MG
    assert sim.urls_de_listagem == [url_da_olx(sf=1)]


@pytest.mark.parametrize("campo", sorted(VAZIOS))
def test_cada_campo_vazio_sozinho_nao_quebra_a_busca(campo):
    c, sim, _ = cliente()
    r = pagina(c, **{campo: VAZIOS[campo]})
    assert r.status_code == 200 and len(r.json()["anuncios"]) == 30
    assert sim.urls_de_listagem == [url_da_olx(sf=1)]


@pytest.mark.parametrize("pedido", [
    {"estado": "XX"}, {"estado": "ZZ"}, {"estado": "MGG"}, {"estado": "M"}, {"estado": "1A"},
    {"ano_min": 2020, "ano_max": 2010}, {"preco_min": 50000, "preco_max": 10000}, {"km_min": 90000, "km_max": 1000},
    {"ano_min": -1}, {"preco_max": -100}, {"km_min": -5},
    {"ano_min": "abc"}, {"preco_max": "50 mil"}, {"km_max": "1.5"}, {"preco_min": "1e5"}, {"ano_min": "2.020"},
    {"cambio": "turbo"}, {"combustivel": "gnv"}, {"anunciante": "loja"}, {"ordenar": "barato"},
    {"estado": "todos", "regiao": BH}, {"pagina": 0}, {"pagina": "abc"},
])
def test_pedido_invalido_volta_422_e_nem_chega_na_olx(pedido):
    c, sim, fonte = cliente()
    r = pagina(c, **pedido)
    assert r.status_code == 422 and r.json() == {"erro": server.MSG_PEDIDO}
    assert fonte.abertas == 0 and sim.urls == []


@pytest.mark.parametrize("pedido,mensagem", [
    ({"regiao": "regiao-que-nao-existe"}, server.MSG_REGIAO),
    ({"estado": "SP", "regiao": BH}, server.MSG_REGIAO),
    ({"regiao": BH, "zona": "zona-que-nao-existe"}, server.MSG_ZONA),
    ({"regiao": JF, "zona": "barreiro"}, server.MSG_ZONA),
    ({"zona": "barreiro"}, server.MSG_ZONA_SEM_REGIAO),
])
def test_local_invalido_explica_o_que_fazer(pedido, mensagem):
    c, sim, fonte = cliente()
    r = pagina(c, **pedido)
    assert r.status_code == 422 and r.json() == {"erro": mensagem}
    assert fonte.abertas == 0 and sim.urls == []


@pytest.mark.parametrize("estado", sorted(ESTADOS))
def test_todo_estado_do_brasil_vale(estado):
    assert Busca(texto="", estado=estado.lower()).estado == estado


def test_sigla_que_nao_e_estado_nao_vale():
    for sigla in ("XX", "BR", "ZZ"):
        with pytest.raises(ValidationError):
            Busca(texto="", estado=sigla)


def test_estados_aceitos_sao_os_da_lista_de_locais():
    assert set(ESTADOS) == set(localidades._dados()["estados"]) and len(ESTADOS) == 27


TELA = RAIZ.parent / "apps" / "web" / "src" / "busca" / "pedido.ts"
com_a_tela = pytest.mark.skipif(not TELA.exists(), reason="sem a pasta da tela")


def _da_tela(padrao):
    achado = re.search(padrao, TELA.read_text(encoding="utf-8"), re.S)
    assert achado, f"não achei {padrao!r} no pedido.ts"
    return achado.group(1)


def _opcoes_da_tela(nome):
    bloco = _da_tela(rf"export const {nome} = \[(.*?)\] as const")
    return re.findall(r"\[\s*'([^']*)'\s*,\s*'[^']*'\s*\]", bloco)


@com_a_tela
@pytest.mark.parametrize("nome,servidor,qualquer", [
    ("CAMBIOS", CAMBIOS, ""), ("COMBUSTIVEIS", COMBUSTIVEIS, ""), ("ANUNCIANTES", ANUNCIANTES, ""),
    ("ESTADOS", ESTADOS, "todos"), ("ORDENS", ORDENS, None),
])
def test_opcoes_da_tela_sao_as_que_o_servidor_aceita(nome, servidor, qualquer):
    """Opção que só a tela tem dá 422. Opção que só o servidor tem a pessoa nunca consegue escolher."""
    tela = _opcoes_da_tela(nome)
    if qualquer is not None:
        assert tela[0] == qualquer
        tela = tela[1:]
    assert len(tela) == len(set(tela)) and set(tela) == set(servidor)


@com_a_tela
def test_campos_da_tela_sao_os_do_servidor():
    """O servidor ignora parâmetro que não conhece. Nome diferente dos dois lados faria o filtro sumir calado."""
    tela = set(re.findall(r"^\s+(\w+)\??:", _da_tela(r"export interface Pedido \{(.*?)\n\}"), re.M))
    c, _, _ = cliente()
    na_api = {p["name"] for p in c.app.openapi()["paths"]["/buscar/pagina"]["get"]["parameters"]}
    assert len(tela) == 18 and tela == set(Busca.model_fields) and tela <= na_api


@com_a_tela
def test_padroes_da_tela_valem_no_servidor():
    assert _da_tela(r"export const ESTADO_PADRAO = '(\w+)'") in ESTADOS
    assert _da_tela(r"RASCUNHO_VAZIO: Rascunho = \{.*?ordenar: '(\w+)'") == ORDEM_PADRAO


@pytest.mark.parametrize("pedido,esperado", [
    ({"preco_min": 999_999_999}, set()),
    ({"ano_min": 1900, "ano_max": 2100}, MG - {34}),
    ({"ano_min": 2100}, set()),
    ({"km_min": 500000}, set()),
    ({"preco_max": 0}, set()),
    ({"ano_min": "99999999999999999999999"}, set()),
])
def test_extremos(pedido, esperado):
    c, _, _ = cliente()
    ids, respostas = todas(c, **pedido)
    assert set(ids) == esperado


def test_extremos_nao_quebram_a_frase():
    c, _, _ = cliente()
    _, (j,) = todas(c, preco_min=999_999_999)
    assert j["informacao"] == "Não achei nenhum carro com esses filtros. Que tal afrouxar algum?" and not j["tem_mais"]


def test_cada_filtro_muda_o_resultado():
    """Nenhum filtro é enfeite: sozinho, cada um traz menos carros do que a busca sem filtro."""
    pedidos = [
        {"estado": "SP"}, {"regiao": JF}, {"regiao": BH, "zona": "pampulha"}, {"cidade": "Contagem"},
        {"marca": "Honda"}, {"modelo": "Corolla"}, {"versao": "touring"}, {"texto": "civic"},
        {"ano_min": 2020}, {"ano_max": 2015}, {"preco_min": 100000}, {"preco_max": 50000},
        {"km_min": 100000}, {"km_max": 50000}, {"cambio": "manual"}, {"combustivel": "diesel"},
        {"anunciante": "particular"}, {"anunciante": "profissional"},
    ]
    for pedido in pedidos:
        c, _, _ = cliente()
        ids = set(todas(c, **pedido)[0])
        assert ids and ids != MG, pedido


# ---------------------------------------------------------------------------
# O filtro daqui sozinho (vale para qualquer fonte)
# ---------------------------------------------------------------------------

ANUNCIOS = [olx.normalizar(c.cru()) for c in BASE]


@pytest.mark.parametrize("procurado,valor,casa", [
    ("hrv", "HR-V EXL 1.8", True), ("hr v", "HR-V", True), ("hr-v", "HR-V", True), ("HRV", "hr-v", True),
    ("tcross", "T-Cross Highline", True), ("t cross", "T-Cross", True), ("t-cross", "TCross", True),
    ("1,5", "City EXL 1.5 CVT", True), ("1.5", "City EXL 1.5 CVT", True), ("15", "City 1.5", False),
    ("1.5", "City 1.6 15V", False), ("up", "up! take 1.0", True), ("up", "Upgrade 2.0", False),
    ("gol", "Golf GTI", False), ("gol", "Gol 1.0", True), ("volkswagen", "VW - VolksWagen", True),
    ("vw", "VW - VolksWagen", True), ("chevrolet", "GM - Chevrolet", True), ("são joão", "Sao Joao del-Rei", True),
    ("civic", None, False), ("", "Civic", False), ("!!", "Civic", False), ("civic", "", False),
])
def test_contem(procurado, valor, casa):
    assert _contem(procurado, valor) is casa


@pytest.mark.parametrize("procuradas,valor,casa", [
    ("ex l", "Sedan EXL 2.0", True), ("exl 2.0", "Civic Sedan EXL 2.0 Flex", True),
    ("2.0 exl", "Civic Sedan EXL 2.0 Flex", True), ("exl 1.5", "Civic Sedan EXL 2.0 Flex", False),
    ("touring", "Civic Sed.touring 2.0 16V Aut. (híbrido)", True), ("16v", "Sedan EX 2.0 16V", True),
])
def test_tem_todas(procuradas, valor, casa):
    assert _tem_todas(procuradas, valor) is casa


@pytest.mark.parametrize("campo,opcao", [
    *(("cambio", o) for o in CAMBIOS), *(("combustivel", o) for o in COMBUSTIVEIS), *(("anunciante", o) for o in ANUNCIANTES),
])
def test_filtro_daqui_de_cada_opcao(campo, opcao):
    aprovados, cortados = filtrar_local_contando(ANUNCIOS, Busca(texto="", **{campo: opcao}))
    assert {int(a.external_id) for a in aprovados} == gabarito(estado=None, **{campo: opcao})
    assert cortados == {campo: len(BASE) - len(aprovados)}


def test_filtro_daqui_respeita_o_que_a_fonte_ja_aplicou():
    busca = Busca(texto="", cambio="manual", combustivel="flex", anunciante="particular")
    aprovados, cortados = filtrar_local_contando(ANUNCIOS, busca, ignorar=("cambio", "combustivel", "anunciante"))
    assert len(aprovados) == len(BASE) and cortados == {}


def test_filtro_daqui_com_tudo_junto_conta_cada_corte_uma_vez():
    busca = Busca(
        texto="", marca="honda", modelo="civic", versao="exl", cidade="belo horizonte", estado="MG",
        ano_min=2015, ano_max=2020, preco_min=90000, preco_max=120000, km_min=50000, km_max=90000,
        cambio="automatico", combustivel="flex", anunciante="particular",
    )
    aprovados, cortados = filtrar_local_contando(ANUNCIOS, busca)
    assert [a.external_id for a in aprovados] == ["1"]
    assert sum(cortados.values()) == len(BASE) - 1
    assert set(cortados) == {
        "marca", "modelo", "versao", "cidade", "estado", "ano", "preco", "km", "cambio", "combustivel", "anunciante",
    }


def test_filtros_locais_lista_so_o_que_a_fonte_nao_fez():
    busca = Busca(texto="", cambio="manual", combustivel="flex", anunciante="particular", km_max=1000, cidade="x", estado="MG")
    assert filtros_locais(busca, ["estado", "cambio", "combustivel", "anunciante"]) == ["cidade", "km"]
    assert filtros_locais(busca, ["estado"]) == ["cidade", "km", "cambio", "combustivel", "anunciante"]


def test_frase_quando_nada_serviu():
    nada = "Não achei nenhum carro com esses filtros. Que tal afrouxar algum?"
    ainda = "Ainda não achei carro com esses filtros. Toca em Ver mais pra procurar no resto."
    assert texto_informacao(0, 0, False, 0, False) == nada
    assert texto_informacao(0, 1200, False, 50, False) == nada
    assert texto_informacao(0, 1200, True, 50, False) == ainda


# ---------------------------------------------------------------------------
# Cursor guardado no banco e busca de várias páginas
# ---------------------------------------------------------------------------


def _cursor(sim, busca):
    relogio = Relogio()
    return olx.abrir(busca, limites(), sessao=sim, dormir=relogio.dormir, relogio=relogio)


def test_cursor_guardado_continua_com_o_modelo_como_texto():
    sim = OlxSimulada(GRANDE)
    busca = Busca(texto="", modelo="Uno", estado="MG")
    primeiro = _cursor(sim, busca)
    p1 = primeiro.proxima()
    estado = json.loads(json.dumps(primeiro.exportar()))
    assert estado["texto"] == "Uno"
    segundo = _cursor(sim, busca)
    segundo.restaurar(estado)
    p2 = segundo.proxima()
    assert params(sim.urls_de_listagem[-1]) == {"q": "Uno", "o": "2", "sf": "1"}
    ids = [int(a.external_id) for a in p1.anuncios + p2.anuncios]
    assert len(ids) == len(set(ids)) == 56 and set(ids) == gabarito(GRANDE, modelo="Uno")


def test_cursor_guardado_por_versao_antiga_segue_sem_texto_e_sem_filtrar_duas_vezes(monkeypatch):
    sim = OlxSimulada(GRANDE)
    busca = Busca(texto="", modelo="Uno", cambio="manual", estado="MG")
    cursor = _cursor(sim, busca)
    with monkeypatch.context() as m:
        m.setattr(olx, "_modelo_como_texto", lambda *a: None)  # a versão antiga não mandava o modelo como texto
        cursor.proxima()
    assert "q" not in params(sim.urls_de_listagem[0])
    estado = cursor.exportar()
    del estado["texto"]
    estado["ignorar"] = ["estado", "ano_min", "ano_max", "preco_min", "preco_max"]  # o que a versão antiga guardava
    novo = _cursor(sim, busca)
    novo.restaurar(estado)
    assert {"cambio", "combustivel", "anunciante"} <= set(novo._ignorar)
    p2 = novo.proxima()
    assert "q" not in params(sim.urls_de_listagem[-1]) and params(sim.urls_de_listagem[-1])["o"] == "2"
    assert "cambio" not in p2.cortados_por_filtro


def test_buscar_paginas_tambem_volta_sem_o_texto_se_nao_achar():
    sim, relogio = OlxSimulada(BASE), Relogio()
    r = olx.buscar(Busca(texto="", modelo="hrv", estado="MG"), limites(), sessao=sim, dormir=relogio.dormir, relogio=relogio)
    assert [int(a.external_id) for a in r.anuncios] == [9]
    assert [params(u).get("q") for u in sim.urls_de_listagem] == ["hrv", None]
    assert relogio.esperas == [1.0]  # a mesma pausa de sempre antes de pedir de novo


def test_buscar_paginas_nunca_troca_o_texto_da_pessoa():
    sim, relogio = OlxSimulada(BASE), Relogio()
    r = olx.buscar(Busca(texto="xyzzy", modelo="Civic", estado="MG"), limites(), sessao=sim, dormir=relogio.dormir, relogio=relogio)
    assert r.anuncios == [] and [params(u)["q"] for u in sim.urls_de_listagem] == ["xyzzy"]


def test_modelo_resolvido_pelo_codigo_nao_vai_como_texto():
    sim, relogio = OlxSimulada(BASE), Relogio()
    r = olx.buscar(Busca(texto="", marca="Honda", modelo="HR-V", estado="MG"), limites(), sessao=sim, dormir=relogio.dormir, relogio=relogio)
    assert [int(a.external_id) for a in r.anuncios] == [9]
    p = params(sim.urls_de_listagem[0])
    assert "q" not in p and (p["vb"], p["vm"]) == ("33", "9")


# ---------------------------------------------------------------------------
# Contrato com a OLX: os códigos de câmbio, combustível e anunciante
# ---------------------------------------------------------------------------

CONTRATO = [
    *(("cambio", o, lambda a, o=o: a.cambio == CAMBIO[o]) for o in CAMBIOS),
    *(("combustivel", o, lambda a, o=o: a.combustivel == COMBUSTIVEL[o]) for o in COMBUSTIVEIS),
    ("anunciante", "particular", lambda a: a.anunciante_profissional is False),
    ("anunciante", "profissional", lambda a: a.anunciante_profissional is True),
]


def conferir_contrato(buscar):
    """Para cada opção, a 1ª página da OLX só pode trazer carros daquela opção. `buscar` recebe a Busca."""
    erros = []
    for campo, opcao, serve in CONTRATO:
        r = buscar(Busca(texto="", estado="MG", **{campo: opcao}))
        if not r.anuncios or not all(serve(a) for a in r.anuncios):
            erros.append(f"{campo}={opcao}: {len(r.anuncios)} carros, fora {sum(not serve(a) for a in r.anuncios)}")
    return erros


def test_contrato_com_a_olx_simulada():
    def buscar(busca):
        sim, relogio = OlxSimulada(BASE), Relogio()
        return olx.buscar(busca, limites(max_paginas=1), sessao=sim, dormir=relogio.dormir, relogio=relogio)

    assert len(CONTRATO) == 12 and conferir_contrato(buscar) == []


@pytest.mark.skipif(os.environ.get("OLX_LIVE") != "1", reason="ao vivo: rode com OLX_LIVE=1")
def test_ao_vivo_os_codigos_da_olx_ainda_sao_estes():
    """Uma página por opção (12 no total), com a mesma pausa da busca entre elas."""
    def buscar(busca):
        time.sleep(random.uniform(6, 14))
        return olx.buscar(busca, LimitesBusca(max_paginas=1))

    assert conferir_contrato(buscar) == []
