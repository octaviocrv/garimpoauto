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
  regiao?: string // slug, só com estado
  zona?: string // slug, só com região
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
  regiao: string
  zona: string
  ordenar: string
}

export const ESTADO_PADRAO = 'MG'

export const RASCUNHO_VAZIO: Rascunho = {
  texto: '', estado: ESTADO_PADRAO, marca: '', modelo: '', versao: '', anoMin: '', anoMax: '',
  precoMin: '', precoMax: '', kmMin: '', kmMax: '', cambio: '', combustivel: '', anunciante: '',
  cidade: '', regiao: '', zona: '', ordenar: 'recentes',
}

const FILTROS_DO_PEDIDO = [
  'marca', 'modelo', 'versao', 'ano_min', 'ano_max', 'preco_min', 'preco_max', 'km_min', 'km_max',
  'cambio', 'combustivel', 'anunciante', 'cidade', 'regiao', 'zona',
] as const

// Quantos filtros vão de verdade na busca. Campo com espaço ou sem número nenhum não conta.
export const contarFiltros = (p: Pedido): number => FILTROS_DO_PEDIDO.filter((k) => p[k] !== undefined).length

// Lê o número do jeito que a pessoa escreve. "R$ 50.000,00", "50 mil", "1,5 mil", "50k", "120.000 km" e "2.020"
// viram 50000, 50000, 1500, 50000, 120000 e 2020. Vírgula ou ponto com 1 ou 2 dígitos no fim é decimal.
// Sem número nenhum o filtro fica de fora.
export function numero(v: string): number | undefined {
  const s = v.toLowerCase()
  const trecho = s.match(/\d+(?:[.,]\d+|\s\d{3}(?!\d))*/)?.[0] // o primeiro número, com separador de milhar
  if (!trecho) return undefined
  const decimal = trecho.match(/^(.+)[.,](\d{1,2})$/)
  const digitos = (t: string) => t.replace(/\D/g, '')
  let n = decimal ? Number(`${digitos(decimal[1])}.${decimal[2]}`) : Number(digitos(trecho))
  if (/\d\s*(?:mil|k)(?![a-z])/.test(s)) n *= 1000
  n = Math.round(n)
  return Number.isSafeInteger(n) ? n : undefined
}

// Se a pessoa trocar mínimo e máximo, a tela arruma sozinha em vez de dar erro.
const ordenado = (a?: number, b?: number): [number | undefined, number | undefined] =>
  a !== undefined && b !== undefined && a > b ? [b, a] : [a, b]

// Busca digitada: sem texto não há o que buscar.
export function montarPedido(r: Rascunho): Pedido | null {
  return r.texto.trim() ? montar(r) : null
}

// Busca da tela ao abrir e ao apertar Buscar. Sem texto e sem filtro é a vitrine do estado. Sem texto e
// com filtro busca com o filtro, não volta pra vitrine. Nunca devolve null.
export function montarPedidoOuVitrine(r: Rascunho): Pedido {
  return montar(r)
}

function montar(r: Rascunho): Pedido {
  const texto = r.texto.trim()
  const [ano_min, ano_max] = ordenado(numero(r.anoMin), numero(r.anoMax))
  const [preco_min, preco_max] = ordenado(numero(r.precoMin), numero(r.precoMax))
  const [km_min, km_max] = ordenado(numero(r.kmMin), numero(r.kmMax))
  const texto_ou_nada = (v: string) => v.trim() || undefined
  const estado = r.estado || ESTADO_PADRAO
  const regiao = estado === 'todos' ? undefined : texto_ou_nada(r.regiao) // região exige estado
  const zona = regiao ? texto_ou_nada(r.zona) : undefined // zona exige região
  return {
    texto, ordenar: r.ordenar || 'recentes', estado, regiao, zona,
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
