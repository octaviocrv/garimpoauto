// A FIPE ainda não existe de verdade. Este arquivo é o ÚNICO lugar que sabe disso.
// `fipeDe` devolve a referência de um carro, ou null quando não temos. Hoje sempre null, a não ser
// com ?demo=1 no endereço da página, quando devolve um valor INVENTADO só pra ver o layout do card.
// Quando a FIPE real chegar, troque o corpo de `fipeDe` e o card continua igual.
// A FIPE (de verdade ou de exemplo) nunca entra em sinal, em ordem nem em destaque.
import type { Anuncio } from '../types'

export interface ReferenciaFipe {
  valor: number // valor de referência em reais
  diferencaReais: number // referência menos o preço do anúncio. Positivo: anúncio abaixo da FIPE
  diferencaPercentual: number // a mesma diferença em % da referência, com sinal igual
  exemplo: boolean // true quando o valor é inventado
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
  return { valor, diferencaReais, diferencaPercentual: Math.round((diferencaReais / valor) * 100), exemplo: true }
}

export function fipeDe(a: Anuncio): ReferenciaFipe | null {
  return DEMO ? fipeDeExemplo(a) : null
}
