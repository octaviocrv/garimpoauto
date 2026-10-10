// Controla a busca por página: junta os carros de cada página que chega, cuida do "Ver mais",
// de cancelar e de começar outra no meio. Só a busca mais nova pode mexer no estado.
import { useCallback, useEffect, useReducer, useRef } from 'react'
import { buscarPagina, ErroBusca } from '../api'
import type { Anuncio, Aviso, RespostaPagina } from '../types'
import type { Pedido } from './pedido'
import { analisesDaPagina, type Analise } from './analise'
import { sinaisDaPagina, type Sinal } from './sinais'
import { T } from './textos'

export type Fase = 'inicial' | 'buscando' | 'pronto' | 'parada' | 'falhou'

export interface EstadoBusca {
  fase: Fase
  pedido: Pedido | null
  anuncios: Anuncio[]
  blocos: Anuncio[][] // os mesmos carros, um bloco por página, pra cada página ter a própria grade
  resposta: RespostaPagina | null // a última que chegou (tem proxima_pagina, informacao, avisos...)
  primeira: RespostaPagina | null // a da página 1, que tem a hora da coleta
  carregandoMais: boolean
  falhouMais: boolean
  erro: string | null // frase pronta quando a busca nem começou
  // Nada abaixo muda para um carro que já está na tela. Só cresce quando chega página nova.
  sinais: Record<string, Sinal[]> // calculados quando o carro chegou, nunca refeitos
  analises: Record<string, Analise> // idem: o nível Quente ou Boa e a tela do Garimpar vêm daqui
  avisos: Aviso[] // de todas as páginas, sem repetir, pra o aviso não sumir quando chega a página 2
  agora: number // a hora de referência das datas e dos sinais, fixada na página 1
}

export const INICIAL: EstadoBusca = {
  fase: 'inicial', pedido: null, anuncios: [], blocos: [], resposta: null, primeira: null,
  carregandoMais: false, falhouMais: false, erro: null, sinais: {}, analises: {}, avisos: [], agora: 0,
}

export type Acao =
  | { tipo: 'iniciar'; pedido: Pedido }
  | { tipo: 'chegou'; resposta: RespostaPagina; agora?: number } // agora: só os testes passam, na tela é a hora real
  | { tipo: 'verMais' }
  | { tipo: 'caiu'; erro: string }
  | { tipo: 'parar' }

const mesclarAvisos = (antigos: Aviso[], novos: Aviso[]): Aviso[] => {
  const vistos = new Set(antigos.map((a) => `${a.codigo}|${a.mensagem}`))
  return [...antigos, ...novos.filter((a) => !vistos.has(`${a.codigo}|${a.mensagem}`))]
}

export function reduzir(e: EstadoBusca, a: Acao): EstadoBusca {
  switch (a.tipo) {
    case 'iniciar': // busca nova, de qualquer tipo, limpa a lista antiga
      return { ...INICIAL, fase: 'buscando', pedido: a.pedido }
    case 'verMais':
      return { ...e, carregandoMais: true, falhouMais: false }
    case 'chegou': {
      const r = a.resposta
      const primeira = r.pagina === 1
      if (r.falhou) {
        if (primeira) return { ...e, fase: 'falhou', erro: T.semCarro, resposta: r }
        return { ...e, carregandoMais: false, falhouMais: true } // mantém a resposta anterior, que já aponta a mesma página
      }
      const agora = primeira ? a.agora ?? Date.now() : e.agora
      const anuncios = primeira ? r.anuncios : [...e.anuncios, ...r.anuncios]
      return {
        ...e, fase: 'pronto', carregandoMais: false, falhouMais: false, erro: null, resposta: r,
        primeira: primeira ? r : e.primeira, anuncios, agora,
        blocos: primeira ? [r.anuncios] : [...e.blocos, r.anuncios],
        sinais: { ...(primeira ? {} : e.sinais), ...sinaisDaPagina(r.anuncios, anuncios, agora) },
        analises: { ...(primeira ? {} : e.analises), ...analisesDaPagina(r.anuncios, anuncios, agora) },
        avisos: mesclarAvisos(primeira ? [] : e.avisos, r.avisos),
      }
    }
    case 'caiu':
      if (e.fase === 'buscando') return { ...e, fase: 'falhou', erro: a.erro }
      return { ...e, carregandoMais: false, falhouMais: true }
    case 'parar':
      return e.fase === 'buscando' ? { ...e, fase: 'parada' } : e
  }
}

export function useBusca(dev: boolean) {
  const [estado, despachar] = useReducer(reduzir, INICIAL)
  const atual = useRef<AbortController | null>(null)
  const ultimo = useRef(estado)
  ultimo.current = estado

  const carregar = useCallback((pedido: Pedido, pagina: number, atualizar: boolean) => {
    atual.current?.abort() // a busca velha é largada
    const ctl = new AbortController()
    atual.current = ctl
    buscarPagina(pedido, pagina, dev, atualizar, ctl.signal)
      .then((resposta) => { if (!ctl.signal.aborted) despachar({ tipo: 'chegou', resposta }) })
      .catch((e) => {
        if (ctl.signal.aborted) return
        despachar({ tipo: 'caiu', erro: e instanceof ErroBusca ? e.message : T.semCarro })
      })
  }, [dev])

  const buscar = useCallback((pedido: Pedido, atualizar = false) => {
    despachar({ tipo: 'iniciar', pedido })
    carregar(pedido, 1, atualizar)
  }, [carregar])

  const verMais = useCallback(() => {
    const { pedido, resposta, carregandoMais } = ultimo.current
    if (!pedido || !resposta?.proxima_pagina || carregandoMais) return
    despachar({ tipo: 'verMais' })
    carregar(pedido, resposta.proxima_pagina, false)
  }, [carregar])

  const parar = useCallback(() => {
    atual.current?.abort()
    atual.current = null
    despachar({ tipo: 'parar' })
  }, [])

  useEffect(() => () => atual.current?.abort(), [])

  return { estado, buscar, verMais, parar }
}
