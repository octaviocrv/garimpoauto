"""Marca, modelo e versão filtrados na própria OLX (vb, vm, vv), com as listas reais de
tests/fixtures/olx_api_*.json. Tudo offline."""

import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from schemas import Busca  # noqa: E402
from sources import olx  # noqa: E402
from tests.test_contrato_olx import pagina_real  # noqa: E402
from tests.test_olx import Relogio, SessaoFalsa, limites  # noqa: E402

FIXTURES = RAIZ / "tests" / "fixtures"


def lista(nome):
    return json.loads((FIXTURES / f"olx_api_{nome}.json").read_text(encoding="utf-8"))


MARCAS, MODELOS, VERSOES = lista("marcas"), lista("modelos_honda"), lista("versoes_civic")
API = {
    "carbrand": MARCAS,
    "carmodel?carbrand=33": MODELOS,
    "carversion?carbrand=33&carmodel=3": VERSOES,
}


@pytest.fixture(autouse=True)
def _sem_cache_de_codigos():
    olx.limpar_cache_codigos()
    yield
    olx.limpar_cache_codigos()


def buscar(busca, respostas=None, api=API):
    sessao, relogio = SessaoFalsa(respostas or [pagina_real("olx_poucos")], api=api), Relogio()
    resultado = olx.buscar(busca, limites(), sessao=sessao, dormir=relogio.dormir, relogio=relogio)
    return resultado, sessao, relogio


@pytest.mark.parametrize("texto,esperado", [
    ("Honda", "33"), ("honda", "33"), ("  HONDA ", "33"), ("volkswagen", "75"), ("Land Rover", None),
    ("vw", None),  # 'VW' e 'Volkswagen' disputam, melhor não chutar
    ("marca que não existe", None),
])
def test_achar_marca(texto, esperado):
    item = olx.achar_marca(texto, MARCAS)
    if esperado is None and texto == "Land Rover":
        assert item and item["label"] == "Land Rover"
    else:
        assert (item["value"] if item else None) == esperado


@pytest.mark.parametrize("texto,label,resto", [
    ("civic", "Civic", ""), ("CIVIC", "Civic", ""), ("hrv", "HR-V", ""), ("hr-v", "HR-V", ""),
    ("civic touring", "Civic", "touring"), ("city 1.5", "City", "1.5"),
])
def test_achar_modelo(texto, label, resto):
    item, sobra = olx.achar_modelo(texto, MODELOS)
    assert item["label"] == label and sobra == resto


def test_modelo_desconhecido_nao_acha():
    assert olx.achar_modelo("fusca", MODELOS) == (None, "")


def test_achar_versao_exata_ou_unica_e_nao_chuta_se_tiver_varias():
    assert olx.achar_versao("touring", VERSOES)["label"] == "Touring"
    assert olx.achar_versao("sedan touring 1.5 turbo", VERSOES)["label"].startswith("Sedan Touring")
    assert olx.achar_versao("16v", VERSOES) is None  # várias versões servem


def test_marca_e_modelo_vao_para_a_olx_e_o_filtro_local_sai():
    busca = Busca(texto="civic", marca="Honda", modelo="Civic", ano_min=2018, ano_max=2018, estado="MG")
    r, sessao, _ = buscar(busca)
    assert "vb=33" in sessao.urls_de_listagem[0] and "vm=3" in sessao.urls_de_listagem[0]
    assert r.filtros_na_origem == ["estado", "ano", "marca", "modelo"]
    assert r.filtros_locais == []
    assert "marca" not in r.funil.cortados_por_filtro and "modelo" not in r.funil.cortados_por_filtro
    assert r.avisos == []  # nenhum aviso: tudo resolvido na origem
    assert all(a.marca == "Honda" and "Civic" in a.modelo_original for a in r.anuncios)


def test_versao_pedida_vai_junto_com_modelo():
    r, sessao, _ = buscar(Busca(texto="civic", marca="honda", modelo="civic", versao="touring", estado="MG"))
    assert "vb=33" in sessao.urls_de_listagem[0] and "vm=3" in sessao.urls_de_listagem[0]
    assert "vv=" in sessao.urls_de_listagem[0]
    assert {"marca", "modelo", "versao"} <= set(r.filtros_na_origem)


def test_modelo_com_resto_tenta_virar_versao():
    _, sessao, _ = buscar(Busca(texto="civic", marca="honda", modelo="civic touring"))
    assert "vm=3" in sessao.urls_de_listagem[0] and "vv=" in sessao.urls_de_listagem[0]


def test_resto_do_modelo_que_nao_vira_versao_continua_filtrando_aqui_e_avisa():
    r, sessao, _ = buscar(Busca(texto="civic", marca="honda", modelo="civic zzz"))
    assert "vm=3" in sessao.urls_de_listagem[0] and "vv=" not in sessao.urls_de_listagem[0]
    assert "modelo" in r.filtros_locais and "modelo" not in r.filtros_na_origem
    assert r.anuncios == []  # 'civic zzz' não existe em nenhum anúncio
    assert [a.codigo for a in r.avisos if a.codigo == "filtro_aproximado"] == ["filtro_aproximado"]


def test_marca_que_a_olx_nao_conhece_filtra_aqui_e_avisa():
    r, sessao, _ = buscar(Busca(texto="civic", marca="Marca Inventada"))
    assert "vb=" not in sessao.urls_de_listagem[0]
    assert r.filtros_locais == ["marca"] and r.filtros_na_origem == []
    aviso = next(a for a in r.avisos if a.codigo == "filtro_aproximado")
    assert "Marca Inventada" in aviso.mensagem and "Pode ter ficado" in aviso.mensagem
    assert all(ch not in aviso.mensagem for ch in ("—", "–", ";")) and ":" not in aviso.mensagem


def test_modelo_sem_marca_nao_da_para_resolver_e_filtra_aqui():
    r, sessao, _ = buscar(Busca(texto="civic", modelo="civic"))
    assert not any("/api/filters/" in u for u in sessao.urls)
    assert r.filtros_locais == ["modelo"]
    assert any(a.codigo == "filtro_aproximado" for a in r.avisos)


def test_api_de_filtros_fora_do_ar_nao_quebra_a_busca():
    r, _, _ = buscar(Busca(texto="civic", marca="Honda"), api={})
    assert r.motivo_parada == "acabaram_paginas" and r.filtros_locais == ["marca"]
    assert any(a.codigo == "filtro_aproximado" for a in r.avisos)
    assert len(r.anuncios) == 10  # as 10 do Honda Civic passam no filtro local


def test_listas_ficam_em_memoria_e_a_segunda_busca_nao_consulta_de_novo():
    busca = Busca(texto="civic", marca="Honda", modelo="Civic")
    _, primeira, _ = buscar(busca)
    _, segunda, _ = buscar(busca)
    assert sum("/api/filters/" in u for u in primeira.urls) == 2
    assert sum("/api/filters/" in u for u in segunda.urls) == 0


def test_pausa_entre_a_consulta_de_codigos_e_a_primeira_pagina():
    _, _, relogio = buscar(Busca(texto="civic", marca="Honda", modelo="Civic"))
    assert len(relogio.esperas) == 2  # marca -> modelo, modelo -> página 1
    assert all(e == 1.0 for e in relogio.esperas)  # o limites() de teste fixa a pausa em 1 s


def test_sem_marca_nem_modelo_nao_consulta_nada():
    _, sessao, relogio = buscar(Busca(texto="civic"))
    assert not any("/api/filters/" in u for u in sessao.urls) and relogio.esperas == []
