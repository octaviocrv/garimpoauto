"""Casamento conservador entre um anúncio e o catálogo FIPE."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
import hashlib
import json
import re
import unicodedata
from typing import Literal, Optional

from armazem import Armazem
from catalogo_fipe import CatalogoFipe
from schemas import Anuncio
from sources.fipe import AnoFonte, OpcaoFonte, PrecoFonte, ReferenciaFonte

ConfiancaFipe = Literal["alta", "media", "baixa", "sem_candidato"]


@dataclass(frozen=True)
class EscolhaFipe:
    referencia: ReferenciaFonte
    marca: OpcaoFonte
    modelo: OpcaoFonte
    ano: AnoFonte
    confianca: ConfiancaFipe
    motivo: str
    pontuacao: float


@dataclass(frozen=True)
class CasamentoFipe:
    referencia_codigo: Optional[str]
    codigo_fipe: Optional[str]
    preco: Optional[float]
    mes_referencia: Optional[str]
    confianca: ConfiancaFipe
    motivo: str
    bloqueio: Optional[str] = None
    preco_estranho: bool = False

    def para_banco(self) -> dict:
        return {
            "referencia_codigo": self.referencia_codigo,
            "codigo_fipe": self.codigo_fipe,
            "preco": self.preco,
            "mes_referencia": self.mes_referencia,
            "confianca": self.confianca,
            "motivo": self.motivo,
            "bloqueio": self.bloqueio,
            "preco_estranho": self.preco_estranho,
        }


def normalizar(texto: Optional[str]) -> str:
    sem_acento = unicodedata.normalize("NFD", texto or "")
    sem_acento = "".join(c for c in sem_acento if unicodedata.category(c) != "Mn")
    sem_acento = sem_acento.lower().replace(",", ".")
    return " ".join(re.sub(r"[^a-z0-9.]+", " ", sem_acento).split())


def hash_entrada(a: Anuncio) -> str:
    dados = [
        a.marca, a.modelo, a.modelo_original, a.titulo, a.ano, a.combustivel,
        a.cambio, a.portas, a.preco, a.km,
    ]
    return hashlib.sha256(json.dumps(dados, ensure_ascii=False).encode()).hexdigest()


def bloqueio_do_anuncio(a: Anuncio, ano_atual: Optional[int] = None) -> Optional[str]:
    titulo = normalizar(a.titulo)
    frases_promocionais = (
        "em preparacao", "consulte o valor", "valor da entrada", "apenas entrada", "so entrada",
    )
    if any(frase in titulo for frase in frases_promocionais):
        return "anuncio_promocional"
    if a.ano is None or a.km is None:
        return None
    atual = ano_atual if ano_atual is not None else datetime.now().year
    if a.ano > atual + 1 or (atual - a.ano >= 2 and a.km < 1000):
        return "km_incoerente"
    return None


def _marca_base(texto: str) -> str:
    tokens = [x for x in normalizar(texto).split() if x not in {"vw", "sa", "ltda"}]
    return " ".join(tokens)


def _motor(texto: str) -> Optional[str]:
    achado = re.search(r"\b([0-9]\.[0-9])\b", normalizar(texto))
    return achado.group(1) if achado else None


def _portas_fipe(texto: str) -> Optional[int]:
    achado = re.search(r"\b([2345])p\b", normalizar(texto))
    return int(achado.group(1)) if achado else None


def _cambio_fipe(texto: str) -> Optional[str]:
    n = normalizar(texto)
    if any(x in n for x in (" automatic", " aut ", "i motion", " tiptronic", " dsg")):
        return "automatico"
    if any(x in n for x in (" mec ", " manual")):
        return "manual"
    return None


def _compativel_com_campos(a: Anuncio, candidato: OpcaoFonte) -> bool:
    texto = f" {normalizar(candidato.nome)} "
    motor_anuncio = _motor(f"{a.modelo_original or ''} {a.titulo or ''}")
    motor_fipe = _motor(texto)
    if motor_anuncio and motor_fipe and motor_anuncio != motor_fipe:
        return False
    portas = _portas_fipe(texto)
    if a.portas and portas:
        aceitas = {a.portas, a.portas + 1} if a.portas in (2, 4) else {a.portas}
        if portas not in aceitas:
            return False
    cambio = _cambio_fipe(texto)
    if a.cambio and cambio and normalizar(a.cambio) != cambio:
        return False
    return True


def _combustivel_compativel(anuncio: Optional[str], fipe: Optional[str]) -> bool:
    a, f = normalizar(anuncio), normalizar(fipe)
    if not a or not f:
        return False
    equivalentes = {
        "alcool": "etanol", "etanol": "etanol", "gasolina": "gasolina", "flex": "flex",
        "diesel": "diesel", "eletrico": "eletrico", "hibrido": "hibrido",
    }
    return equivalentes.get(a, a) == equivalentes.get(f, f)


def _pontuar(a: Anuncio, modelo: OpcaoFonte) -> float:
    origem = normalizar(a.titulo or a.modelo_original)
    origem = origem.replace("geracao vi ", "").replace("geracao v ", "novo ")
    destino = normalizar(modelo.nome)
    sequencia = SequenceMatcher(None, origem, destino).ratio()
    comuns = {"gol", "total", "flex", "mi", "mec", "mecanico", "geracao"}
    a_tokens = set(origem.split()) - comuns
    b_tokens = set(destino.split()) - comuns
    uniao = a_tokens | b_tokens
    jaccard = len(a_tokens & b_tokens) / len(uniao) if uniao else 0.0
    return sequencia * 0.65 + jaccard * 0.35


def _motivo(confianca: ConfiancaFipe, pontuacao: float, margem: float) -> str:
    if confianca == "alta":
        return f"Marca, modelo, ano, combustível e versão conferem com folga {margem:.2f}"
    if confianca == "media":
        return f"Versões próximas demais, diferença {margem:.2f}"
    if confianca == "baixa":
        return f"Versão pouco parecida, confiança {pontuacao:.2f}"
    return "Nenhum candidato compatível"


class CasadorFipe:
    def __init__(
        self, catalogo: CatalogoFipe, armazem: Armazem, maximo_candidatos_anos: int = 4,
        ano_atual: Optional[int] = None,
    ) -> None:
        self.catalogo, self.armazem = catalogo, armazem
        self.maximo_candidatos_anos = maximo_candidatos_anos
        self.ano_atual = ano_atual

    def escolher(self, a: Anuncio) -> Optional[EscolhaFipe]:
        if not a.marca or not a.modelo or a.ano is None or not a.combustivel or a.preco is None or a.preco <= 0:
            return None
        referencia = self.catalogo.referencia_atual()
        marca_base = _marca_base(a.marca)
        marcas = [m for m in self.catalogo.marcas(referencia.codigo) if _marca_base(m.nome) == marca_base]
        if len(marcas) != 1:
            return None
        marca = marcas[0]
        modelo_base = normalizar(a.modelo).split()
        if not modelo_base:
            return None
        candidatos = [
            m for m in self.catalogo.modelos(referencia.codigo, marca.codigo)
            if normalizar(m.nome).split()[:len(modelo_base)] == modelo_base and _compativel_com_campos(a, m)
        ]
        ranqueados = sorted(((_pontuar(a, m), m) for m in candidatos), key=lambda x: (-x[0], x[1].codigo))
        com_ano: list[tuple[float, OpcaoFonte, AnoFonte]] = []
        for pontuacao, modelo in ranqueados[:self.maximo_candidatos_anos]:
            anos = self.catalogo.anos(referencia.codigo, marca.codigo, modelo.codigo)
            compativeis = [
                ano for ano in anos
                if ano.ano_modelo == a.ano and _combustivel_compativel(a.combustivel, ano.combustivel)
            ]
            if len(compativeis) == 1:
                com_ano.append((pontuacao, modelo, compativeis[0]))
        if not com_ano:
            return None
        com_ano.sort(key=lambda x: (-x[0], x[1].codigo))
        melhor, segundo = com_ano[0], com_ano[1] if len(com_ano) > 1 else None
        margem = melhor[0] - segundo[0] if segundo else 1.0
        if melhor[0] >= 0.55 and margem >= 0.06:
            confianca: ConfiancaFipe = "alta"
        elif melhor[0] >= 0.48 and margem >= 0.03:
            confianca = "media"
        else:
            confianca = "baixa"
        return EscolhaFipe(
            referencia, marca, melhor[1], melhor[2], confianca,
            _motivo(confianca, melhor[0], margem), melhor[0],
        )

    def casar(self, a: Anuncio) -> CasamentoFipe:
        entrada = hash_entrada(a)
        guardado = self.armazem.fipe_casamento(a.source, a.external_id, entrada)
        if guardado:
            return CasamentoFipe(
                referencia_codigo=guardado["referencia_codigo"], codigo_fipe=guardado["codigo_fipe"],
                preco=float(guardado["preco"]) if guardado["preco"] is not None else None,
                mes_referencia=guardado["mes_referencia"], confianca=guardado["confianca"],
                motivo=guardado["motivo"], bloqueio=guardado["bloqueio"],
                preco_estranho=bool(guardado["preco_estranho"]),
            )
        bloqueio = bloqueio_do_anuncio(a, self.ano_atual)
        if bloqueio:
            motivo = "Anúncio promocional" if bloqueio == "anuncio_promocional" else "Quilometragem incoerente com o ano"
            resultado = CasamentoFipe(None, None, None, None, "sem_candidato", motivo, bloqueio=bloqueio)
            self.armazem.fipe_salvar_casamento(a.source, a.external_id, entrada, resultado.para_banco())
            return resultado
        escolha = self.escolher(a)
        if escolha is None:
            resultado = CasamentoFipe(None, None, None, None, "sem_candidato", "Nenhum candidato compatível")
        elif escolha.confianca != "alta":
            resultado = CasamentoFipe(
                escolha.referencia.codigo, None, None, escolha.referencia.mes,
                escolha.confianca, escolha.motivo,
            )
        else:
            preco: PrecoFonte = self.catalogo.preco(
                escolha.referencia.codigo, escolha.marca.codigo, escolha.modelo.codigo, escolha.ano.codigo,
            )
            resultado = CasamentoFipe(
                escolha.referencia.codigo, preco.codigo_fipe, float(preco.preco), preco.mes_referencia,
                escolha.confianca, escolha.motivo,
                preco_estranho=a.preco is not None and a.preco < float(preco.preco) * 0.5,
            )
        self.armazem.fipe_salvar_casamento(a.source, a.external_id, entrada, resultado.para_banco())
        return resultado
