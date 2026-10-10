// @vitest-environment jsdom
import { act, StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, describe, expect, it, vi } from 'vitest'
import * as api from '../api'
import type { RespostaPagina } from '../types'
import { PaginaBusca } from './PaginaBusca'
import { T } from './textos'

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

vi.mock('../api', async (importOriginal) => {
  const original = await importOriginal<typeof import('../api')>()
  return {
    ...original,
    buscarPagina: vi.fn(),
    buscarRegioes: vi.fn(() => Promise.resolve([])),
    buscarZonas: vi.fn(() => Promise.resolve([])),
  }
})

const resposta: RespostaPagina = {
  pagina: 1,
  anuncios: [],
  tem_mais: false,
  proxima_pagina: null,
  entregues: 0,
  coletados: 0,
  total_na_fonte: 0,
  cortados_por_filtro: {},
  motivo_parada: null,
  falhou: false,
  informacao: 'Não achei nenhum carro agora.',
  avisos: [],
  filtros_na_origem: [],
  filtros_locais: [],
  busca: { texto: '' },
  estado_aplicado: 'MG',
  coletado_em: '2026-10-10T15:00:00Z',
  do_cache: false,
}

afterEach(() => {
  vi.clearAllMocks()
})

describe('vitrine ao abrir', () => {
  it('repete o pedido abortado pelo StrictMode e sai do carregamento', async () => {
    const buscarPagina = vi.mocked(api.buscarPagina)
    buscarPagina.mockImplementation((_pedido, _pagina, _dev, _atualizar, signal) =>
      new Promise((resolve, reject) => {
        signal.addEventListener('abort', () => reject(new DOMException('Abortada', 'AbortError')))
        queueMicrotask(() => {
          if (!signal.aborted) resolve(resposta)
        })
      }),
    )

    const container = document.createElement('div')
    document.body.appendChild(container)
    const root = createRoot(container)

    await act(async () => {
      root.render(
        <StrictMode>
          <PaginaBusca />
        </StrictMode>,
      )
      await vi.waitFor(() => expect(container.textContent).not.toContain(T.garimpando))
    })

    expect(buscarPagina).toHaveBeenCalledTimes(2)

    act(() => root.unmount())
    container.remove()
  })
})
