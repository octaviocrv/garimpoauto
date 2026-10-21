// Cada filtro do painel, do que a pessoa digita até a URL que vai pro servidor. O servidor e a OLX
// estão cobertos em scraper/tests/test_filtros.py.
import { describe, expect, it } from 'vitest'
import { montarUrl } from '../api'
import {
  ANUNCIANTES, CAMBIOS, COMBUSTIVEIS, ESTADOS, ORDENS, RASCUNHO_VAZIO, contarFiltros, montarPedido,
  montarPedidoOuVitrine, numero, type Rascunho,
} from './pedido'

const params = (url: string) => Object.fromEntries(new URL(url, 'http://x').searchParams)
const pedido = (r: Partial<Rascunho>) => montarPedidoOuVitrine({ ...RASCUNHO_VAZIO, ...r })
const url = (r: Partial<Rascunho>, pagina = 1) => params(montarUrl(pedido(r), pagina, false, false))
const VITRINE = { texto: '', ordenar: 'recentes', estado: 'MG', pagina: '1' }
const opcoes = (lista: readonly (readonly [string, string])[]) => lista.map(([valor]) => valor).filter(Boolean)

const TUDO: Partial<Rascunho> = {
  texto: ' civic ', estado: 'MG', regiao: 'belo-horizonte-e-regiao', zona: 'barreiro', marca: 'Honda', modelo: 'Civic',
  versao: 'EXL', anoMin: '2015', anoMax: '2020', precoMin: 'R$ 50.000,00', precoMax: '120 mil', kmMin: '10.000',
  kmMax: '80k', cambio: 'automatico', combustivel: 'flex', anunciante: 'profissional', cidade: 'Belo Horizonte',
  ordenar: 'menor_preco',
}

describe('número digitado', () => {
  it.each([
    ['2018', 2018], ['  2015  ', 2015], ['0', 0], ['R$ 50.000,00', 50000], ['R$ 80.000', 80000], ['50.000', 50000],
    ['50,000', 50000], ['1.000.000', 1000000], ['120 000', 120000], ['50 000,00', 50000], ['2.020', 2020],
    ['120.000 km', 120000], ['50 mil', 50000], ['50mil', 50000], ['50 MIL', 50000], ['1,5 mil', 1500],
    ['35.9 mil', 35900], ['100 mil km', 100000], ['50k', 50000], ['2.5K', 2500], ['R$ 1.234,56', 1235],
  ])('"%s" vira %s', (digitado, esperado) => expect(numero(digitado)).toBe(esperado))

  it.each(['', '   ', 'abc', 'R$', 'mil', 'k', '-', '.,', 'km'])('"%s" fica de fora da busca', (digitado) => {
    expect(numero(digitado)).toBeUndefined()
  })

  it('"mil" e "k" só multiplicam colados no número', () => {
    expect(numero('80 milhas')).toBe(80)
    expect(numero('5 kg')).toBe(5)
    expect(numero('120.000 km')).toBe(120000)
  })

  it('pega só o primeiro número e nunca manda negativo, que o servidor recusaria', () => {
    expect(numero('2010 a 2015')).toBe(2010)
    expect(numero('2010 2015')).toBe(2010)
    expect(numero('-5000')).toBe(5000)
  })

  it('número grande demais fica de fora em vez de virar 1e+21 na URL', () => {
    expect(numero('9'.repeat(25))).toBeUndefined()
    expect(numero('9'.repeat(15))).toBe(999999999999999)
  })
})

describe('cada filtro do painel vai na URL', () => {
  it.each<[string, Partial<Rascunho>, Record<string, string>]>([
    ['texto', { texto: ' civic ' }, { texto: 'civic' }],
    ['estado', { estado: 'SP' }, { estado: 'SP' }],
    ['Brasil todo', { estado: 'todos' }, { estado: 'todos' }],
    ['região', { regiao: 'belo-horizonte-e-regiao' }, { regiao: 'belo-horizonte-e-regiao' }],
    ['zona', { regiao: 'belo-horizonte-e-regiao', zona: 'barreiro' }, { regiao: 'belo-horizonte-e-regiao', zona: 'barreiro' }],
    ['cidade', { cidade: ' São João del-Rei ' }, { cidade: 'São João del-Rei' }],
    ['marca', { marca: ' Honda ' }, { marca: 'Honda' }],
    ['modelo', { modelo: 'HR-V' }, { modelo: 'HR-V' }],
    ['versão', { versao: 'EXL 2.0' }, { versao: 'EXL 2.0' }],
    ['ano mínimo', { anoMin: '2018' }, { ano_min: '2018' }],
    ['ano máximo', { anoMax: '2020' }, { ano_max: '2020' }],
    ['preço mínimo', { precoMin: 'R$ 30.000' }, { preco_min: '30000' }],
    ['preço máximo', { precoMax: '80 mil' }, { preco_max: '80000' }],
    ['km mínimo', { kmMin: '10.000' }, { km_min: '10000' }],
    ['km máximo', { kmMax: '120 mil' }, { km_max: '120000' }],
    ['km zero', { kmMax: '0' }, { km_max: '0' }],
  ])('%s', (_nome, rascunho, esperado) => {
    expect(url(rascunho)).toEqual({ ...VITRINE, ...esperado })
  })

  it.each(opcoes(CAMBIOS))('câmbio %s', (valor) => expect(url({ cambio: valor })).toEqual({ ...VITRINE, cambio: valor }))
  it.each(opcoes(COMBUSTIVEIS))('combustível %s', (valor) => {
    expect(url({ combustivel: valor })).toEqual({ ...VITRINE, combustivel: valor })
  })
  it.each(opcoes(ANUNCIANTES))('anunciante %s', (valor) => {
    expect(url({ anunciante: valor })).toEqual({ ...VITRINE, anunciante: valor })
  })
  it.each(opcoes(ORDENS))('ordenar %s', (valor) => expect(url({ ordenar: valor })).toEqual({ ...VITRINE, ordenar: valor }))

  it('"Qualquer" não manda nada', () => {
    expect(url({ cambio: '', combustivel: '', anunciante: '' })).toEqual(VITRINE)
  })

  it('as opções da tela são as que o servidor aceita', () => {
    // Iguais a scraper/schemas.py. O test_filtros.py confere o mesmo do lado do servidor.
    expect(opcoes(CAMBIOS)).toEqual(['manual', 'automatico', 'semi-automatico', 'automatizado'])
    expect(opcoes(COMBUSTIVEIS)).toEqual(['gasolina', 'alcool', 'flex', 'diesel', 'hibrido', 'eletrico'])
    expect(opcoes(ANUNCIANTES).sort()).toEqual(['particular', 'profissional'])
    expect(opcoes(ORDENS).sort()).toEqual(['menor_preco', 'recentes', 'relevancia'])
    expect(ESTADOS.map(([sigla]) => sigla).filter((s) => s !== 'todos')).toHaveLength(27)
  })
})

