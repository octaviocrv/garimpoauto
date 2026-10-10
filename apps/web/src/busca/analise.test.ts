import { describe, expect, it } from 'vitest'
import { agrupar, analisesDaPagina, palavraDeRisco } from './analise'
import type { Anuncio } from '../types'

const AGORA = new Date(2026, 9, 10, 15, 0).getTime()
const fotos = ['a', 'b', 'c', 'd']

const carro = (id: string, extra: Partial<Anuncio> = {}): Anuncio => ({
  external_id: id, marca: 'Fiat', modelo: 'Argo', ano: 2019, km: 60000, preco: 50000, titulo: 'Argo 1.0 Drive',
  modelo_original: 'Argo 1.0 Drive', anunciado_em: null, renovado_em: null, publicado_em: null, em_destaque: false,
  novo: false, imagens: fotos, anunciante_profissional: null, nota_anunciante: null, repetido_de: null, ...extra,
} as Anuncio)

// Cinco iguais por perto de R$ 50 mil, mais o carro que a gente quer analisar.
const mercado = (alvo: Anuncio): Anuncio[] =>
  [50000, 52000, 51000, 50000, 50000].map((p, i) => carro(`m${i}`, { preco: p })).concat(alvo)
const analise = (alvo: Anuncio) => { const lista = mercado(alvo); return analisesDaPagina([alvo], agrupar(lista), AGORA)[alvo.external_id] }
const veredito = (alvo: Anuncio, id: string) => analise(alvo).criterios.find((c) => c.id === id)?.veredito

describe('nível do carro', () => {
  it('Quente: margem alta, sem alerta e pelo menos 2 pontos a favor', () => {
    const a = analise(carro('x', { preco: 42000, km: 35000, anunciante_profissional: false }))
    expect(a.nivel).toBe('quente')
    expect(a.resumo).toMatch(/^Margem estimada R\$ 5\.\d00$/)
    expect(a.margem?.estimada).toBeCloseTo(50000 - 42000 - 2500)
    expect(a.motivo).toContain('2 pontos a favor')
  })

  it('Boa: margem razoável mas sem os pontos a favor pra ser Quente', () => {
    const a = analise(carro('x', { preco: 44500 })) // margem de uns R$ 3.000, 6% da mediana
    expect(a.nivel).toBe('boa')
    expect(a.motivo).toContain('Pra ser Quente')
  })

  it('margem baixa não destaca, e o motivo diz o mínimo', () => {
    const a = analise(carro('x', { preco: 48000 }))
    expect(a.nivel).toBeNull()
    expect(a.resumo).toBeNull()
    expect(a.motivo).toContain('abaixo do mínimo')
  })

  it('um alerta tira o Quente mesmo com margem alta', () => {
    const a = analise(carro('x', { preco: 42000, km: 35000, anunciante_profissional: false, imagens: ['a'] }))
    expect(veredito(carro('x', { imagens: ['a'] }), 'fotos')).toBe('atencao')
    expect(a.nivel).toBe('boa')
  })

  it('sem carros iguais suficientes não tem margem nem nível, e diz por quê', () => {
    const sozinho = carro('x', { preco: 30000 })
    const a = analisesDaPagina([sozinho], agrupar([sozinho]), AGORA).x
    expect(a.nivel).toBeNull()
    expect(a.margem).toBeNull()
    expect(a.criterios.find((c) => c.id === 'preco')?.veredito).toBe('semdado')
    expect(a.criterios.find((c) => c.id === 'preco')?.fato).toContain('preciso de 5')
  })

  it('sem preço, sem margem e sem nível', () => {
    expect(analise(carro('x', { preco: null })).nivel).toBeNull()
  })
})

