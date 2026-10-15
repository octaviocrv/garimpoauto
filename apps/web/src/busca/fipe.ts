// A FIPE real vem pronta do servidor. Só referências com confiança alta chegam à tela.
import type { Anuncio } from '../types'

export interface ReferenciaFipe {
  valor: number // valor de referência em reais
  diferencaReais: number // referência menos o preço do anúncio. Positivo: anúncio abaixo da FIPE
  diferencaPercentual: number // a mesma diferença em % da referência, com sinal igual
  codigo?: string
  mesReferencia?: string
  precoEstranho: boolean
}

export function fipeDe(a: Anuncio): ReferenciaFipe | null {
  if (a.fipe?.confianca === 'alta' && a.preco !== null) {
    return {
      valor: a.fipe.preco,
      diferencaReais: a.fipe.preco - a.preco,
      diferencaPercentual: a.fipe.diferenca_percentual,
      codigo: a.fipe.codigo,
      mesReferencia: a.fipe.mes_referencia,
      precoEstranho: a.fipe.preco_estranho,
    }
  }
  return null
}
