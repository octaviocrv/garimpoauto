import { describe, expect, it } from 'vitest'
import { RASCUNHO_VAZIO, montarPedido, nomeDoEstado, ESTADOS } from './pedido'
import { montarUrl } from '../api'

describe('montarPedido', () => {
  it('sem texto não busca', () => {
    expect(montarPedido({ ...RASCUNHO_VAZIO, texto: '   ' })).toBeNull()
  })

  it('padrão é Minas e ordem por mais recentes, sem filtro nenhum', () => {
    expect(montarPedido({ ...RASCUNHO_VAZIO, texto: ' gol 2012 ' })).toEqual({
      texto: 'gol 2012', ordenar: 'recentes', estado: 'MG',
      marca: undefined, modelo: undefined, versao: undefined, ano_min: undefined, ano_max: undefined,
      preco_min: undefined, preco_max: undefined, km_min: undefined, km_max: undefined,
      cambio: undefined, combustivel: undefined, anunciante: undefined, cidade: undefined,
    })
  })

  it('números aceitam ponto e R$ e viram inteiro', () => {
    const p = montarPedido({ ...RASCUNHO_VAZIO, texto: 'x', precoMax: 'R$ 80.000', kmMax: '50.000', anoMin: '2015' })
    expect(p).toMatchObject({ preco_max: 80000, km_max: 50000, ano_min: 2015 })
  })

  it('mínimo maior que máximo troca de lugar em vez de dar erro', () => {
    const p = montarPedido({ ...RASCUNHO_VAZIO, texto: 'x', anoMin: '2020', anoMax: '2015', kmMin: '90000', kmMax: '10000' })
    expect(p).toMatchObject({ ano_min: 2015, ano_max: 2020, km_min: 10000, km_max: 90000 })
  })

  it('leva todos os filtros que o servidor aceita', () => {
    const p = montarPedido({
      ...RASCUNHO_VAZIO, texto: 'civic', estado: 'todos', marca: 'Honda', modelo: 'Civic', versao: 'Touring',
      cambio: 'automatico', combustivel: 'flex', anunciante: 'profissional', cidade: 'Contagem', ordenar: 'menor_preco',
    })
    expect(p).toMatchObject({
      estado: 'todos', marca: 'Honda', modelo: 'Civic', versao: 'Touring', cambio: 'automatico',
      combustivel: 'flex', anunciante: 'profissional', cidade: 'Contagem', ordenar: 'menor_preco',
    })
  })
})

describe('estados', () => {
  it('Brasil todo é a primeira opção e as 27 siglas estão aí', () => {
    expect(ESTADOS[0]).toEqual(['todos', 'Brasil todo'])
    expect(ESTADOS).toHaveLength(28)
    expect(nomeDoEstado('MG')).toBe('Minas Gerais')
    expect(nomeDoEstado('todos')).toBe('Brasil todo')
  })
})

describe('url da busca por página', () => {
  const pedido = montarPedido({ ...RASCUNHO_VAZIO, texto: 'fiat argo', marca: 'Fiat', anoMin: '2020' })!
  const params = (url: string) => Object.fromEntries(new URL(url, 'http://x').searchParams)

  it('manda só o que foi preenchido, com a página', () => {
    expect(params(montarUrl(pedido, 1, false, false))).toEqual({
      texto: 'fiat argo', ordenar: 'recentes', estado: 'MG', marca: 'Fiat', ano_min: '2020', pagina: '1',
    })
    expect(montarUrl(pedido, 1, false, false)).toMatch(/^\/api\/buscar\/pagina\?/)
  })

  it('"buscar de novo" manda atualizar só na página 1', () => {
    expect(params(montarUrl(pedido, 1, false, true)).atualizar).toBe('1')
    expect(params(montarUrl(pedido, 2, false, true)).atualizar).toBeUndefined()
  })

  it('dev só quando pedido', () => {
    expect(params(montarUrl(pedido, 3, true, false))).toMatchObject({ dev: '1', pagina: '3' })
    expect(params(montarUrl(pedido, 3, false, false)).dev).toBeUndefined()
  })
})
