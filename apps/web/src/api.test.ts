import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Anuncio, ResultadoFipe } from './types'
import { ErroDetalhe, buscarDetalhe, resolverFipe, urlDetalhe } from './api'
import { T } from './busca/textos'

const anuncio = {
  source: 'olx',
  external_id: '123',
  url: 'https://exemplo',
} as Anuncio

const resultado: ResultadoFipe = {
  fipe: null,
  fipe_bloqueio: null,
  fipe_ausencia: 'sem_candidato',
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('FIPE sob demanda', () => {
  it('compartilha pedidos simultâneos do mesmo anúncio', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(resultado), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }))
    vi.stubGlobal('fetch', fetch)
    const primeira = resolverFipe(anuncio)
    const segunda = resolverFipe(anuncio)
    expect(primeira).toBe(segunda)
    await expect(primeira).resolves.toEqual(resultado)
    expect(fetch).toHaveBeenCalledTimes(1)
  })
})

describe('página do anúncio sob demanda', () => {
  const resposta = (corpo: unknown, status = 200) => new Response(JSON.stringify(corpo), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })

  it('pede o detalhe pelo id e pelo endereço do anúncio', () => {
    const url = urlDetalhe({ source: 'olx', external_id: '123', url: 'https://mg.olx.com.br/a/carro-123?x=1&y=2' })
    const q = new URL(url, 'http://x').searchParams
    expect(url.split('?')[0]).toMatch(/\/anuncio\/detalhe$/)
    expect(Object.fromEntries(q)).toEqual({ fonte: 'olx', id: '123', url: 'https://mg.olx.com.br/a/carro-123?x=1&y=2' })
  })

  it('compartilha pedidos simultâneos e pede de novo depois', async () => {
    const fetch = vi.fn().mockImplementation(() => Promise.resolve(resposta({ external_id: '123' })))
    vi.stubGlobal('fetch', fetch)
    const primeira = buscarDetalhe(anuncio)
    expect(buscarDetalhe(anuncio)).toBe(primeira)
    await primeira
    await buscarDetalhe(anuncio)
    expect(fetch).toHaveBeenCalledTimes(2)
  })

  it('usa a frase do servidor e sabe quando não adianta tentar de novo', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(resposta({ erro: 'Esse anúncio saiu do ar na OLX.' }, 404)))
    const saiu = await buscarDetalhe(anuncio).catch((e) => e)
    expect(saiu).toBeInstanceOf(ErroDetalhe)
    expect(saiu).toMatchObject({ message: 'Esse anúncio saiu do ar na OLX.', podeTentar: false })

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('quebrou', { status: 502 })))
    await expect(buscarDetalhe(anuncio)).rejects.toMatchObject({ message: T.detalheFalhou, podeTentar: true })

    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('rede')))
    await expect(buscarDetalhe(anuncio)).rejects.toMatchObject({ message: T.detalheFalhou, podeTentar: true })
  })
})
