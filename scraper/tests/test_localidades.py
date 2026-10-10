"""Região e cidade na própria URL da OLX, com a árvore de locais de dados_olx/localidades.json."""

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import localidades  # noqa: E402
from schemas import Busca  # noqa: E402
from sources import olx  # noqa: E402

BH = "belo-horizonte-e-regiao"
CONTAGEM = f"{BH}/grande-belo-horizonte/contagem"


def test_os_dados_cobrem_os_27_estados_e_as_7_regioes_de_minas():
    d = localidades._dados()["estados"]
    assert len(d) == 27
    assert set(d["MG"]) == {
        BH, "regiao-de-divinopolis", "regiao-de-governador-valadares-e-teofilo-otoni", "regiao-de-juiz-de-fora",
        "regiao-de-montes-claros-e-diamantina", "regiao-de-pocos-de-caldas-e-varginha", "regiao-de-uberlandia-e-uberaba",
    }


@pytest.mark.parametrize("texto", [BH, "Belo Horizonte e região", "belo horizonte e regiao", "  BELO-HORIZONTE-E-REGIAO ", "Belo Horizonte"])
def test_achar_regiao_aceita_slug_nome_sem_acento_e_nome_curto(texto):
    assert localidades.achar_regiao("MG", texto) == BH


@pytest.mark.parametrize("uf,texto", [("MG", "Marte"), ("MG", ""), ("MG", "Brasil"), ("SP", BH), (None, BH)])
def test_regiao_que_a_olx_nao_tem_no_estado_nao_e_aceita(uf, texto):
    assert localidades.achar_regiao(uf, texto) is None


def test_lista_de_regioes_para_o_seletor_vem_em_ordem_e_com_nome():
    lista = localidades.regioes("MG")
    assert len(lista) == 7 and all(r["slug"] and r["nome"] for r in lista)
    nomes = [r["nome"] for r in lista]
    assert nomes == sorted(nomes, key=lambda n: localidades._sem_simbolos(n))
    assert any(r["slug"] == BH for r in lista)


def test_nome_de_regiao_sem_dados_sai_do_endereco():
    assert localidades.nome_regiao("XX", "belo-horizonte-e-regiao") == "Belo Horizonte e região"
    assert localidades.nome_regiao("XX", "regiao-de-juiz-de-fora") == "Região de Juiz de Fora"


@pytest.mark.parametrize("texto", ["Contagem", "contagem", "  CONTAGEM "])
def test_achar_cidade(texto):
    assert localidades.achar_cidade("MG", texto) == (BH, "grande-belo-horizonte", "contagem")


def test_cidade_com_acento_e_cidade_de_outro_estado():
    assert localidades.achar_cidade("MG", "Ribeirão das Neves")[2] == "ribeirao-das-neves"
    assert localidades.achar_cidade("SP", "Contagem") is None


def test_cidade_sem_pagina_propria_na_olx_nao_e_resolvida():
    assert localidades.achar_cidade("MG", "Belo Horizonte") is None  # a capital é dividida em zonas
    assert localidades.achar_cidade("MG", "Cidade Que Nao Existe") is None


def test_nome_que_serve_para_dois_lugares_nao_e_chutado(monkeypatch):
    dados = {"estados": {"ZZ": {"r1": {"z1": ["centro"], "z2": ["centro"]}}}, "nomes": {}}
    monkeypatch.setattr(localidades, "_dados", lambda: dados)
    assert localidades.achar_cidade("ZZ", "centro") is None


# --- o que vai na URL ---------------------------------------------------------


def url(**kw):
    return olx.montar_url(Busca(texto="civic", **kw)).split("olx.com.br/autos-e-pecas/carros-vans-e-utilitarios")[1]


def test_regiao_vai_na_url_mesmo_escrita_de_outro_jeito():
    assert url(estado="MG", regiao="Belo Horizonte e região") == f"/estado-mg/{BH}?q=civic&sf=1"


