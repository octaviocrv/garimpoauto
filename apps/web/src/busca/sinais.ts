// Sinais de que um carro vale abrir primeiro. Regras da casa:
// 1) só nasce de dado que o servidor devolveu, e dado faltando significa nenhum sinal, nunca chute
// 2) preço não vira sinal aqui. A comparação de preço é a referência da OLX, lida no Garimpar
// 3) "Destaque" da OLX é anúncio pago e não entra aqui
import type { Anuncio } from '../types'
import { T } from './textos'

export type TipoSinal = 'km' | 'recente'
export interface Sinal {
  tipo: TipoSinal
  texto: string // o motivo, em poucas palavras
  detalhe?: string // de onde veio a conta
}

export const KM_POR_ANO_BAIXO = 8000 // abaixo disso o carro rodou pouco (a média do uso fica perto de 12 mil)
export const KM_MINIMO_CONFIAVEL = 1000 // km menor que isso em carro de 2 anos ou mais costuma ser campo preenchido errado
export const IDADE_MINIMA_ANOS = 2 // em carro mais novo "km por ano" não diz nada
export const RECENTE_MINUTOS = 180

const MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']
const DIA = 86400000
const meiaNoite = (t: number) => new Date(t).setHours(0, 0, 0, 0)
const hora = (d: Date) => `${d.getHours()}h${String(d.getMinutes()).padStart(2, '0')}`

// Minutos desde o anúncio, ou null se não tem data (ou se ela está no futuro, o que não faz sentido).
export function minutosDesde(iso: string | null, agora: number): number | null {
  if (!iso) return null
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return null
  const min = Math.floor((agora - t) / 60000)
  return min < -5 ? null : Math.max(min, 0) // até 5 min de relógio torto a gente aceita
}

// "há 20 min", "há 2 h", "hoje às 14h05", "ontem às 9h30", "há 4 dias", "em 12 de set". Sem data, null.
export function dataCurta(iso: string | null, agora: number): string | null {
  const min = minutosDesde(iso, agora)
  if (min === null || !iso) return null
  const d = new Date(iso)
  if (min < 60) return `há ${Math.max(min, 1)} min`
  if (min < RECENTE_MINUTOS) return `há ${Math.floor(min / 60)} h`
  const dias = Math.round((meiaNoite(agora) - meiaNoite(d.getTime())) / DIA)
  if (dias <= 0) return `hoje às ${hora(d)}`
  if (dias === 1) return `ontem às ${hora(d)}`
  if (dias <= 6) return `há ${dias} dias`
  const ano = d.getFullYear() === new Date(agora).getFullYear() ? '' : ` de ${d.getFullYear()}`
  return `em ${d.getDate()} de ${MESES[d.getMonth()]}${ano}`
}

export const prefixoData = (a: Anuncio) => (a.renovado_em ? 'Renovado' : 'Anunciado')

function sinalDeKm(a: Anuncio, agora: number): Sinal | null {
  if (a.km === null || a.ano === null || a.km < KM_MINIMO_CONFIAVEL) return null
  const idade = new Date(agora).getFullYear() - a.ano
  if (idade < IDADE_MINIMA_ANOS) return null
  const porAno = a.km / idade
  if (porAno > KM_POR_ANO_BAIXO) return null
  const mil = (porAno / 1000).toLocaleString('pt-BR', { maximumFractionDigits: 1 })
  return { tipo: 'km', texto: T.poucoKm, detalhe: `${mil} mil km por ano` }
}

function sinalRecente(a: Anuncio, agora: number): Sinal | null {
  const min = minutosDesde(a.anunciado_em, agora)
  if (min === null || min >= RECENTE_MINUTOS) return null
  return { tipo: 'recente', texto: `${prefixoData(a)} ${dataCurta(a.anunciado_em, agora)}` }
}

// Os sinais dos carros que acabaram de chegar. Quem chama guarda o resultado e não recalcula:
// assim o card não muda sozinho quando chega outra página.
export function sinaisDaPagina(novos: Anuncio[], agora: number): Record<string, Sinal[]> {
  const saida: Record<string, Sinal[]> = {}
  for (const a of novos) {
    saida[a.external_id] = [sinalDeKm(a, agora), sinalRecente(a, agora)]
      .filter((s): s is Sinal => s !== null)
  }
  return saida
}
