// As listas dos seletores de região e zona. Cada lista é buscada uma vez e fica guardada.
import { useEffect, useState } from 'react'
import { buscarRegioes, buscarZonas, ErroBusca } from '../api'
import type { Lugar } from '../types'
import { T } from './textos'

interface Lista {
  itens: Lugar[]
  carregando: boolean
  erro: string | null
}
const VAZIA: Lista = { itens: [], carregando: false, erro: null }
const guardadas = new Map<string, Lugar[]>()

function useLista(chave: string | null, buscar: (sinal: AbortSignal) => Promise<Lugar[]>): Lista {
  const [lista, setLista] = useState<Lista>(VAZIA)
  useEffect(() => {
    if (!chave) { setLista(VAZIA); return }
    const guardada = guardadas.get(chave)
    if (guardada) { setLista({ itens: guardada, carregando: false, erro: null }); return }
    const ctl = new AbortController()
    setLista({ itens: [], carregando: true, erro: null })
    buscar(ctl.signal)
      .then((itens) => { guardadas.set(chave, itens); setLista({ itens, carregando: false, erro: null }) })
      .catch((e) => {
        if (!ctl.signal.aborted) setLista({ itens: [], carregando: false, erro: e instanceof ErroBusca ? e.message : T.listaFalhou })
      })
    return () => ctl.abort()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chave])
  return lista
}

// "todos" (Brasil todo) não tem região.
export function useRegioes(estado: string): Lista {
  return useLista(estado === 'todos' ? null : `r|${estado}`, (s) => buscarRegioes(estado, s))
}

// A zona só existe depois da região.
export function useZonas(estado: string, regiao: string): Lista {
  return useLista(estado === 'todos' || !regiao ? null : `z|${estado}|${regiao}`, (s) => buscarZonas(estado, regiao, s))
}