def test_cidade_vai_na_url_com_regiao_e_zona():
    assert url(estado="MG", cidade="Contagem") == f"/estado-mg/{CONTAGEM}?q=civic&sf=1"
    assert url(estado="MG", regiao=BH, cidade="contagem") == f"/estado-mg/{CONTAGEM}?q=civic&sf=1"


def test_regiao_desconhecida_nunca_vai_na_url_porque_a_olx_responderia_o_brasil_todo():
    assert url(estado="MG", regiao="regiao-de-marte") == "/estado-mg?q=civic&sf=1"


def test_cidade_sem_pagina_fica_so_na_regiao():
    assert url(estado="MG", regiao=BH, cidade="Belo Horizonte") == f"/estado-mg/{BH}?q=civic&sf=1"
    assert url(estado="MG", cidade="Belo Horizonte") == "/estado-mg?q=civic&sf=1"


def test_cidade_de_outra_regiao_nao_troca_a_regiao_pedida():
    assert url(estado="MG", regiao="regiao-de-divinopolis", cidade="Contagem") == "/estado-mg/regiao-de-divinopolis?q=civic&sf=1"


def test_sem_estado_nao_ha_local_na_url():
    assert url(cidade="Contagem") == "?q=civic&sf=1"


def resolver(**kw):
    return olx.resolver_local(Busca(texto="x", **kw))


def test_resolver_local_diz_o_que_foi_para_a_olx_e_o_que_nao_foi():
    assert resolver(estado="MG", cidade="Contagem") == (CONTAGEM, {"cidade"}, [])
    assert resolver(estado="MG", regiao=BH, cidade="Contagem") == (CONTAGEM, {"regiao", "cidade"}, [])
    assert resolver(estado="MG", regiao=BH) == (BH, {"regiao"}, [])
    assert resolver(estado="MG", regiao="marte") == (None, set(), ["a região marte"])
    assert resolver(estado="MG", regiao=BH, cidade="Belo Horizonte") == (BH, {"regiao"}, ["a cidade Belo Horizonte"])
    assert resolver(cidade="Contagem") == (None, set(), [])  # sem estado não dá para procurar


def test_sem_o_arquivo_de_locais_confia_na_regiao_que_veio(monkeypatch):
    monkeypatch.setattr(localidades, "_dados", lambda: {"estados": {}, "nomes": {}})
    assert url(estado="MG", regiao="qualquer-coisa-e-regiao") == "/estado-mg/qualquer-coisa-e-regiao?q=civic&sf=1"


# --- zonas (entre a região e a cidade) -----------------------------------------


def test_belo_horizonte_tem_as_9_zonas_da_capital_na_lista():
    slugs = {z["slug"] for z in localidades.zonas("MG", BH)}
    assert {"barreiro", "pampulha", "venda-nova", "zona-centro-sul", "zona-leste", "zona-nordeste", "zona-noroeste", "zona-norte", "zona-oeste"} <= slugs
    assert "grande-belo-horizonte" in slugs  # as cidades da região ficam em outra zona


def test_lista_de_zonas_vem_em_ordem_e_cada_uma_com_nome():
    lista = localidades.zonas("MG", BH)
    assert all(z["slug"] and z["nome"] for z in lista)
    assert [z["nome"] for z in lista] == sorted((z["nome"] for z in lista), key=localidades._sem_simbolos)


def test_nome_da_zona_sem_titulo_da_olx_sai_do_endereco():
    assert localidades.nome_zona("XX", "r", "zona-centro-sul") == "Zona Centro Sul"
    assert localidades.nome_zona("XX", "r", "regiao-de-sete-lagoas") == "Região de Sete Lagoas"


@pytest.mark.parametrize("texto", ["barreiro", "Barreiro", " BARREIRO "])
def test_achar_zona(texto):
    assert localidades.achar_zona("MG", BH, texto) == "barreiro"


