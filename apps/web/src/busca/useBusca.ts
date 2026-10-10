// Controla uma busca ao vivo: junta os carros conforme as páginas chegam, guarda o progresso e
// cuida de cancelar e de começar outra no meio. Só a busca mais nova pode mexer no estado.
import { useCallback, useEffect, useRef, useState } from 'react'
import { buscarAoVivo, type FimStream, type PaginaStream, type Pedido } from '../api'
import type { Anuncio } from '../types'

export type Fase = 'inicial' | 'buscando' | 'pronto' | 'parada' | 'falhou'

export interface EstadoBusca {
  fase: Fase
  pedido: Pedido | null
  anuncios: Anuncio[]
  pagina: number // páginas já lidas
  paginasTotal: number | null // estimativa, só depois que a 1ª página chega
  fim: FimStream | null
}

const INICIAL: EstadoBusca = { fase: 'inicial', pedido: null, anuncios: [], pagina: 0, paginasTotal: null, fim: null }

// A fonte diz quantos anúncios tem no total. Páginas esperadas = total / tamanho da 1ª página,
// nunca mais que o teto da coleta.
export function estimarPaginas(p: Pick<PaginaStream, 'total_na_fonte' | 'coletados' | 'max_paginas'>): number {
  if (!p.total_na_fonte || p.coletados <= 0) return p.max_paginas
  return Math.max(1, Math.min(p.max_paginas, Math.ceil(p.total_na_fonte / p.coletados)))
}

export function useBusca(dev: boolean) {
  const [estado, setEstado] = useState<EstadoBusca>(INICIAL)
  const atual = useRef<AbortController | null>(null)

  const parar = useCallback(() => {
    atual.current?.abort()
    atual.current = null
    setEstado((e) => (e.fase === 'buscando' ? { ...e, fase: 'parada' } : e))
  }, [])

  const buscar = useCallback((pedido: Pedido) => {
    atual.current?.abort() // busca nova no meio de outra: a velha é largada
    const ctl = new AbortController()
    atual.current = ctl
    setEstado({ ...INICIAL, fase: 'buscando', pedido })
    void buscarAoVivo(pedido, dev, {
      aoChegarPagina: (p) =>
        setEstado((e) => ({
          ...e,
          anuncios: [...e.anuncios, ...p.anuncios],
          pagina: p.numero,
          paginasTotal: e.paginasTotal ?? estimarPaginas(p),
        })),
      aoTerminar: (fim) => setEstado((e) => ({ ...e, fase: 'pronto', fim })),
      aoFalhar: () => setEstado((e) => ({ ...e, fase: 'falhou' })),
    }, ctl.signal)
  }, [dev])

  useEffect(() => () => atual.current?.abort(), [])

  return { estado, buscar, parar }
}
