import sys
import threading
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from casamento_fipe import CasamentoFipe  # noqa: E402
from schemas import Anuncio, ReferenciaFipe  # noqa: E402
from servico_fipe import EnriquecedorFipe  # noqa: E402
from sources.fipe import FonteFipeIndisponivel, LimiteFipeAtingido  # noqa: E402
from tests.test_server import cliente  # noqa: E402


def anuncio(id_, preco=30000, **kw):
    return Anuncio(source="olx", external_id=id_, url="https://exemplo", preco=preco, **kw)


class ArmazemEstado:
    def __init__(self, fora=False):
        self.fora = fora
        self.ausencias = []

    def fipe_salvar_ausencias(self, ocorrencias):
        self.ausencias.extend(ocorrencias)


class CasadorControlado:
    def __init__(self, resultados, demora=0):
        self.resultados, self.demora = resultados, demora
        self.chamadas = []
        self.cache = {}
        self.ativas = 0
        self.max_ativas = 0
        self.trava = threading.Lock()

    def casar(self, carro):
        with self.trava:
            self.chamadas.append(carro.external_id)
            self.ativas += 1
            self.max_ativas = max(self.max_ativas, self.ativas)
        try:
            if self.demora:
                time.sleep(self.demora)
            resultado = self.resultados[carro.external_id]
            self.cache[carro.external_id] = resultado
            return resultado
        finally:
            with self.trava:
                self.ativas -= 1

    def guardado(self, carro):
        return self.cache.get(carro.external_id)

    def reaproveitar(self, carro, resultado):
        self.cache[carro.external_id] = resultado
        return resultado


class CasadorComErro:
    def __init__(self, erro):
        self.erro = erro

    def casar(self, carro):
        raise self.erro


def casamento(confianca="alta", bloqueio=None, estranho=False):
    if confianca != "alta":
        return CasamentoFipe("338", None, None, "outubro de 2026", confianca, "Sem confiança alta", bloqueio)
    return CasamentoFipe("338", "005384-8", 40000, "outubro de 2026", "alta", "Casamento exato", bloqueio, estranho)


def test_so_confianca_alta_chega_no_anuncio_e_diferenca_e_calculada():
    carros = [anuncio("alta"), anuncio("media"), anuncio("baixa")]
    casador = CasadorControlado({
        "alta": casamento(),
        "media": casamento("media"),
        "baixa": casamento("baixa", bloqueio="km_incoerente"),
    })
    enriquecedor = EnriquecedorFipe(casador, ArmazemEstado(), tempo_pagina=1)
    enriquecedor.enriquecer(carros)
    assert carros[0].fipe == ReferenciaFipe("005384-8", 40000, 25, "outubro de 2026", "alta", False)
    assert carros[0].fipe_ausencia is None
    assert carros[1].fipe is None and carros[1].fipe_ausencia == "confianca_media"
    assert (
        carros[2].fipe is None and carros[2].fipe_bloqueio == "km_incoerente"
        and carros[2].fipe_ausencia == "confianca_baixa"
    )


def test_no_maximo_duas_consultas_rodam_em_paralelo():
    carros = [anuncio(str(i)) for i in range(6)]
    casador = CasadorControlado({str(i): casamento() for i in range(6)}, demora=0.02)
    EnriquecedorFipe(casador, ArmazemEstado(), tempo_pagina=1).enriquecer(carros)
    assert casador.max_ativas == 2
    assert all(carro.fipe is not None for carro in carros)


def test_busca_resolve_uma_vez_cada_combinacao_e_reaproveita_no_grupo():
    carros = [
        anuncio(str(i), marca="VW", modelo="Gol", modelo_original="Gol 1.0", ano=2020, combustivel="flex")
        for i in range(3)
    ]
    casador = CasadorControlado({"0": casamento()})
    enriquecedor = EnriquecedorFipe(casador, ArmazemEstado(), tempo_pagina=1)
    enriquecedor.resolver_busca(carros)
    assert casador.chamadas == ["0"]
    assert all(carro.fipe is not None for carro in carros)
    assert set(casador.cache) == {"0", "1", "2"}


def test_vitrine_aplica_somente_o_casamento_que_ja_estava_guardado():
    guardado, sem_cache = anuncio("guardado"), anuncio("novo")
    casador = CasadorControlado({})
    casador.cache["guardado"] = casamento()
    enriquecedor = EnriquecedorFipe(casador, ArmazemEstado(), tempo_pagina=1)
    enriquecedor.carregar_cache([guardado, sem_cache])
    assert guardado.fipe is not None and sem_cache.fipe is None
    assert casador.chamadas == []


