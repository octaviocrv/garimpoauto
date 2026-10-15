import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Anuncio, ResultadoFipe } from './types'
import { resolverFipe } from './api'

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