describe('filtros juntos', () => {
  it('tudo preenchido vai junto, com os números já lidos', () => {
    expect(url(TUDO)).toEqual({
      texto: 'civic', estado: 'MG', ordenar: 'menor_preco', pagina: '1', regiao: 'belo-horizonte-e-regiao', zona: 'barreiro',
      marca: 'Honda', modelo: 'Civic', versao: 'EXL', ano_min: '2015', ano_max: '2020', preco_min: '50000',
      preco_max: '120000', km_min: '10000', km_max: '80000', cambio: 'automatico', combustivel: 'flex',
      anunciante: 'profissional', cidade: 'Belo Horizonte',
    })
  })

  it('o Ver mais leva os mesmos filtros, só muda a página', () => {
    const { pagina: p1, ...primeira } = url(TUDO)
    const { pagina: p3, ...terceira } = url(TUDO, 3)
    expect([p1, p3]).toEqual(['1', '3'])
    expect(terceira).toEqual(primeira)
  })

  it('sem texto e com filtro busca com o filtro, a busca digitada continua exigindo texto', () => {
    expect(url({ marca: 'Fiat', cambio: 'manual' })).toEqual({ ...VITRINE, marca: 'Fiat', cambio: 'manual' })
    expect(montarPedido({ ...RASCUNHO_VAZIO, marca: 'Fiat' })).toBeNull()
  })

  it('mínimo maior que o máximo troca de lugar em ano, preço e km', () => {
    expect(url({ anoMin: '2020', anoMax: '2015', precoMin: '90 mil', precoMax: '30.000', kmMin: '100k', kmMax: '5000' }))
      .toMatchObject({ ano_min: '2015', ano_max: '2020', preco_min: '30000', preco_max: '90000', km_min: '5000', km_max: '100000' })
  })

  it('mínimo igual ao máximo vale como valor exato', () => {
    expect(url({ anoMin: '2018', anoMax: '2018' })).toMatchObject({ ano_min: '2018', ano_max: '2018' })
  })
})

describe('campos vazios e valores ruins', () => {
  it('campo só com espaço não vai', () => {
    expect(url({ texto: '   ', marca: '  ', modelo: ' ', versao: '\t', cidade: '  ', regiao: ' ', anoMin: ' ', precoMax: '  ' }))
      .toEqual(VITRINE)
  })

  it('número sem número nenhum não vai e não quebra a busca', () => {
    expect(url({ anoMin: 'abc', anoMax: 'R$', precoMin: 'mil', precoMax: '-', kmMin: '.,', kmMax: 'km' })).toEqual(VITRINE)
  })

  it('um lado da faixa ruim não estraga o outro', () => {
    expect(url({ anoMin: 'abc', anoMax: '2020' })).toEqual({ ...VITRINE, ano_max: '2020' })
  })

  it('zona sem região e região no Brasil todo não vão, o servidor responderia 422', () => {
    expect(url({ zona: 'barreiro' })).toEqual(VITRINE)
    expect(url({ estado: 'todos', regiao: 'belo-horizonte-e-regiao', zona: 'barreiro' })).toEqual({ ...VITRINE, estado: 'todos' })
  })

  it('estado vazio usa o padrão e ordem vazia usa mais recentes', () => {
    expect(url({ estado: '', ordenar: '' })).toEqual(VITRINE)
  })
})

describe('número no botão Filtros', () => {
  it('conta só o que vai na busca', () => {
    expect(contarFiltros(pedido({}))).toBe(0)
    expect(contarFiltros(pedido({ texto: 'civic', estado: 'SP', ordenar: 'menor_preco' }))).toBe(0) // não são filtro do painel
    expect(contarFiltros(pedido({ marca: '   ', anoMin: 'abc', kmMax: 'mil' }))).toBe(0)
    expect(contarFiltros(pedido({ zona: 'barreiro' }))).toBe(0)
    expect(contarFiltros(pedido({ estado: 'todos', regiao: 'belo-horizonte-e-regiao' }))).toBe(0)
    expect(contarFiltros(pedido({ marca: 'Fiat', anoMin: '2020', anoMax: '2015' }))).toBe(3)
    expect(contarFiltros(pedido({ kmMax: '0' }))).toBe(1)
    expect(contarFiltros(pedido(TUDO))).toBe(15)
  })
})
