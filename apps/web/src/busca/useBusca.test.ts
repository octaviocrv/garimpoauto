import { describe, expect, it } from 'vitest'
import { INICIAL, reduzir, type EstadoBusca } from './useBusca'
import type { Anuncio, RespostaPagina } from '../types'
import type { Pedido } from './pedido'
import { T } from './textos'

const pedido: Pedido = { texto: 'gol', ordenar: 'recentes', estado: 'MG' }
const carro = (id: string): Anuncio => ({ external_id: id, em_destaque: false } as Anuncio)

function resposta(pagina: number, ids: string[], extra: Partial<RespostaPagina> = {}): RespostaPagina {
  return {
    pagina, anuncios: ids.map(carro), tem_mais: true, proxima_pagina: pagina + 1, entregues: ids.length,
    coletados: ids.length, total_na_fonte: 100, cortados_por_filtro: {}, motivo_parada: null, falhou: false,
    informacao: 'Mostrando', avisos: [], filtros_na_origem: [], filtros_locais: [], busca: { texto: 'gol' },
    estado_aplicado: 'MG', coletado_em: '2026-10-10T17:32:00Z', do_cache: false, ...extra,
  }
}

const comPrimeira = (): EstadoBusca =>
  reduzir(reduzir(INICIAL, { tipo: 'iniciar', pedido }), { tipo: 'chegou', resposta: resposta(1, ['a', 'b']) })

describe('estado da busca', () => {
  it('começa em buscando e a página 1 deixa a lista pronta', () => {
    const e = comPrimeira()
    expect(e.fase).toBe('pronto')
    expect(e.anuncios.map((a) => a.external_id)).toEqual(['a', 'b'])
    expect(e.primeira?.pagina).toBe(1)
  })

  it('"Ver mais" junta a página nova no fim da lista', () => {
    let e = reduzir(comPrimeira(), { tipo: 'verMais' })
    expect(e.carregandoMais).toBe(true)
    e = reduzir(e, { tipo: 'chegou', resposta: resposta(2, ['c', 'd']) })
    expect(e.anuncios.map((a) => a.external_id)).toEqual(['a', 'b', 'c', 'd'])
    expect(e.carregandoMais).toBe(false)
    expect(e.resposta?.proxima_pagina).toBe(3)
    expect(e.primeira?.pagina).toBe(1) // a hora da coleta continua a da página 1
  })

  it('busca nova limpa a lista antiga e volta pra página 1', () => {
    const e = reduzir(comPrimeira(), { tipo: 'iniciar', pedido: { ...pedido, texto: 'onix' } })
    expect(e.fase).toBe('buscando')
    expect(e.anuncios).toEqual([])
    expect(e.resposta).toBeNull()
    expect(e.pedido?.texto).toBe('onix')
  })

  it('buscar de novo (mesmo pedido) também começa limpo', () => {
    const e = reduzir(comPrimeira(), { tipo: 'iniciar', pedido })
    expect(e.anuncios).toEqual([])
    expect(e.fase).toBe('buscando')
  })

  it('falha no "Ver mais" mantém a lista e deixa tentar a mesma página de novo', () => {
    let e = reduzir(comPrimeira(), { tipo: 'verMais' })
    e = reduzir(e, { tipo: 'chegou', resposta: resposta(2, [], { falhou: true, proxima_pagina: 2, informacao: T.maisFalhou }) })
    expect(e.anuncios).toHaveLength(2)
    expect(e.falhouMais).toBe(true)
    expect(e.carregandoMais).toBe(false)
    expect(e.resposta?.proxima_pagina).toBe(2)
  })

  it('rede caída no "Ver mais" não apaga o que já chegou', () => {
    const e = reduzir(reduzir(comPrimeira(), { tipo: 'verMais' }), { tipo: 'caiu', erro: T.semCarro })
    expect(e.anuncios).toHaveLength(2)
    expect(e.falhouMais).toBe(true)
    expect(e.fase).toBe('pronto')
  })

  it('falha na primeira página mostra a frase tranquila', () => {
    const e = reduzir(reduzir(INICIAL, { tipo: 'iniciar', pedido }), { tipo: 'chegou', resposta: resposta(1, [], { falhou: true }) })
    expect(e.fase).toBe('falhou')
    expect(e.erro).toBe(T.semCarro)
    expect(e.anuncios).toEqual([])
  })

  it('pedido ruim (422) mostra a frase do servidor', () => {
    const e = reduzir(reduzir(INICIAL, { tipo: 'iniciar', pedido }), { tipo: 'caiu', erro: T.pedidoRuim })
    expect(e.fase).toBe('falhou')
    expect(e.erro).toBe(T.pedidoRuim)
  })

  it('parar só vale enquanto busca a primeira página', () => {
    expect(reduzir(reduzir(INICIAL, { tipo: 'iniciar', pedido }), { tipo: 'parar' }).fase).toBe('parada')
    expect(reduzir(comPrimeira(), { tipo: 'parar' }).fase).toBe('pronto')
  })

  it('no fim da lista não tem mais o que pedir', () => {
    const e = reduzir(comPrimeira(), { tipo: 'chegou', resposta: resposta(2, ['c'], { tem_mais: false, proxima_pagina: null }) })
    expect(e.resposta?.tem_mais).toBe(false)
  })
})
