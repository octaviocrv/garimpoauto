// @vitest-environment jsdom
// O painel de filtros de verdade: o que a pessoa preenche chega no pedido, Enter e Limpar buscam, o número
// do botão Filtros e o Ver mais quando os filtros daqui esvaziam uma página.
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, describe, expect, it, vi } from 'vitest'
import * as api from '../api'
import type { Anuncio, RespostaPagina } from '../types'
import { PaginaBusca } from './PaginaBusca'
import type { Pedido } from './pedido'
import { T } from './textos'

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

vi.mock('../api', async (importOriginal) => {
  const original = await importOriginal<typeof import('../api')>()
  return {
    ...original,
    buscarPagina: vi.fn(),
    buscarRegioes: vi.fn(() => Promise.resolve([{ slug: 'belo-horizonte-e-regiao', nome: 'Belo Horizonte e região' }])),
    buscarZonas: vi.fn(() => Promise.resolve([{ slug: 'barreiro', nome: 'Barreiro' }])),
    buscarDetalhe: vi.fn(() => new Promise(() => {})),
  }
})

const carro = (id: string): Anuncio => ({
  source: 'olx', external_id: id, url: `https://mg.olx.com.br/autos-e-pecas/carros/civic-${id}`, titulo: `Honda Civic ${id}`,
  marca: 'Honda', modelo: 'Civic', modelo_original: 'Civic Sedan EXL 2.0', ano: 2018, km: 60000, preco: 90000,
  cambio: 'Automático', combustivel: 'Flex', cor: null, portas: 4, cidade: 'Contagem', bairro: null, estado: 'MG',
  publicado_em: null, renovado_em: null, anunciado_em: null, em_destaque: false, repetido_de: null,
  anunciante_profissional: false, nota_anunciante: null, imagens: [], novo: false, incompleto: false, campos_faltando: [],
})

const resposta = (extra: Partial<RespostaPagina> = {}): RespostaPagina => ({
  pagina: 1, anuncios: [], tem_mais: false, proxima_pagina: null, entregues: 0, coletados: 0, total_na_fonte: 0,
  cortados_por_filtro: {}, motivo_parada: null, falhou: false, informacao: 'Achei 0 carros.', avisos: [],
  filtros_na_origem: [], filtros_locais: [], busca: { texto: '' }, estado_aplicado: 'MG',
  coletado_em: '2026-10-21T15:00:00Z', do_cache: false, ...extra,
})

const AINDA_NAO = 'Ainda não achei carro com esses filtros. Toca em Ver mais pra procurar no resto.'

let container: HTMLDivElement
let root: Root

async function abrirTela() {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => root.render(<PaginaBusca />))
  await vi.waitFor(() => expect(api.buscarPagina).toHaveBeenCalledTimes(1)) // a vitrine ao abrir
}

afterEach(() => {
  act(() => root.unmount())
  container.remove()
  vi.clearAllMocks()
  vi.mocked(api.buscarPagina).mockReset() // a resposta "once" que sobrou não passa pro próximo teste
})

const chamadas = () => vi.mocked(api.buscarPagina).mock.calls
const ultimoPedido = (): Pedido => chamadas()[chamadas().length - 1][0]
const botaoFiltros = () => container.querySelector<HTMLButtonElement>('button[aria-expanded]')!
const contador = () => Number(botaoFiltros().textContent!.replace(/\D/g, '') || 0)
const botao = (texto: string) => [...container.querySelectorAll('button')].find((b) => b.textContent?.trim() === texto)
const cards = () => container.querySelectorAll('.vehicle-card').length

function campo(nome: string): HTMLInputElement | HTMLSelectElement {
  const label = [...container.querySelectorAll('.filter-panel label')].find((l) => l.querySelector('span')?.textContent === nome)
  const el = label?.querySelector<HTMLInputElement | HTMLSelectElement>('input, select')
  if (!el) throw new Error(`campo ${nome} não está no painel`)
  return el
}

async function preencher(el: HTMLInputElement | HTMLSelectElement, valor: string) {
  const select = el instanceof HTMLSelectElement
  await act(async () => {
    Object.getOwnPropertyDescriptor(select ? HTMLSelectElement.prototype : HTMLInputElement.prototype, 'value')!.set!.call(el, valor)
    el.dispatchEvent(new Event(select ? 'change' : 'input', { bubbles: true }))
  })
}

const clicar = (el: HTMLElement | undefined) => act(async () => el!.click())
const apertarBuscar = () => clicar(container.querySelector<HTMLButtonElement>('button[type="submit"]')!)
const abrirPainel = () => clicar(botaoFiltros())

