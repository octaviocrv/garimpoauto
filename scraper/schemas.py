"""Modelo único dos anúncios, igual para todas as fontes (OLX, Mercado Livre, WebMotors)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Optional

# Campos sem os quais o anúncio não serve para comparar com a FIPE.
CAMPOS_OBRIGATORIOS = ("preco", "ano", "modelo")


@dataclass
class Anuncio:
    source: str
    external_id: str
    url: str
    titulo: Optional[str] = None
    marca: Optional[str] = None
    modelo: Optional[str] = None
    ano: Optional[int] = None
    km: Optional[int] = None
    preco: Optional[int] = None  # em reais, sem centavos
    cambio: Optional[str] = None
    combustivel: Optional[str] = None
    cor: Optional[str] = None
    portas: Optional[int] = None
    cidade: Optional[str] = None
    bairro: Optional[str] = None
    estado: Optional[str] = None  # sigla, ex.: "MG"
    publicado_em: Optional[datetime] = None  # data do anúncio na fonte, em UTC
    anunciante_profissional: Optional[bool] = None
    nota_anunciante: Optional[float] = None  # nota do Google (0 a 5), só de anunciante profissional
    imagens: list[str] = field(default_factory=list)  # só os links
    incompleto: bool = False
    campos_faltando: list[str] = field(default_factory=list)
    # Item cru da fonte, já sem nome nem telefone de anunciante (vai para raw_listings).
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def marcar_completude(self) -> "Anuncio":
        self.campos_faltando = [c for c in CAMPOS_OBRIGATORIOS if getattr(self, c) is None]
        self.incompleto = bool(self.campos_faltando)
        return self

    def to_dict(self, com_raw: bool = True) -> dict[str, Any]:
        d = asdict(self)
        if self.publicado_em is not None:
            d["publicado_em"] = self.publicado_em.isoformat()
        if not com_raw:
            d.pop("raw")
        return d


@dataclass
class PaginaBusca:
    """Uma página devolvida pela busca. A última traz `parou_por` preenchido."""

    fonte: str
    numero: int
    anuncios: list[Anuncio]
    acumulado: int  # quantos anúncios já juntou até aqui, contando esta página
    total_ads: Optional[int] = None  # total que a fonte diz ter para a busca
    parou_por: Optional[str] = None  # None enquanto houver mais páginas
    aviso: Optional[str] = None  # texto humano quando algo deu errado

    @property
    def ultima(self) -> bool:
        return self.parou_por is not None


@dataclass
class ResultadoBusca:
    """Resultado de uma busca inteira, para quem não precisa receber página por página."""

    fonte: str
    anuncios: list[Anuncio]
    paginas: int  # páginas que de fato trouxeram resposta
    total_ads: Optional[int]
    parou_por: Optional[str]
    aviso: Optional[str]
    segundos: float

    @property
    def incompletos(self) -> int:
        return sum(1 for a in self.anuncios if a.incompleto)
