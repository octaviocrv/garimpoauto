// A FIPE vem do quadro Referência de preço da página do anúncio na OLX, lida quando a pessoa abre o Garimpar.
import type { Anuncio } from '../types'

export interface ReferenciaFipe {
  valor: number // valor de referência em reais
  diferencaReais: number // referência menos o preço do anúncio. Positivo: anúncio abaixo da FIPE
  diferencaPercentual: number // a mesma diferença em % da referência, com sinal igual
}

export function fipeDe(a: Anuncio): ReferenciaFipe | null {
  const fipe = a.referencia_preco?.fipe
  if (!fipe || fipe <= 0 || a.preco === null || a.preco <= 0) return null
  return {
    valor: fipe,
    diferencaReais: fipe - a.preco,
    diferencaPercentual: Math.round(((fipe - a.preco) / fipe) * 100),
  }
}
