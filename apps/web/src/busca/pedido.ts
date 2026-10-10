// O que a pessoa preenche na tela e como isso vira o pedido que o servidor entende.
export interface Pedido {
  texto: string
  marca?: string
  modelo?: string
  versao?: string
  ano_min?: number
  ano_max?: number
  preco_min?: number
  preco_max?: number
  km_min?: number
  km_max?: number
  cambio?: string
  combustivel?: string
  anunciante?: string
  cidade?: string
  ordenar: string
  estado: string // sigla, ou "todos" para o Brasil todo
}

export interface Rascunho {
  texto: string
  estado: string
  marca: string
  modelo: string
  versao: string
  anoMin: string
  anoMax: string
  precoMin: string
  precoMax: string
  kmMin: string
  kmMax: string
  cambio: string
  combustivel: string
  anunciante: string
  cidade: string
  ordenar: string
}

export const ESTADO_PADRAO = 'MG'

export const RASCUNHO_VAZIO: Rascunho = {
  texto: '', estado: ESTADO_PADRAO, marca: '', modelo: '', versao: '', anoMin: '', anoMax: '',
  precoMin: '', precoMax: '', kmMin: '', kmMax: '', cambio: '', combustivel: '', anunciante: '',
  cidade: '', ordenar: 'recentes',
}

export const FILTROS_DO_RASCUNHO: (keyof Rascunho)[] = [
  'marca', 'modelo', 'versao', 'anoMin', 'anoMax', 'precoMin', 'precoMax', 'kmMin', 'kmMax',
  'cambio', 'combustivel', 'anunciante', 'cidade',
]

const numero = (v: string): number | undefined => {
  const digitos = v.replace(/\D/g, '')
  return digitos ? Number(digitos) : undefined
}

// Se a pessoa trocar mínimo e máximo, a tela arruma sozinha em vez de dar erro.
const ordenado = (a?: number, b?: number): [number | undefined, number | undefined] =>
  a !== undefined && b !== undefined && a > b ? [b, a] : [a, b]

export function montarPedido(r: Rascunho): Pedido | null {
  const texto = r.texto.trim()
  if (!texto) return null
  const [ano_min, ano_max] = ordenado(numero(r.anoMin), numero(r.anoMax))
  const [preco_min, preco_max] = ordenado(numero(r.precoMin), numero(r.precoMax))
  const [km_min, km_max] = ordenado(numero(r.kmMin), numero(r.kmMax))
  const texto_ou_nada = (v: string) => v.trim() || undefined
  return {
    texto, ordenar: r.ordenar || 'recentes', estado: r.estado || ESTADO_PADRAO,
    marca: texto_ou_nada(r.marca), modelo: texto_ou_nada(r.modelo), versao: texto_ou_nada(r.versao),
    ano_min, ano_max, preco_min, preco_max, km_min, km_max,
    cambio: r.cambio || undefined, combustivel: r.combustivel || undefined,
    anunciante: r.anunciante || undefined, cidade: texto_ou_nada(r.cidade),
  }
}

export const CAMBIOS = [
  ['', 'Qualquer'], ['manual', 'Manual'], ['automatico', 'Automático'],
  ['semi-automatico', 'Semi-automático'], ['automatizado', 'Automatizado'],
] as const
export const COMBUSTIVEIS = [
  ['', 'Qualquer'], ['gasolina', 'Gasolina'], ['alcool', 'Álcool'], ['flex', 'Flex'],
  ['diesel', 'Diesel'], ['hibrido', 'Híbrido'], ['eletrico', 'Elétrico'],
] as const
export const ANUNCIANTES = [['', 'Qualquer'], ['profissional', 'Loja'], ['particular', 'Particular']] as const
export const ORDENS = [['recentes', 'Mais recentes'], ['menor_preco', 'Menor preço'], ['relevancia', 'Mais relevantes']] as const

export const ESTADOS = [
  ['todos', 'Brasil todo'], ['AC', 'Acre'], ['AL', 'Alagoas'], ['AP', 'Amapá'], ['AM', 'Amazonas'], ['BA', 'Bahia'],
  ['CE', 'Ceará'], ['DF', 'Distrito Federal'], ['ES', 'Espírito Santo'], ['GO', 'Goiás'], ['MA', 'Maranhão'],
  ['MT', 'Mato Grosso'], ['MS', 'Mato Grosso do Sul'], ['MG', 'Minas Gerais'], ['PA', 'Pará'], ['PB', 'Paraíba'],
  ['PR', 'Paraná'], ['PE', 'Pernambuco'], ['PI', 'Piauí'], ['RJ', 'Rio de Janeiro'], ['RN', 'Rio Grande do Norte'],
  ['RS', 'Rio Grande do Sul'], ['RO', 'Rondônia'], ['RR', 'Roraima'], ['SC', 'Santa Catarina'], ['SP', 'São Paulo'],
  ['SE', 'Sergipe'], ['TO', 'Tocantins'],
] as const

export const nomeDoEstado = (sigla: string): string =>
  ESTADOS.find(([s]) => s.toLowerCase() === sigla.toLowerCase())?.[1] ?? sigla
