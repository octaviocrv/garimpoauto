// Mesma lógica do filtro local do scraper (busca.py), em TypeScript: sem diferença de maiúscula e
// de acento, marca e modelo por palavra inteira, cidade igual, campo vazio não passa por filtro que o usa.
import type { Anuncio } from '../types'

export type TipoAnunciante = 'todos' | 'loja' | 'particular'
export type Ordem = 'menor_preco' | 'maior_preco' | 'menor_km' | 'mais_novo'

export interface Filtros {
  texto: string
  marca: string
  modelo: string
  anoMin: string
  anoMax: string
  precoMin: string
  precoMax: string
  kmMax: string
  cidade: string
  tipo: TipoAnunciante
}

export const FILTROS_VAZIOS: Filtros = {
  texto: '', marca: '', modelo: '', anoMin: '', anoMax: '',
  precoMin: '', precoMax: '', kmMax: '', cidade: '', tipo: 'todos',
}

export function normalizar(texto: string | null | undefined): string {
  if (!texto) return ''
  return texto.normalize('NFD').replace(/\p{Mn}/gu, '').toLowerCase().split(/\s+/).filter(Boolean).join(' ')
}

const escapar = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

function contemPalavra(procurado: string, valor: string | null): boolean {
  const alvo = normalizar(valor)
  return !!alvo && new RegExp(`(?<![\\p{L}\\p{N}_])${escapar(procurado)}(?![\\p{L}\\p{N}_])`, 'u').test(alvo)
}

const numero = (s: string): number | null => {
  const limpo = s.replace(/\D/g, '')
  return limpo ? Number(limpo) : null
}

export interface Filtrado {
  aprovados: Anuncio[]
  cortados: Record<string, number> // por filtro, só os ativos; cada anúncio conta no primeiro que o reprova
}

export function filtrar(anuncios: Anuncio[], f: Filtros): Filtrado {
  const marca = normalizar(f.marca)
  const modelo = normalizar(f.modelo)
  const cidade = normalizar(f.cidade)
  const palavras = normalizar(f.texto).split(' ').filter(Boolean)
  const [anoMin, anoMax, precoMin, precoMax, kmMax] = [f.anoMin, f.anoMax, f.precoMin, f.precoMax, f.kmMax].map(numero)

  const faixa = (v: number | null, min: number | null, max: number | null) =>
    min === null && max === null ? true : v !== null && (min === null || v >= min) && (max === null || v <= max)

  const testes: [string, boolean, (a: Anuncio) => boolean][] = [
    ['texto', palavras.length > 0, (a) => {
      const palheiro = normalizar([a.titulo, a.marca, a.modelo_original, a.cidade].filter(Boolean).join(' '))
      return palavras.every((p) => palheiro.includes(p))
    }],
    ['marca', !!marca, (a) => contemPalavra(marca, a.marca)],
    ['modelo', !!modelo, (a) => contemPalavra(modelo, a.modelo_original ?? a.modelo)],
    ['cidade', !!cidade, (a) => normalizar(a.cidade) === cidade],
    ['ano', anoMin !== null || anoMax !== null, (a) => faixa(a.ano, anoMin, anoMax)],
    ['preco', precoMin !== null || precoMax !== null, (a) => faixa(a.preco, precoMin, precoMax)],
    ['km', kmMax !== null, (a) => faixa(a.km, null, kmMax)],
    ['anunciante', f.tipo !== 'todos', (a) =>
      a.anunciante_profissional !== null && a.anunciante_profissional === (f.tipo === 'loja')],
  ]
  const ativos = testes.filter(([, ligado]) => ligado)
  const cortados = Object.fromEntries(ativos.map(([nome]) => [nome, 0]))
  const aprovados: Anuncio[] = []
  for (const a of anuncios) {
    const reprovou = ativos.find(([, , passa]) => !passa(a))
    if (reprovou) cortados[reprovou[0]] += 1
    else aprovados.push(a)
  }
  return { aprovados, cortados }
}

// Anúncio sem o campo da ordenação vai sempre para o fim.
export function ordenar(anuncios: Anuncio[], ordem: Ordem): Anuncio[] {
  const campo = { menor_preco: 'preco', maior_preco: 'preco', menor_km: 'km', mais_novo: 'ano' }[ordem] as 'preco' | 'km' | 'ano'
  const sentido = ordem === 'maior_preco' || ordem === 'mais_novo' ? -1 : 1
  return [...anuncios].sort((a, b) => {
    const [x, y] = [a[campo], b[campo]]
    if (x === null && y === null) return 0
    if (x === null) return 1
    if (y === null) return -1
    return (x - y) * sentido
  })
}

const CAMPOS_VERIFICADOS = ['preco', 'ano', 'km', 'marca', 'modelo_original', 'cidade'] as const

// Para o bloco de diagnóstico: quantos anúncios têm cada campo vazio (os que os filtros usam).
export function contarVazios(anuncios: Anuncio[]): { porCampo: Record<string, number>; algum: number } {
  const porCampo = Object.fromEntries(CAMPOS_VERIFICADOS.map((c) => [c, 0]))
  let algum = 0
  for (const a of anuncios) {
    let tem = false
    for (const c of CAMPOS_VERIFICADOS) {
      if (a[c] === null || a[c] === '') { porCampo[c] += 1; tem = true }
    }
    if (tem) algum += 1
  }
  return { porCampo, algum }
}