async function escolherRegiaoEZona() {
  await vi.waitFor(() => expect(campo('Região').querySelectorAll('option')).toHaveLength(2))
  await preencher(campo('Região'), 'belo-horizonte-e-regiao')
  await vi.waitFor(() => expect(campo('Zona').querySelectorAll('option')).toHaveLength(2))
  await preencher(campo('Zona'), 'barreiro')
}

describe('painel de filtros', () => {
  it('cada campo chega no pedido que vai pro servidor', async () => {
    vi.mocked(api.buscarPagina).mockResolvedValue(resposta())
    await abrirTela()
    await abrirPainel()
    await escolherRegiaoEZona()
    const preenchidos: [string, string][] = [
      ['Marca', 'Honda'], ['Modelo', 'Civic'], ['Versão', 'EXL'], ['Ano mínimo', '2015'], ['Ano máximo', '2020'],
      ['Preço mínimo', 'R$ 50.000,00'], ['Preço máximo', '120 mil'], ['Km mínimo', '10.000'], ['Km máximo', '80k'],
      ['Câmbio', 'automatico'], ['Combustível', 'flex'], ['Anunciante', 'profissional'], ['Cidade', 'Belo Horizonte'],
      ['Ordenar por', 'menor_preco'],
    ]
    for (const [nome, valor] of preenchidos) await preencher(campo(nome), valor)
    await preencher(container.querySelector<HTMLInputElement>('input[type="search"]')!, ' civic ')
    expect(contador()).toBe(15)

    await apertarBuscar()

    expect(ultimoPedido()).toEqual({
      texto: 'civic', estado: 'MG', ordenar: 'menor_preco', regiao: 'belo-horizonte-e-regiao', zona: 'barreiro',
      marca: 'Honda', modelo: 'Civic', versao: 'EXL', ano_min: 2015, ano_max: 2020, preco_min: 50000, preco_max: 120000,
      km_min: 10000, km_max: 80000, cambio: 'automatico', combustivel: 'flex', anunciante: 'profissional',
      cidade: 'Belo Horizonte',
    })
    expect(chamadas()[chamadas().length - 1][1]).toBe(1)
  })

  it('Brasil todo tira região e zona da busca', async () => {
    vi.mocked(api.buscarPagina).mockResolvedValue(resposta())
    await abrirTela()
    await abrirPainel()
    await escolherRegiaoEZona()
    await preencher(container.querySelector<HTMLSelectElement>('select[aria-label="Estado"]')!, 'todos')
    expect(() => campo('Região')).toThrow()
    await apertarBuscar()
    expect(ultimoPedido()).toEqual({ texto: '', estado: 'todos', ordenar: 'recentes' })
  })

  it('Enter num campo do painel busca na hora, igual ao campo de cima', async () => {
    vi.mocked(api.buscarPagina).mockResolvedValue(resposta())
    await abrirTela()
    await abrirPainel()
    await preencher(campo('Ano mínimo'), '2018')
    await preencher(campo('Marca'), 'Fiat')
    const antes = chamadas().length

    await act(async () => campo('Marca').dispatchEvent(new KeyboardEvent('keydown', { key: 'a', bubbles: true })))
    expect(chamadas()).toHaveLength(antes)

    await act(async () => campo('Marca').dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })))
    expect(chamadas()).toHaveLength(antes + 1)
    expect(ultimoPedido()).toEqual({ texto: '', estado: 'MG', ordenar: 'recentes', ano_min: 2018, marca: 'Fiat' })
  })

  it('Limpar tira os filtros, guarda texto e estado e já busca sem eles', async () => {
    vi.mocked(api.buscarPagina).mockResolvedValue(resposta())
    await abrirTela()
    await abrirPainel()
    await preencher(container.querySelector<HTMLSelectElement>('select[aria-label="Estado"]')!, 'SP')
    await preencher(container.querySelector<HTMLInputElement>('input[type="search"]')!, 'civic')
    await preencher(campo('Marca'), 'Honda')
    await preencher(campo('Ano mínimo'), '2018')
    await preencher(campo('Câmbio'), 'manual')
    await apertarBuscar()
    expect(ultimoPedido()).toMatchObject({ texto: 'civic', estado: 'SP', marca: 'Honda', ano_min: 2018, cambio: 'manual' })
    const antes = chamadas().length

    await clicar(botao(T.limparFiltros))

    expect(chamadas()).toHaveLength(antes + 1)
    expect(ultimoPedido()).toEqual({ texto: 'civic', estado: 'SP', ordenar: 'recentes' })
    expect(campo('Marca').value).toBe('')
    expect(campo('Câmbio').value).toBe('')
    expect(contador()).toBe(0)
  })

  it('o número do botão Filtros conta só o que vai na busca', async () => {
    vi.mocked(api.buscarPagina).mockResolvedValue(resposta())
    await abrirTela()
    await abrirPainel()
    await preencher(campo('Marca'), '   ')
    await preencher(campo('Ano mínimo'), 'abc')
    expect(contador()).toBe(0)
    await preencher(campo('Ano mínimo'), '2018')
    expect(contador()).toBe(1)
    await preencher(campo('Marca'), 'Fiat')
    await preencher(campo('Anunciante'), 'particular')
    expect(contador()).toBe(3)
  })
})

