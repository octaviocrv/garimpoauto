"""Cache mensal do catálogo FIPE."""

from __future__ import annotations

from decimal import Decimal

from armazem import Armazem
from sources.fipe import AnoFonte, FonteFipe, OpcaoFonte, PrecoFonte, ReferenciaFonte


def _opcao(d: dict) -> OpcaoFonte:
    return OpcaoFonte(str(d["codigo"]), str(d["nome"]))


def _ano(d: dict) -> AnoFonte:
    return AnoFonte(
        codigo=str(d["codigo"]), nome=str(d["nome"]), ano_modelo=d["ano_modelo"],
        combustivel_codigo=d["combustivel_codigo"], combustivel=d["combustivel"],
    )


def _preco(d: dict) -> PrecoFonte:
    return PrecoFonte(
        codigo_fipe=str(d["codigo_fipe"]), preco=Decimal(d["preco"]), mes_referencia=str(d["mes_referencia"]),
        marca=str(d["marca"]), modelo=str(d["modelo"]), ano_modelo=int(d["ano_modelo"]),
        combustivel=str(d["combustivel"]),
    )


class CatalogoFipe:
    def __init__(self, armazem: Armazem, fonte: FonteFipe) -> None:
        self.armazem, self.fonte = armazem, fonte

    def referencia_atual(self) -> ReferenciaFonte:
        guardada = self.armazem.fipe_referencia_atual(somente_de_hoje=True)
        if guardada:
            return ReferenciaFonte(str(guardada["codigo"]), str(guardada["mes"]))
        referencias = self.fonte.referencias()
        if not referencias:
            raise ValueError("A fonte FIPE não devolveu mês de referência")
        self.armazem.fipe_salvar_referencias([{"codigo": r.codigo, "mes": r.mes} for r in referencias])
        return referencias[0]

    def marcas(self, referencia: str) -> list[OpcaoFonte]:
        if self.armazem.fipe_cache_concluido(referencia, "marcas", ""):
            return [_opcao(x) for x in self.armazem.fipe_marcas(referencia)]
        itens = self.fonte.marcas(referencia)
        self.armazem.fipe_salvar_marcas(referencia, [{"codigo": x.codigo, "nome": x.nome} for x in itens])
        return itens

    def modelos(self, referencia: str, marca: str) -> list[OpcaoFonte]:
        if self.armazem.fipe_cache_concluido(referencia, "modelos", marca):
            return [_opcao(x) for x in self.armazem.fipe_modelos(referencia, marca)]
        itens = self.fonte.modelos(referencia, marca)
        self.armazem.fipe_salvar_modelos(
            referencia, marca, [{"codigo": x.codigo, "nome": x.nome} for x in itens],
        )
        return itens

    def anos(self, referencia: str, marca: str, modelo: str) -> list[AnoFonte]:
        chave = f"{marca}|{modelo}"
        if self.armazem.fipe_cache_concluido(referencia, "anos", chave):
            return [_ano(x) for x in self.armazem.fipe_anos(referencia, marca, modelo)]
        itens = self.fonte.anos(referencia, marca, modelo)
        self.armazem.fipe_salvar_anos(
            referencia, marca, modelo,
            [
                {
                    "codigo": x.codigo, "nome": x.nome, "ano_modelo": x.ano_modelo,
                    "combustivel_codigo": x.combustivel_codigo, "combustivel": x.combustivel,
                }
                for x in itens
            ],
        )
        return itens

    def preco(self, referencia: str, marca: str, modelo: str, ano: str) -> PrecoFonte:
        guardado = self.armazem.fipe_preco(referencia, marca, modelo, ano)
        if guardado:
            return _preco(guardado)
        item = self.fonte.preco(referencia, marca, modelo, ano)
        self.armazem.fipe_salvar_preco(
            referencia, marca, modelo, ano,
            {
                "codigo_fipe": item.codigo_fipe, "preco": item.preco, "mes_referencia": item.mes_referencia,
                "marca": item.marca, "modelo": item.modelo, "ano_modelo": item.ano_modelo,
                "combustivel": item.combustivel,
            },
        )
        return item
