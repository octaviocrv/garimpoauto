// A FIPE vem da página do anúncio na OLX, lida quando a pessoa abre o Garimpar.
import type { Anuncio, ReferenciaFipe as FipeDoAnuncio } from '../types'

export interface ReferenciaFipe {
  valor: number // valor de referência em reais
  diferencaReais: number // referência menos o preço do anúncio. Positivo: anúncio abaixo da FIPE
  diferencaPercentual: number // a mesma diferença em % da referência, com sinal igual
}

export function fipeDe(a: Anuncio): ReferenciaFipe | null {
  if (a.fipe?.confianca === 'alta' && a.preco !== null) {
    return {
      valor: a.fipe.preco,
      diferencaReais: a.fipe.preco - a.preco,
      diferencaPercentual: a.fipe.diferenca_percentual,
    }
  }
  return null
}

// O preço FIPE da OLX no formato que a análise e o card já leem.
export function fipeDaOlx(preco: number | null, fipe: number | null | undefined): FipeDoAnuncio | null {
  if (!fipe || fipe <= 0) return null
  return {
    preco: fipe,
    diferenca_percentual: preco !== null && preco > 0 ? Math.round(((fipe - preco) / fipe) * 100) : 0,
    confianca: 'alta',
  }
}
