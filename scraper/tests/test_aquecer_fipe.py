import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from aquecer_fipe import OrcamentoExecucao, ordenar_por_modelo_comum  # noqa: E402
from schemas import Anuncio  # noqa: E402


def carro(id_, marca, modelo):
    return Anuncio(source="olx", external_id=id_, url="https://exemplo", marca=marca, modelo=modelo)


def test_modelos_mais_comuns_entram_primeiro_e_ordem_e_estavel():
    anuncios = [
        carro("3", "Fiat", "Uno"), carro("2", "Volkswagen", "Gol"),
        carro("1", "Volkswagen", "Gol"), carro("4", "Honda", "Civic"),
    ]
    assert [a.external_id for a in ordenar_por_modelo_comum(anuncios)] == ["1", "2", "3", "4"]


class BancoOrcamento:
    def __init__(self):
        self.chamadas = 0

    def fipe_reservar_requisicao(self, limite):
        self.chamadas += 1
        return self.chamadas <= limite


def test_orcamento_da_execucao_nunca_ultrapassa_o_diario():
    banco = BancoOrcamento()
    controle = OrcamentoExecucao(banco, limite_execucao=2, limite_dia=10)
    assert controle.reservar()
    assert controle.reservar()
    assert not controle.reservar()
    assert banco.chamadas == 2

    banco = BancoOrcamento()
    controle = OrcamentoExecucao(banco, limite_execucao=10, limite_dia=1)
    assert controle.reservar()
    assert not controle.reservar()
    assert controle.usadas == 1
