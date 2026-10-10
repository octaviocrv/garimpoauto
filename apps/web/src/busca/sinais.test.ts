import { describe, expect, it } from 'vitest'
import { dataCurta, minutosDesde, sinaisDaPagina } from './sinais'
import { agrupar } from './analise'
import { fipeDe, fipeDeExemplo } from './fipe'
import type { Anuncio } from '../types'

// 10 de outubro de 2026, 15h00 no horário local
const AGORA = new Date(2026, 9, 10, 15, 0).getTime()
const antes = (min: number) => new Date(AGORA - min * 60000).toISOString()

const carro = (id: string, extra: Partial<Anuncio> = {}): Anuncio => ({
  external_id: id, marca: 'Fiat', modelo: 'Argo', ano: 2019, km: 60000, preco: 50000, anunciado_em: null,
  renovado_em: null, publicado_em: null, em_destaque: false, novo: false, imagens: [], ...extra,
} as Anuncio)
const sinaisDe = (a: Anuncio, lista: Anuncio[] = [a]) => sinaisDaPagina([a], agrupar(lista), AGORA)[a.external_id]

describe('data curta', () => {
  it('conta em minutos, horas, hoje, ontem, dias e data', () => {
    expect(dataCurta(antes(20), AGORA)).toBe('há 20 min')
    expect(dataCurta(antes(0), AGORA)).toBe('há 1 min')
    expect(dataCurta(antes(130), AGORA)).toBe('há 2 h')
    expect(dataCurta(new Date(2026, 9, 10, 9, 5).toISOString(), AGORA)).toBe('hoje às 9h05')
    expect(dataCurta(new Date(2026, 9, 9, 23, 30).toISOString(), AGORA)).toBe('ontem às 23h30')
    expect(dataCurta(new Date(2026, 9, 6, 12, 0).toISOString(), AGORA)).toBe('há 4 dias')
    expect(dataCurta(new Date(2026, 8, 12, 12, 0).toISOString(), AGORA)).toBe('em 12 de set')
    expect(dataCurta(new Date(2025, 8, 12, 12, 0).toISOString(), AGORA)).toBe('em 12 de set de 2025')
  })

  it('sem data, data torta ou no futuro não mostra nada', () => {
    expect(dataCurta(null, AGORA)).toBeNull()
    expect(dataCurta('ontem', AGORA)).toBeNull()
    expect(dataCurta(antes(-60), AGORA)).toBeNull()
    expect(minutosDesde(antes(-3), AGORA)).toBe(0) // relógio torto de poucos minutos é aceito
  })
})

describe('sinal de km baixo pro ano', () => {
  it('aparece com km por ano baixo e diz a conta', () => {
    const s = sinaisDe(carro('a', { ano: 2019, km: 49000 })) // 7 anos, 7 mil por ano
    expect(s).toEqual([{ tipo: 'km', texto: 'Pouco km pro ano', detalhe: '7 mil km por ano' }])
  })

  it('não aparece com km normal, acima do limite', () => {
    expect(sinaisDe(carro('a', { ano: 2019, km: 90000 }))).toEqual([])
  })

  it('dado faltando ou duvidoso não vira sinal', () => {
    expect(sinaisDe(carro('a', { km: null }))).toEqual([])
    expect(sinaisDe(carro('b', { ano: null }))).toEqual([])
    expect(sinaisDe(carro('c', { km: 0 }))).toEqual([])
    expect(sinaisDe(carro('d', { km: 500 }))).toEqual([])
  })

  it('carro novo demais não entra, km por ano não diz nada', () => {
    expect(sinaisDe(carro('a', { ano: 2026, km: 3000 }))).toEqual([])
    expect(sinaisDe(carro('b', { ano: 2025, km: 3000 }))).toEqual([])
  })
})

describe('sinal de anúncio recente', () => {
  it('anúncio de poucas horas aparece, e diz se foi renovado', () => {
    const a = sinaisDe(carro('a', { km: null, anunciado_em: antes(40) }))
    expect(a).toEqual([{ tipo: 'recente', texto: 'Anunciado há 40 min' }])
    const b = sinaisDe(carro('b', { km: null, anunciado_em: antes(130), renovado_em: antes(130) }))
    expect(b[0].texto).toBe('Renovado há 2 h')
  })

  it('anúncio mais velho ou sem data não aparece', () => {
    expect(sinaisDe(carro('a', { km: null, anunciado_em: antes(200) }))).toEqual([])
    expect(sinaisDe(carro('b', { km: null, anunciado_em: null }))).toEqual([])
  })
})