def test_teto_da_pagina_deixa_o_restante_sem_fipe():
    carros = [anuncio(str(i)) for i in range(5)]
    casador = CasadorControlado({str(i): casamento() for i in range(5)}, demora=0.15)
    enriquecedor = EnriquecedorFipe(casador, ArmazemEstado(), tempo_pagina=0.02)
    inicio = time.monotonic()
    enriquecedor.enriquecer(carros)
    assert time.monotonic() - inicio < 0.1
    assert all(carro.fipe is None for carro in carros)
    assert all(carro.fipe_ausencia == "tempo_esgotado" for carro in carros)
    assert len(casador.chamadas) <= 2


def test_banco_fora_nao_consulta_fipe():
    casador = CasadorControlado({"a": casamento()})
    armazem = ArmazemEstado(fora=True)
    carro = anuncio("a")
    enriquecedor = EnriquecedorFipe(casador, armazem, tempo_pagina=1)
    enriquecedor.enriquecer([carro])
    assert casador.chamadas == []
    assert carro.fipe is None
    assert carro.fipe_ausencia == "banco_fora"
    assert armazem.ausencias == []
    armazem.fora = False
    enriquecedor.enriquecer([])
    enriquecedor.executor.shutdown(wait=True)
    assert [x["motivo"] for x in armazem.ausencias] == ["banco_fora"]


def test_falhas_operacionais_ficam_no_anuncio_e_sao_guardadas():
    casos = [
        (LimiteFipeAtingido(), "sem_orcamento"),
        (FonteFipeIndisponivel(), "fonte_indisponivel"),
        (RuntimeError("falha"), "erro_inesperado"),
    ]
    for erro, motivo in casos:
        armazem = ArmazemEstado()
        carro = anuncio(motivo)
        enriquecedor = EnriquecedorFipe(CasadorComErro(erro), armazem, tempo_pagina=1)
        enriquecedor.enriquecer([carro])
        enriquecedor.executor.shutdown(wait=True)
        assert carro.fipe_ausencia == motivo
        assert [x["motivo"] for x in armazem.ausencias] == [motivo]


class EnriquecedorResposta:
    def __init__(self):
        self.cache = 0
        self.buscas = 0
        self.individuais = 0

    @staticmethod
    def _aplicar(carros):
        for carro in carros:
            carro.fipe = ReferenciaFipe("005384-8", 40000, 25, "outubro de 2026", "alta")

    def carregar_cache(self, carros):
        self.cache += 1

    def resolver_busca(self, carros):
        self.buscas += 1
        self._aplicar(carros)

    def resolver(self, carro):
        self.individuais += 1
        self._aplicar([carro])


def test_bloco_fipe_sai_na_resposta_e_fica_fixo_na_pagina():
    enriquecedor = EnriquecedorResposta()
    c, fonte = cliente(enriquecedor_fipe=enriquecedor)
    primeira = c.get("/buscar/pagina", params={"texto": "gol", "pagina": 1}).json()
    segunda = c.get("/buscar/pagina", params={"texto": "gol", "pagina": 1}).json()
    assert primeira["anuncios"][0]["fipe"] == {
        "codigo": "005384-8",
        "preco": 40000.0,
        "diferenca_percentual": 25,
        "mes_referencia": "outubro de 2026",
        "confianca": "alta",
        "preco_estranho": False,
    }
    assert segunda["anuncios"][0]["fipe"] == primeira["anuncios"][0]["fipe"]
    assert fonte.paginas_pedidas == [("gol", 1)]
    assert (enriquecedor.cache, enriquecedor.buscas) == (1, 1)


def test_vitrine_so_le_o_cache_e_garimpar_resolve_um_anuncio():
    enriquecedor = EnriquecedorResposta()
    c, _ = cliente(enriquecedor_fipe=enriquecedor)
    vitrine = c.get("/buscar/pagina", params={"texto": "", "pagina": 1}).json()
    assert vitrine["anuncios"][0]["fipe"] is None
    assert (enriquecedor.cache, enriquecedor.buscas) == (1, 0)
    carro = vitrine["anuncios"][0]
    resposta = c.post("/fipe/anuncio", json=carro)
    assert resposta.status_code == 200
    assert resposta.json()["fipe"]["codigo"] == "005384-8"
    assert enriquecedor.individuais == 1
