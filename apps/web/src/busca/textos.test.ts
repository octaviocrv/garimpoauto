import { describe, expect, it } from 'vitest'
import { T, buscadoAs, naOlx, novosDesde } from './textos'

describe('textos da tela', () => {
  it('sem travessão, dois pontos nem ponto e vírgula', () => {
    for (const [nome, frase] of Object.entries(T)) {
      expect(frase, nome).not.toMatch(/[—–;:]/)
    }
  })

  it('usa carro e anúncio, nunca veículo ou listing', () => {
    const tudo = Object.values(T).join(' ').toLowerCase()
    expect(tudo).not.toMatch(/ve[ií]culo|listing/)
  })

  it('total e hora saem em português', () => {
    expect(naOlx(1413)).toBe('1.413 na OLX')
    expect(buscadoAs(new Date(2026, 9, 10, 14, 5).toISOString())).toBe('buscado às 14h05')
  })
})

describe('textos novos da tela', () => {
  it('a contagem de novos concorda com o número e segue as regras', () => {
    expect(novosDesde(1)).toBe('1 novo desde a última busca')
    expect(novosDesde(7)).toBe('7 novos desde a última busca')
    expect(novosDesde(7)).not.toMatch(/[—–;:]/)
  })
})