describe('sinal de preço contra a lista carregada', () => {
  const grupo = (precos: number[], extra: Partial<Anuncio> = {}) =>
    precos.map((p, i) => carro(`g${i}`, { km: null, preco: p, ...extra }))

  it('aparece quando está bem abaixo dos iguais da lista, e diz com quantos comparou', () => {
    const lista = grupo([50000, 52000, 51000, 50000, 40000])
    const s = sinaisDaPagina(lista, agrupar(lista), AGORA)
    expect(s.g4).toEqual([{ tipo: 'preco', texto: 'Preço 20% abaixo da lista', detalhe: 'Comparado com 5 Argo 2019 já carregados' }])
    expect(s.g0).toEqual([])
  })

  it('amostra pequena não compara', () => {
    const lista = grupo([50000, 52000, 51000, 40000])
    expect(sinaisDaPagina(lista, agrupar(lista), AGORA).g3).toEqual([])
  })

  it('só compara com o mesmo modelo e ano', () => {
    const lista = [...grupo([50000, 52000, 51000, 50000]), carro('outro', { km: null, preco: 30000, ano: 2012 })]
    expect(sinaisDaPagina(lista, agrupar(lista), AGORA).outro).toEqual([])
  })

  it('diferença pequena não é sinal, e desconto grande demais também não', () => {
    const pequena = grupo([50000, 52000, 51000, 50000, 45000])
    expect(sinaisDaPagina(pequena, agrupar(pequena), AGORA).g4).toEqual([])
    const enorme = grupo([50000, 52000, 51000, 50000, 5000])
    expect(sinaisDaPagina(enorme, agrupar(enorme), AGORA).g4).toEqual([])
  })

  it('sem preço ou sem modelo não entra na conta nem vira sinal', () => {
    const lista = [...grupo([50000, 52000, 51000, 50000, 40000]), carro('x', { km: null, preco: null }), carro('y', { km: null, modelo: null })]
    const s = sinaisDaPagina(lista, agrupar(lista), AGORA)
    expect(s.x).toEqual([])
    expect(s.y).toEqual([])
    expect(s.g4[0].detalhe).toContain('5 Argo')
  })
})

describe('o que não é sinal', () => {
  it('destaque pago da OLX não gera sinal', () => {
    expect(sinaisDe(carro('a', { km: null, em_destaque: true }))).toEqual([])
  })

  it('os textos dos sinais seguem as regras da tela', () => {
    const lista = [...[50000, 52000, 51000, 50000, 40000].map((p, i) => carro(`g${i}`, { km: 40000, preco: p, anunciado_em: antes(10) }))]
    const todos = Object.values(sinaisDaPagina(lista, agrupar(lista), AGORA)).flat()
    expect(todos.length).toBeGreaterThan(0)
    for (const s of todos) expect(`${s.texto} ${s.detalhe ?? ''}`).not.toMatch(/[—–;:]/)
  })
})

describe('FIPE', () => {
  it('sem o interruptor de exemplo, não existe FIPE', () => {
    expect(fipeDe(carro('a'))).toBeNull()
  })

  it('o exemplo vem marcado, tem a conta certa e é sempre o mesmo pro mesmo carro', () => {
    const feitos = Array.from({ length: 30 }, (_, i) => fipeDeExemplo(carro(`id${i}`))).filter((f) => f !== null)
    expect(feitos.length).toBeGreaterThan(10)
    expect(feitos.length).toBeLessThan(30) // um pedaço fica sem FIPE, pra comparar
    for (const f of feitos) {
      expect(f.exemplo).toBe(true)
      expect(f.diferencaReais).toBe(f.valor - 50000)
      expect(Math.sign(f.diferencaPercentual)).toBe(Math.sign(f.diferencaReais))
    }
    expect(fipeDeExemplo(carro('id1'))).toEqual(fipeDeExemplo(carro('id1')))
  })

  it('carro sem preço não tem FIPE de exemplo', () => {
    expect(fipeDeExemplo(carro('a', { preco: null }))).toBeNull()
  })
})
