// @vitest-environment jsdom
import { act, StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, describe, expect, it, vi } from 'vitest'
import * as api from '../api'
import type { Anuncio, RespostaPagina } from '../types'
import { PaginaBusca } from './PaginaBusca'
import { T } from './textos'

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockReturnValue({ matches: true }),
})

vi.mock('../api', async (importOriginal) => {
  const original = await importOriginal<typeof import('../api')>()
  return {
    ...original,
    buscarPagina: vi.fn(),
    buscarRegioes: vi.fn(() => Promise.resolve([])),
    buscarZonas: vi.fn(() => Promise.resolve([])),
    resolverFipe: vi.fn(),
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

const carroComFipe = {
  source: 'olx', external_id: 'fipe-1', url: 'https://exemplo', titulo: 'Gol', marca: 'Volkswagen',
  modelo: 'Gol', modelo_original: 'Gol Trendline 1.0', ano: 2016, km: 60000, preco: 30000,
  cambio: 'manual', combustivel: 'flex', cor: null, portas: 4, cidade: 'Contagem', bairro: null,
  estado: 'MG', publicado_em: null, renovado_em: null, anunciado_em: null, em_destaque: false,
  repetido_de: null, anunciante_profissional: false, nota_anunciante: null, imagens: [], novo: false,
  incompleto: false, campos_faltando: [],
  fipe: {
    codigo: '005384-8', preco: 40000, diferenca_percentual: 25,
    mes_referencia: 'outubro de 2026', confianca: 'alta', preco_estranho: false,
  },
  fipe_bloqueio: null,
} satisfies Anuncio

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

  it('mostra uma vez o selo FIPE real dentro do StrictMode', async () => {
    const buscarPagina = vi.mocked(api.buscarPagina)
    const respostaFipe = {
      ...resposta, anuncios: [carroComFipe], entregues: 1, coletados: 1, total_na_fonte: 1,
    }
    buscarPagina.mockImplementation((_pedido, _pagina, _dev, _atualizar, signal) =>
      new Promise((resolve, reject) => {
        signal.addEventListener('abort', () => reject(new DOMException('Abortada', 'AbortError')))
        queueMicrotask(() => {
          if (!signal.aborted) resolve(respostaFipe)
        })
      }),
    )
    const container = document.createElement('div')
    document.body.appendChild(container)
    const root = createRoot(container)

    await act(async () => {
      root.render(<StrictMode><PaginaBusca /></StrictMode>)
      await new Promise((resolve) => setTimeout(resolve, 0))
    })

    await vi.waitFor(() => expect(container.textContent?.match(/25% abaixo da FIPE/g)).toHaveLength(1))
    act(() => root.unmount())
    container.remove()
  })

  it('ao abrir Garimpar resolve a FIPE e permite buscar carros iguais', async () => {
    vi.mocked(api.buscarPagina).mockResolvedValue({
      ...resposta,
      anuncios: [{ ...carroComFipe, fipe: null }],
      entregues: 1,
      coletados: 1,
      total_na_fonte: 1,
    })
    vi.mocked(api.resolverFipe).mockResolvedValue({
      fipe: carroComFipe.fipe,
      fipe_bloqueio: null,
      fipe_ausencia: null,
    })
    const container = document.createElement('div')
    document.body.appendChild(container)
    const root = createRoot(container)
    await act(async () => root.render(<PaginaBusca />))
    await vi.waitFor(() => expect(container.textContent).toContain(T.garimpar))
    const botao = container.querySelector<HTMLButtonElement>('.vehicle-card__primary')
    await act(async () => botao?.click())
    await vi.waitFor(() => expect(api.resolverFipe).toHaveBeenCalledTimes(1))
    await vi.waitFor(() => expect(container.textContent).toContain('R$ 40.000'))
    const iguais = container.querySelector<HTMLButtonElement>('.ga-buscar-iguais')
    await act(async () => iguais?.click())
    await vi.waitFor(() => expect(api.buscarPagina).toHaveBeenCalledTimes(2))
    expect(vi.mocked(api.buscarPagina).mock.calls[1][0]).toMatchObject({
      texto: 'Volkswagen Gol',
      marca: 'Volkswagen',
      modelo: 'Gol',
      ano_min: 2016,
      ano_max: 2016,
      estado: 'MG',
    })
    expect(container.querySelector('[role="dialog"]')).toBeNull()
    act(() => root.unmount())
    container.remove()
  })
})
