import { describe, expect, it } from 'vitest'
import { criarLeitorSse, type EventoSse } from './sse'
import { montarUrl } from '../api'

function ler(pedacos: string[]): EventoSse[] {
  const saida: EventoSse[] = []
  const leitor = criarLeitorSse((e) => saida.push(e))
  pedacos.forEach((p) => leitor.empurrar(p))
  return saida
}

describe('leitor de SSE', () => {
  it('lê eventos inteiros', () => {
    const e = ler(['event: pagina\ndata: {"numero":1}\n\nevent: fim\ndata: {"ok":true}\n\n'])
    expect(e).toEqual([{ nome: 'pagina', dados: { numero: 1 } }, { nome: 'fim', dados: { ok: true } }])
  })

  it('junta um evento que chegou picado em vários pedaços', () => {
    const e = ler(['event: pag', 'ina\ndata: {"nu', 'mero":2}\n', '\n'])
    expect(e).toEqual([{ nome: 'pagina', dados: { numero: 2 } }])
  })

  it('ignora sinal de vida e aceita CRLF e acento', () => {
    const e = ler([': aguardando\n\n', 'event: pagina\r\ndata: {"c":"São João"}\r\n\r\n'])
    expect(e).toEqual([{ nome: 'pagina', dados: { c: 'São João' } }])
  })

  it('evento quebrado não derruba os seguintes', () => {
    const e = ler(['event: pagina\ndata: {quebrado\n\nevent: fim\ndata: {}\n\n'])
    expect(e.map((x) => x.nome)).toEqual(['fim'])
  })
})

describe('url da busca', () => {
  it('manda só o que foi preenchido', () => {
    expect(montarUrl({ texto: 'gol' }, false)).toBe('/api/buscar/stream?texto=gol')
  })
  it('manda marca e ano junto, e dev quando pedido', () => {
    const u = new URL(montarUrl({ texto: 'civic g10', marca: 'Honda', ano_min: 2015, ano_max: 2018 }, true), 'http://x')
    expect(Object.fromEntries(u.searchParams)).toEqual({
      texto: 'civic g10', marca: 'Honda', ano_min: '2015', ano_max: '2018', dev: '1',
    })
  })
})
