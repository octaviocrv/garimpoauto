// A FIPE real vem pronta do servidor. O exemplo continua isolado aqui para o modo ?demo=1.
// Nenhuma das duas entra em sinal, ordem, destaque ou veredito.
import type { Anuncio } from '../types'

export interface ReferenciaFipe {
  valor: number // valor de referência em reais
  diferencaReais: number // referência menos o preço do anúncio. Positivo: anúncio abaixo da FIPE
  diferencaPercentual: number // a mesma diferença em % da referência, com sinal igual
  exemplo: boolean // true quando o valor é inventado
  codigo?: string
  mesReferencia?: string
  precoEstranho: boolean
}

export const DEMO = typeof window !== 'undefined' && new URLSearchParams(window.location.search).get('demo') === '1'

// Número estável a partir do id, pra o mesmo carro ter sempre o mesmo exemplo.
function semente(id: string): number {
  let h = 7
  for (const c of id) h = (h * 31 + c.charCodeAt(0)) >>> 0
  return h
}

export function fipeDeExemplo(a: Anuncio): ReferenciaFipe | null {
  if (a.preco === null) return null
  const s = semente(a.external_id)
  if (s % 3 === 0) return null // um terço dos carros fica sem FIPE, pra comparar com o card de hoje
  const pct = ((s >>> 3) % 33) - 10 // de 10% acima a 22% abaixo da referência
  const valor = Math.round(a.preco / (1 - pct / 100) / 100) * 100
  const diferencaReais = valor - a.preco
  return {
    valor, diferencaReais, diferencaPercentual: Math.round((diferencaReais / valor) * 100),
    exemplo: true, precoEstranho: false,
  }
}

export function fipeDe(a: Anuncio): ReferenciaFipe | null {
  if (a.fipe?.confianca === 'alta' && a.preco !== null) {
    return {
      valor: a.fipe.preco,
      diferencaReais: a.fipe.preco - a.preco,
      diferencaPercentual: a.fipe.diferenca_percentual,
      exemplo: false,
      codigo: a.fipe.codigo,
      mesReferencia: a.fipe.mes_referencia,
      precoEstranho: a.fipe.preco_estranho,
    }
  }
  return DEMO ? fipeDeExemplo(a) : null
}
