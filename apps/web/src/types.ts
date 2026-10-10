// Tipos iguais ao scraper/schemas.py (Busca, Anuncio, Funil, Aviso, ResultadoBusca).
// Campo vazio vem como null.

export interface Busca {
  texto: string
  marca?: string | null
  modelo?: string | null
  ano_min?: number | null
  ano_max?: number | null
  preco_min?: number | null
  preco_max?: number | null
  km_min?: number | null
  km_max?: number | null
  versao?: string | null
  cambio?: string | null
  combustivel?: string | null
  anunciante?: string | null
  ordenar?: string
  estado?: string | null
  regiao?: string | null
  zona?: string | null
  cidade?: string | null
}

export interface Anuncio {
  source: string
  external_id: string
  url: string
  titulo: string | null
  marca: string | null
  modelo: string | null
  modelo_original: string | null
  ano: number | null
  km: number | null
  preco: number | null
  cambio: string | null
  combustivel: string | null
  cor: string | null
  portas: number | null
  cidade: string | null
  bairro: string | null
  estado: string | null
  publicado_em: string | null
  renovado_em: string | null
  anunciado_em: string | null // a data que a pessoa vê: a da renovação, senão a da publicação
  em_destaque: boolean
  repetido_de: string | null
  anunciante_profissional: boolean | null
  nota_anunciante: number | null
  imagens: string[]
  novo: boolean // só vale com o banco ligado, depois da primeira busca
  incompleto: boolean
  campos_faltando: string[]
}

export type MotivoParada = 'acabaram_paginas' | 'teto_paginas' | 'teto_tempo' | 'falha_fonte'
export type CodigoAviso = 'teto_paginas' | 'teto_tempo' | 'muitos_resultados' | 'poucos_resultados' | 'fonte_parcial' | 'filtro_aproximado'

export interface Aviso {
  codigo: CodigoAviso
  mensagem: string
  detalhe_tecnico?: string // o servidor só manda com dev=1, a tela só mostra com ?dev=1
}

export interface Funil {
  total_na_fonte: number | null
  coletados: number
  cortados_por_filtro: Record<string, number>
  finais: number
}

export interface ResultadoBusca {
  fonte: string
  anuncios: Anuncio[]
  paginas_lidas: number
  tempo_segundos: number
  funil: Funil
  motivo_parada: MotivoParada
  avisos: Aviso[]
}

// Resposta de GET /buscar/pagina (o "Ver mais"). Veja docs/api-busca-paginada.md.
export interface RespostaPagina {
  pagina: number
  anuncios: Anuncio[]
  tem_mais: boolean
  proxima_pagina: number | null // se a leitura falhou, é a mesma página, para tentar de novo
  entregues: number
  coletados: number
  total_na_fonte: number | null
  cortados_por_filtro: Record<string, number>
  motivo_parada: MotivoParada | null
  falhou: boolean
  informacao: string // frase pronta, no tom do Garimpo Auto
  avisos: Aviso[]
  filtros_na_origem: string[]
  filtros_locais: string[]
  busca: Busca
  estado_aplicado: string // sigla, ou "todos"
  coletado_em: string | null
  do_cache: boolean
  novos?: number // quantos dos carros entregues até aqui são novos desde a última busca igual
  primeira_busca?: boolean | null // true: nunca houve busca igual. null: servidor sem banco, "não sei"
}

// GET /regioes e GET /zonas, para os seletores da tela.
export interface Lugar {
  slug: string
  nome: string
}
export interface RespostaRegioes {
  estado: string
  regioes: Lugar[]
}
export interface RespostaZonas {
  estado: string
  regiao: string
  zonas: Lugar[]
}
