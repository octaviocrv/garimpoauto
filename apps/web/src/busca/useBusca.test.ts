import { describe, expect, it } from 'vitest'
import { estimarPaginas } from './useBusca'

describe('estimarPaginas', () => {
  it('usa o total da fonte dividido pelo tamanho da 1ª página', () => {
    expect(estimarPaginas({ total_na_fonte: 120, coletados: 50, max_paginas: 8 })).toBe(3)
  })
  it('nunca passa do teto de páginas', () => {
    expect(estimarPaginas({ total_na_fonte: 5000, coletados: 50, max_paginas: 8 })).toBe(8)
  })
  it('sem total, assume o teto', () => {
    expect(estimarPaginas({ total_na_fonte: null, coletados: 50, max_paginas: 8 })).toBe(8)
  })
  it('uma página só quando cabe tudo nela', () => {
    expect(estimarPaginas({ total_na_fonte: 10, coletados: 10, max_paginas: 8 })).toBe(1)
  })
})
