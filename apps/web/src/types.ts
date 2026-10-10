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
  km_max?: number | null
  estado?: string | null
  regiao?: string | null
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
  anunciante_profissional: boolean | null
  nota_anunciante: number | null
  imagens: string[]
  incompleto: boolean
  campos_faltando: string[]
}

export type MotivoParada = 'acabaram_paginas' | 'teto_paginas' | 'teto_tempo' | 'falha_fonte'
export type CodigoAviso = 'teto_paginas' | 'teto_tempo' | 'muitos_resultados' | 'poucos_resultados' | 'fonte_parcial'

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