describe('Ver mais quando os filtros daqui esvaziam a página', () => {
  it('lista vazia com mais páginas na OLX mostra Ver mais e pede a próxima com a mesma busca', async () => {
    const buscarPagina = vi.mocked(api.buscarPagina)
    buscarPagina
      .mockResolvedValueOnce(resposta({ tem_mais: true, proxima_pagina: 2, coletados: 50, total_na_fonte: 300, cortados_por_filtro: { km: 50 }, informacao: AINDA_NAO }))
      .mockResolvedValueOnce(resposta({ pagina: 2, anuncios: [carro('1')], entregues: 1, coletados: 100, informacao: 'Achei 1 carro. Esses são todos.' }))
    await abrirTela()
    await vi.waitFor(() => expect(container.textContent).toContain(AINDA_NAO))
    expect(botao(T.buscarDeNovo)).toBeDefined()
    expect(botao(T.verMais)).toBeDefined()

    await clicar(botao(T.verMais))

    await vi.waitFor(() => expect(cards()).toBe(1))
    expect(chamadas()[1][1]).toBe(2)
    expect(chamadas()[1][0]).toEqual(chamadas()[0][0])
    expect(botao(T.verMais)).toBeUndefined()
  })

  it('sem mais páginas não mostra Ver mais, só Buscar de novo', async () => {
    vi.mocked(api.buscarPagina).mockResolvedValue(resposta({ informacao: T.nenhumComFiltro }))
    await abrirTela()
    await vi.waitFor(() => expect(container.textContent).toContain(T.nenhumComFiltro))
    expect(botao(T.verMais)).toBeUndefined()
    expect(botao(T.buscarDeNovo)).toBeDefined()
  })

  it('se o Ver mais falha com a lista vazia, avisa e deixa tentar de novo', async () => {
    vi.mocked(api.buscarPagina)
      .mockResolvedValueOnce(resposta({ tem_mais: true, proxima_pagina: 2, informacao: AINDA_NAO }))
      .mockRejectedValueOnce(new api.ErroBusca(T.semCarro))
      .mockResolvedValueOnce(resposta({ pagina: 2, anuncios: [carro('1')], entregues: 1 }))
    await abrirTela()
    await vi.waitFor(() => expect(botao(T.verMais)).toBeDefined())

    await clicar(botao(T.verMais))
    await vi.waitFor(() => expect(container.textContent).toContain(T.maisFalhou))
    expect(container.textContent).toContain(AINDA_NAO)

    await clicar(botao(T.tentarDeNovo))
    await vi.waitFor(() => expect(cards()).toBe(1))
    expect(chamadas().map((c) => c[1])).toEqual([1, 2, 2])
  })

  it('página que os filtros esvaziaram no meio não deixa buraco na lista', async () => {
    vi.mocked(api.buscarPagina)
      .mockResolvedValueOnce(resposta({ anuncios: [carro('1')], entregues: 1, tem_mais: true, proxima_pagina: 2, informacao: 'Mostrando 1 de 300 carros.' }))
      .mockResolvedValueOnce(resposta({ pagina: 2, entregues: 1, tem_mais: true, proxima_pagina: 3, informacao: 'Mostrando 1 de 300 carros.' }))
      .mockResolvedValueOnce(resposta({ pagina: 3, anuncios: [carro('3')], entregues: 2, informacao: 'Achei 2 carros.' }))
    await abrirTela()
    await vi.waitFor(() => expect(cards()).toBe(1))
    await clicar(botao(T.verMais))
    await vi.waitFor(() => expect(chamadas()).toHaveLength(2))
    await vi.waitFor(() => expect(botao(T.verMais)?.disabled).toBe(false))
    await clicar(botao(T.verMais))
    await vi.waitFor(() => expect(cards()).toBe(2))
    expect(container.querySelectorAll('ul.vehicle-grid')).toHaveLength(2)
  })
})