def test_achar_zona_pelo_nome_com_ou_sem_acento_e_hifen():
    assert localidades.achar_zona("MG", BH, "zona-centro-sul") == "zona-centro-sul"
    assert localidades.achar_zona("MG", BH, "Zona Centro Sul") == "zona-centro-sul"


def test_zona_que_nao_e_daquela_regiao_nao_e_aceita():
    assert localidades.achar_zona("MG", "regiao-de-divinopolis", "barreiro") is None
    assert localidades.achar_zona("MG", BH, "zona-marciana") is None
    assert localidades.achar_zona("MG", "regiao-que-nao-existe", "barreiro") is None
    assert localidades.achar_zona("MG", BH, "") is None


def test_zona_vai_na_url_depois_da_regiao():
    assert url(estado="MG", regiao=BH, zona="Barreiro") == f"/estado-mg/{BH}/barreiro?q=civic&sf=1"


def test_zona_que_nao_existe_nunca_vai_na_url():
    assert url(estado="MG", regiao=BH, zona="zona-marciana") == f"/estado-mg/{BH}?q=civic&sf=1"


def test_zona_sem_regiao_nao_vira_pedido():
    with pytest.raises(ValueError):
        Busca(texto="x", estado="MG", zona="barreiro")


def test_resolver_local_com_zona():
    assert resolver(estado="MG", regiao=BH, zona="barreiro") == (f"{BH}/barreiro", {"regiao", "zona"}, [])
    assert resolver(estado="MG", regiao=BH, zona="marte") == (BH, {"regiao"}, ["a zona marte"])


def test_cidade_da_mesma_zona_vai_ate_a_cidade_e_a_de_outra_zona_fica_na_zona():
    mesma = resolver(estado="MG", regiao=BH, zona="grande-belo-horizonte", cidade="Contagem")
    assert mesma == (CONTAGEM, {"regiao", "zona", "cidade"}, [])
    outra = resolver(estado="MG", regiao=BH, zona="barreiro", cidade="Contagem")
    assert outra == (f"{BH}/barreiro", {"regiao", "zona"}, [])  # a cidade segue filtrada depois, a zona manda


def test_cidade_sozinha_continua_como_antes():
    assert resolver(estado="MG", cidade="Contagem") == (CONTAGEM, {"cidade"}, [])


def test_zona_que_o_sitemap_lista_mas_a_olx_nao_serve_fica_fora_da_lista():
    """Em Minas, 22 das 37 zonas do sitemap respondem o Brasil todo na URL. Só entram as que têm nome na OLX."""
    assert {z["slug"] for z in localidades.zonas("MG", BH)} >= {"barreiro", "pampulha"}
    assert len(localidades.zonas("MG", BH)) == 14
    assert localidades.zonas("MG", "regiao-de-divinopolis") == []
    assert localidades.achar_zona("MG", "regiao-de-divinopolis", "regiao-central-mineira") is None
    assert localidades.achar_zona("MG", "regiao-de-juiz-de-fora", "regiao-de-juiz-de-fora") is None
    assert localidades.achar_zona("MG", "regiao-de-governador-valadares-e-teofilo-otoni", "manhuacu") == "manhuacu"


def test_zona_inventada_numa_regiao_valida_nao_vai_na_url():
    assert url(estado="MG", regiao="regiao-de-divinopolis", zona="regiao-central-mineira") == "/estado-mg/regiao-de-divinopolis?q=civic&sf=1"


def test_estado_ainda_nao_conferido_usa_a_lista_do_sitemap_e_o_servidor_confere_a_primeira_pagina():
    regioes = localidades._arvore("RJ")
    regiao, zonas = next((r, z) for r, z in regioes.items() if z)
    assert [z["slug"] for z in localidades.zonas("RJ", regiao)] and "RJ" not in localidades._dados().get("zonas_conferidas", [])