describe('alertas fortes', () => {
  it('preço baixo demais é alerta, não oportunidade', () => {
    const a = analise(carro('x', { preco: 30000, km: 35000, anunciante_profissional: false }))
    expect(a.nivel).toBeNull()
    expect(a.criterios.find((c) => c.id === 'preco')?.resultado).toContain('baixo demais')
    expect(a.criterios.find((c) => c.id === 'margem')?.veredito).toBe('atencao')
  })

  it('palavra de risco no título bloqueia o nível', () => {
    const a = analise(carro('x', { preco: 42000, km: 35000, anunciante_profissional: false, titulo: 'Argo 2019 recuperado de leilão' }))
    expect(a.nivel).toBeNull()
    expect(a.criterios.find((c) => c.id === 'risco')?.veredito).toBe('atencao')
  })

  it('anúncio repetido bloqueia o nível', () => {
    const a = analise(carro('x', { preco: 42000, km: 35000, anunciante_profissional: false, repetido_de: 'm0' }))
    expect(a.nivel).toBeNull()
    expect(a.criterios.some((c) => c.id === 'repetido')).toBe(true)
  })

  it('"sem leilão" e "nunca sinistrado" não contam como risco', () => {
    expect(palavraDeRisco('Argo 2019 sem leilão, nunca sinistrado')).toBeNull()
    expect(palavraDeRisco('Argo SINISTRADO')).toBe('sinistrado')
    expect(palavraDeRisco('Veículo de leilão')).toBe('leilao')
    expect(palavraDeRisco('Argo 1.0 Drive completo')).toBeNull()
  })
})

describe('critérios', () => {
  it('km: pouco por ano, mais que os iguais, e km duvidoso', () => {
    expect(veredito(carro('x', { km: 35000 }), 'km')).toBe('favor')
    expect(veredito(carro('x', { km: 70000 }), 'km')).toBe('neutro')
    expect(veredito(carro('x', { km: 500 }), 'km')).toBe('atencao')
    expect(veredito(carro('x', { km: null }), 'km')).toBe('semdado')
  })

  it('km acima da mediana dos iguais pede cuidado', () => {
    const alvo = carro('x', { km: 100000 })
    const lista = [...mercado(alvo).map((c) => (c.external_id === 'x' ? c : { ...c, km: 60000 }))]
    const a = analisesDaPagina([alvo], agrupar(lista), AGORA).x
    expect(a.criterios.find((c) => c.id === 'km')?.veredito).toBe('atencao')
  })

  it('vendedor: particular a favor, loja neutra, loja com nota baixa pede cuidado, sem dado fica sem dado', () => {
    expect(veredito(carro('x', { anunciante_profissional: false }), 'vendedor')).toBe('favor')
    expect(veredito(carro('x', { anunciante_profissional: true, nota_anunciante: 4.6 }), 'vendedor')).toBe('neutro')
    expect(veredito(carro('x', { anunciante_profissional: true, nota_anunciante: 2.9 }), 'vendedor')).toBe('atencao')
    expect(veredito(carro('x'), 'vendedor')).toBe('semdado')
  })

  it('fotos: nenhuma e poucas pedem cuidado, muitas contam a favor', () => {
    expect(veredito(carro('x', { imagens: [] }), 'fotos')).toBe('atencao')
    expect(veredito(carro('x', { imagens: ['a', 'b'] }), 'fotos')).toBe('atencao')
    expect(veredito(carro('x', { imagens: ['a', 'b', 'c', 'd', 'e', 'f'] }), 'fotos')).toBe('favor')
  })

  it('frescor: só as primeiras horas contam, e sem data é sem dado', () => {
    const antes = (min: number) => new Date(AGORA - min * 60000).toISOString()
    expect(veredito(carro('x', { anunciado_em: antes(40) }), 'recencia')).toBe('favor')
    expect(veredito(carro('x', { anunciado_em: antes(500) }), 'recencia')).toBe('neutro')
    expect(veredito(carro('x'), 'recencia')).toBe('semdado')
  })
})

describe('textos da análise', () => {
  it('seguem as regras da tela e todo critério diz de onde veio', () => {
    const casos = [
      carro('q', { preco: 42000, km: 35000, anunciante_profissional: false, anunciado_em: new Date(AGORA - 600000).toISOString() }),
      carro('r', { preco: 30000, titulo: 'Argo sinistrado', repetido_de: 'm0', imagens: [] }),
      carro('s', { preco: 60000, km: 500, anunciante_profissional: true, nota_anunciante: 3 }),
    ]
    const lista = [...mercado(casos[0]), ...casos.slice(1)]
    for (const a of Object.values(analisesDaPagina(casos, agrupar(lista), AGORA))) {
      const textos = [a.motivo, a.resumo ?? '', ...a.criterios.flatMap((c) => [c.titulo, c.resultado, c.fato])]
      for (const t of textos) expect(t).not.toMatch(/[—–;:]/)
      for (const c of a.criterios) expect(c.fato.length).toBeGreaterThan(0)
    }
  })
})
