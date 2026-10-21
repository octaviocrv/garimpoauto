// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import * as api from '../api'
import type { DetalheAnuncio } from '../types'
import { FichaAnuncio } from './FichaAnuncio'
import { GARIMPAR_TEXTOS as GT } from './garimparTextos'

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

vi.mock('../api', async (importOriginal) => {
  const original = await importOriginal<typeof import('../api')>()
  return { ...original, buscarDetalhe: vi.fn() }
})

const anuncio = { source: 'olx', external_id: '1546298897', url: 'https://mg.olx.com.br/a/onix-1546298897' }

const detalhe: DetalheAnuncio = {
  source: 'olx',
  external_id: '1546298897',
  url: anuncio.url,
  detalhes: {
    categoria: 'Carros, vans e utilitários', modelo: 'Onix Hatch LT', marca: 'Chevrolet', tipo: 'Hatch',
    ano: 2024, km: 19798, potencia: '1.0', combustivel: 'Flex', cambio: 'Manual', direcao: 'Elétrica',
    cor: 'Prata', portas: '4 portas', final_placa: null, kit_gnv: 'Não',
  },
  opcionais: ['Air bag', 'Ar condicionado', 'Alarme'],
  outras: ['Aceita trocas', 'IPVA pago'],
  localizacao: { bairro: 'Centro', cidade: 'Poços de Caldas', estado: 'MG', cep: '37701740' },
  descricao: 'Primeira linha\n\nSegunda linha',
  coletado_em: '2026-10-10T12:00:00Z',
}

let container: HTMLDivElement
let root: Root

beforeEach(() => {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
})

afterEach(() => {
  act(() => root.unmount())
  container.remove()
  vi.clearAllMocks()
})

const montar = () => act(async () => root.render(<FichaAnuncio anuncio={anuncio} />))
const botaoTentar = () => [...container.querySelectorAll('button')].find((b) => b.textContent === GT.fichaTentar)

describe('ficha do anúncio no Garimpar', () => {
  it('mostra o carregando enquanto a página do anúncio não chega', async () => {
    vi.mocked(api.buscarDetalhe).mockReturnValue(new Promise(() => {}))
    await montar()
    const status = container.querySelector('[role="status"][aria-busy="true"]')
    expect(status?.textContent).toContain(GT.fichaCarregando)
    expect(api.buscarDetalhe).toHaveBeenCalledWith(anuncio)
  })

  it('mostra detalhes, opcionais, outras características, local e descrição', async () => {
    vi.mocked(api.buscarDetalhe).mockResolvedValue(detalhe)
    await montar()
    await vi.waitFor(() => expect(container.textContent).toContain(GT.fichaDetalhes))
    const texto = container.textContent ?? ''
    for (const esperado of ['Chevrolet', 'Hatch', '19.798 km', '4 portas', 'Air bag', 'Aceita trocas', 'IPVA pago',
      'Centro', 'Poços de Caldas', 'MG', '37701-740', GT.rotuloTipo]) {
      expect(texto).toContain(esperado)
    }
    expect(texto).not.toContain(GT.rotuloFinalPlaca)
    expect(container.querySelector('.ga-ficha__descricao')?.textContent).toBe('Primeira linha\n\nSegunda linha')
    expect(container.querySelector('[aria-busy="true"]')).toBeNull()
  })

  it('campos e listas vazias viram frases calmas', async () => {
    vi.mocked(api.buscarDetalhe).mockResolvedValue({
      ...detalhe,
      detalhes: Object.fromEntries(Object.keys(detalhe.detalhes).map((k) => [k, null])) as unknown as DetalheAnuncio['detalhes'],
      opcionais: [],
      outras: [],
      localizacao: { bairro: null, cidade: null, estado: null, cep: null },
      descricao: null,
    })
    await montar()
    await vi.waitFor(() => expect(container.textContent).toContain(GT.fichaSemDescricao))
    for (const frase of [GT.fichaSemDetalhes, GT.fichaSemOpcionais, GT.fichaSemOutras, GT.fichaSemLocal]) {
      expect(container.textContent).toContain(frase)
    }
  })

  it('erro mostra a frase e tenta de novo no clique', async () => {
    vi.mocked(api.buscarDetalhe)
      .mockRejectedValueOnce(new api.ErroDetalhe('Não consegui abrir esse anúncio na OLX agora, tenta de novo?', true))
      .mockResolvedValueOnce(detalhe)
    await montar()
    await vi.waitFor(() => expect(botaoTentar()).toBeDefined())
    expect(container.textContent).toContain('tenta de novo?')
    await act(async () => botaoTentar()?.click())
    await vi.waitFor(() => expect(container.textContent).toContain('Poços de Caldas'))
    expect(api.buscarDetalhe).toHaveBeenCalledTimes(2)
  })

  it('anúncio fora do ar não oferece tentar de novo', async () => {
    vi.mocked(api.buscarDetalhe).mockRejectedValue(new api.ErroDetalhe('Esse anúncio saiu do ar na OLX.', false))
    await montar()
    await vi.waitFor(() => expect(container.textContent).toContain('saiu do ar'))
    expect(botaoTentar()).toBeUndefined()
  })

  it('não mostra dados de outro anúncio', async () => {
    vi.mocked(api.buscarDetalhe).mockResolvedValue({ ...detalhe, external_id: '999' })
    await montar()
    await vi.waitFor(() => expect(botaoTentar()).toBeDefined())
    expect(container.textContent).not.toContain('Poços de Caldas')
  })
})
