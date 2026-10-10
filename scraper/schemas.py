"""Modelo único dos anúncios, igual para todas as fontes (OLX, Mercado Livre, WebMotors)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import unicodedata
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, field_validator, model_validator

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
    modelo_original: Optional[str] = None  # texto de vehicle_model como veio da fonte, sem normalizar
    ano: Optional[int] = None
    km: Optional[int] = None
    preco: Optional[int] = None  # em reais, sem centavos
    cambio: Optional[str] = None
    combustivel: Optional[str] = None
    cor: Optional[str] = None
    portas: Optional[int] = None
    cidade: Optional[str] = None
    bairro: Optional[str] = None
    estado: Optional[str] = None  # sigla em maiúscula, como a fonte devolve
    # Na OLX o campo "date" é a publicação só se o anúncio nunca foi renovado. Senão é a data da
    # renovação, e a de publicação não existe. Por isso são dois campos, e sem certeza os dois ficam vazios.
    publicado_em: Optional[datetime] = None  # em UTC
    renovado_em: Optional[datetime] = None  # em UTC, só quando o anúncio foi renovado
    em_destaque: bool = False  # anúncio impulsionado ou fixado no topo pela fonte
    repetido_de: Optional[str] = None  # external_id do primeiro igual (mesmo carro, preço, km e cidade)
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
        for campo in ("publicado_em", "renovado_em"):
            if d[campo] is not None:
                d[campo] = d[campo].isoformat()
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
    coletados: int = 0  # anúncios novos que vieram da fonte nesta página, antes do filtro local
    cortados_por_filtro: dict[str, int] = field(default_factory=dict)
    na_origem: list[str] = field(default_factory=list)  # filtros que a fonte aplicou na própria busca
    nao_resolvidos: list[str] = field(default_factory=list)  # filtros pedidos que a fonte não entendeu (viram filtro local)

    @property
    def ultima(self) -> bool:
        return self.parou_por is not None


MotivoParada = Literal["acabaram_paginas", "teto_paginas", "teto_tempo", "falha_fonte"]
CodigoAviso = Literal[
    "teto_paginas", "teto_tempo", "muitos_resultados", "poucos_resultados", "fonte_parcial", "filtro_aproximado"
]


class Aviso(BaseModel):
    """Algo que o usuário precisa saber sobre a busca. O `codigo` é estável (a tela pode se
    basear nele). `mensagem` é curta e humana, para o usuário. `detalhe_tecnico` traz os números e
    o limite configurado e só deve ser mostrado pela tela em modo de desenvolvimento."""

    codigo: CodigoAviso
    mensagem: str
    detalhe_tecnico: str


class Funil(BaseModel):
    """Quanto anúncio sobrou em cada etapa: total_na_fonte (o que a fonte diz ter, quando diz)
    -> coletados (vieram da fonte) -> cortados_por_filtro -> finais. Sempre vale
    coletados - soma(cortados_por_filtro) == finais."""

    total_na_fonte: Optional[int] = None
    coletados: int = 0
    cortados_por_filtro: dict[str, int] = {}
    finais: int = 0


class ResultadoBusca(BaseModel):
    """Resultado de uma busca inteira, igual para todas as fontes.

    `motivo_parada` está sempre preenchido. A busca nunca corta em silêncio: se parou por um
    teto ou por falha da fonte, devolve o que juntou e registra um aviso. Falha no meio da
    coleta (timeout, bloqueio, resposta estranha) não levanta erro, vira "falha_fonte".
    Em `avisos`, `mensagem` é para qualquer usuário e `detalhe_tecnico` (números e limites)
    só é mostrado pela tela em modo de desenvolvimento.
    """

    fonte: str
    anuncios: list[Anuncio]
    paginas_lidas: int
    tempo_segundos: float
    funil: Funil
    motivo_parada: MotivoParada
    avisos: list[Aviso] = []
    # Onde cada filtro pedido foi aplicado: na própria fonte (antes de coletar) ou aqui, depois da coleta.
    filtros_na_origem: list[str] = []
    filtros_locais: list[str] = []
    busca: Optional["Busca"] = None  # o que foi aplicado de fato (estado, ordenação e filtros)
    coletado_em: Optional[datetime] = None  # quando a coleta terminou, em UTC

    @property
    def incompletos(self) -> int:
        return sum(1 for a in self.anuncios if a.incompleto)


# Opções aceitas na busca, iguais para qualquer fonte. A fonte traduz para os códigos dela.
CAMBIOS = ("manual", "automatico", "semi-automatico", "automatizado")
COMBUSTIVEIS = ("gasolina", "alcool", "flex", "diesel", "hibrido", "eletrico")
ANUNCIANTES = ("particular", "profissional")
ORDENS = ("recentes", "menor_preco", "relevancia")
ORDEM_PADRAO = "recentes"  # estável entre páginas, ao contrário da relevância


def _opcao(v: Any, validas: tuple[str, ...], nome: str) -> Any:
    """Aceita 'Automático', ' semi automatico ' e devolve o valor canônico. Vazio vira None."""
    if v is None:
        return None
    chave = "".join(c for c in unicodedata.normalize("NFD", str(v)) if unicodedata.category(c) != "Mn")
    chave = "-".join(chave.lower().split())
    if not chave:
        return None
    if chave not in validas:
        raise ValueError(f"{nome} deve ser um destes: {', '.join(validas)}")
    return chave


class Busca(BaseModel):
    """O que o usuário pediu. Igual para todas as fontes; cada fonte usa o que aceita na URL
    e o resto é filtrado depois da coleta (busca.filtrar_local). Só `texto` é obrigatório."""

    texto: str
    marca: Optional[str] = None
    modelo: Optional[str] = None
    versao: Optional[str] = None
    ano_min: Optional[int] = None
    ano_max: Optional[int] = None
    preco_min: Optional[int] = None
    preco_max: Optional[int] = None
    km_min: Optional[int] = None
    km_max: Optional[int] = None
    cambio: Optional[str] = None
    combustivel: Optional[str] = None
    anunciante: Optional[str] = None  # particular ou profissional
    ordenar: str = ORDEM_PADRAO
    estado: Optional[str] = None  # sigla; vazio = Brasil todo
    regiao: Optional[str] = None  # slug da OLX, ex.: belo-horizonte-e-regiao (exige estado)
    cidade: Optional[str] = None

    @field_validator("texto")
    @classmethod
    def _texto_nao_vazio(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("texto da busca não pode ser vazio")
        return v

    @field_validator("marca", "modelo", "versao", "regiao", "cidade", mode="before")
    @classmethod
    def _vazio_vira_none(cls, v: Any) -> Any:
        if isinstance(v, str):
            v = v.strip()
            return v or None
        return v

    @field_validator("estado", mode="before")
    @classmethod
    def _estado(cls, v: Any) -> Any:
        if v is None:
            return None
        v = str(v).strip()
        if not v:
            return None
        if not (len(v) == 2 and v.isalpha()):
            raise ValueError(f"estado deve ser a sigla com 2 letras, recebi {v!r}")
        return v.upper()

    @field_validator("cambio", mode="before")
    @classmethod
    def _cambio(cls, v: Any) -> Any:
        return _opcao(v, CAMBIOS, "cambio")

    @field_validator("combustivel", mode="before")
    @classmethod
    def _combustivel(cls, v: Any) -> Any:
        return _opcao(v, COMBUSTIVEIS, "combustivel")

    @field_validator("anunciante", mode="before")
    @classmethod
    def _anunciante(cls, v: Any) -> Any:
        return _opcao(v, ANUNCIANTES, "anunciante")

    @field_validator("ordenar", mode="before")
    @classmethod
    def _ordenar(cls, v: Any) -> Any:
        return _opcao(v, ORDENS, "ordenar") or ORDEM_PADRAO

    @field_validator("ano_min", "ano_max", "preco_min", "preco_max", "km_min", "km_max")
    @classmethod
    def _nao_negativo(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("não pode ser negativo")
        return v

    @model_validator(mode="after")
    def _faixas_e_regiao(self) -> "Busca":
        for menor, maior in (("ano_min", "ano_max"), ("preco_min", "preco_max"), ("km_min", "km_max")):
            a, b = getattr(self, menor), getattr(self, maior)
            if a is not None and b is not None and a > b:
                raise ValueError(f"{menor} ({a}) maior que {maior} ({b})")
        if self.regiao and not self.estado:
            raise ValueError("regiao exige estado")
        return self


ResultadoBusca.model_rebuild()  # a Busca é definida depois do resultado
