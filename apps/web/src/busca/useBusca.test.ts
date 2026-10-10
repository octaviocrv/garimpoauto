import { describe, expect, it } from 'vitest'
import { INICIAL, reduzir, type EstadoBusca } from './useBusca'
import type { Anuncio, RespostaPagina } from '../types'
import type { Pedido } from './pedido'
import { T } from './textos'

const pedido: Pedido = { texto: 'gol', ordenar: 'recentes', estado: 'MG' }
// Carro de mentira com tudo vazio como o servidor manda (null), só o que o teste usa é preenchido.
const base = {
  titulo: null, marca: null, modelo: null, modelo_original: null, ano: null, km: null, preco: null, anunciado_em: null,
  renovado_em: null, publicado_em: null, em_destaque: false, repetido_de: null, anunciante_profissional: null,
  nota_anunciante: null, imagens: [],
}
const carro = (id: string): Anuncio => ({ ...base, external_id: id } as unknown as Anuncio)

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

describe('vitrine', () => {
  const vitrine: Pedido = { texto: '', ordenar: 'recentes', estado: 'MG' }
  const ids = Array.from({ length: 50 }, (_, i) => `v${i}`)

  it('chega só a página 1 e fica esperando o clique no Ver mais', () => {
    let e = reduzir(INICIAL, { tipo: 'iniciar', pedido: vitrine })
    expect(e.fase).toBe('buscando')
    e = reduzir(e, { tipo: 'chegou', resposta: resposta(1, ids, { total_na_fonte: 73619 }) })
    expect(e.fase).toBe('pronto')
    expect(e.anuncios).toHaveLength(50)
    expect(e.blocos).toHaveLength(1)
    expect(e.carregandoMais).toBe(false)
    expect(e.resposta?.proxima_pagina).toBe(2) // quem pede é o clique, não o estado
  })

  it('busca nova substitui a vitrine, e voltar pra vitrine também substitui a busca', () => {
    let e = reduzir(reduzir(INICIAL, { tipo: 'iniciar', pedido: vitrine }), { tipo: 'chegou', resposta: resposta(1, ids) })
    e = reduzir(e, { tipo: 'iniciar', pedido: { ...vitrine, texto: 'onix' } })
    expect(e.anuncios).toEqual([])
    e = reduzir(e, { tipo: 'chegou', resposta: resposta(1, ['o1']) })
    expect(e.anuncios.map((a) => a.external_id)).toEqual(['o1'])
    e = reduzir(e, { tipo: 'iniciar', pedido: vitrine })
    expect(e.anuncios).toEqual([])
    expect(e.pedido?.texto).toBe('')
  })

  it('se a vitrine falha mostra a frase da marca e deixa tentar de novo', () => {
    const e = reduzir(reduzir(INICIAL, { tipo: 'iniciar', pedido: vitrine }), { tipo: 'chegou', resposta: resposta(1, [], { falhou: true }) })
    expect(e.fase).toBe('falhou')
    expect(e.erro).toBe(T.semCarro)
    expect(e.pedido).toEqual(vitrine) // o botão Tentar de novo refaz esse mesmo pedido
  })
})

describe('a lista não muda sozinha quando chega página nova', () => {
  const AGORA = new Date(2026, 9, 10, 15, 0).getTime()
  const igual = (id: string, preco: number): Anuncio =>
    ({ ...base, external_id: id, marca: 'Fiat', modelo: 'Argo', ano: 2019, preco } as unknown as Anuncio)
  const resp = (pagina: number, anuncios: Anuncio[], extra: Partial<RespostaPagina> = {}) => ({ ...resposta(pagina, []), anuncios, ...extra })
  const pagina1 = [igual('a', 50000), igual('b', 52000), igual('c', 51000), igual('d', 50000), igual('e', 40000)]

  it('os carros já na tela guardam os mesmos sinais, mesmo com carro novo mudando a conta', () => {
    let e = reduzir(reduzir(INICIAL, { tipo: 'iniciar', pedido }), { tipo: 'chegou', resposta: resp(1, pagina1), agora: AGORA })
    const antes = e.sinais
    const analisesAntes = e.analises
    expect(antes.e).toHaveLength(1)
    // a página 2 traz 5 carros baratos que puxariam a conta pra baixo e apagariam o sinal do "e"
    const barato = [1, 2, 3, 4, 5].map((i) => igual(`n${i}`, 39000))
    e = reduzir(e, { tipo: 'chegou', resposta: resp(2, barato) })
    expect(e.sinais.e).toBe(antes.e)
    expect(e.sinais.a).toBe(antes.a)
    expect(e.analises.e).toBe(analisesAntes.e) // o nível também não muda sozinho
    expect(Object.keys(e.analises)).toHaveLength(10)
    expect(Object.keys(e.sinais)).toHaveLength(10)
  })

  it('a ordem dos carros só cresce no fim e a hora de referência não muda', () => {
    let e = reduzir(reduzir(INICIAL, { tipo: 'iniciar', pedido }), { tipo: 'chegou', resposta: resp(1, pagina1), agora: AGORA })
    e = reduzir(e, { tipo: 'chegou', resposta: resp(2, [igual('z', 1000)]), agora: AGORA + 999999 })
    expect(e.anuncios.map((a) => a.external_id)).toEqual(['a', 'b', 'c', 'd', 'e', 'z'])
    expect(e.agora).toBe(AGORA)
  })

  it('aviso da página 1 não some quando chega a página 2, e não repete', () => {
    const aviso = { codigo: 'filtro_aproximado' as const, mensagem: 'Não achei a cidade X na lista da OLX.' }
    let e = reduzir(reduzir(INICIAL, { tipo: 'iniciar', pedido }), { tipo: 'chegou', resposta: resp(1, pagina1, { avisos: [aviso] }) })
    e = reduzir(e, { tipo: 'chegou', resposta: resp(2, [igual('z', 1)], { avisos: [aviso] }) })
    e = reduzir(e, { tipo: 'chegou', resposta: resp(3, [igual('y', 1)], { avisos: [] }) })
    expect(e.avisos).toEqual([aviso])
  })

  it('busca nova começa sem sinais nem avisos da anterior', () => {
    const e = reduzir(reduzir(INICIAL, { tipo: 'iniciar', pedido }), { tipo: 'chegou', resposta: resp(1, pagina1), agora: AGORA })
    const novo = reduzir(e, { tipo: 'iniciar', pedido })
    expect(novo.sinais).toEqual({})
    expect(novo.analises).toEqual({})
    expect(novo.avisos).toEqual([])
  })
})
