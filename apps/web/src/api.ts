// Única porta de entrada dos dados: a busca ao vivo do servidor (/buscar/stream).
// A tela chama /api/... e o Vite repassa para o servidor (veja vite.config.ts).
import type { Anuncio, ResultadoBusca } from './types'
import { criarLeitorSse } from './busca/sse'

const API = import.meta.env.VITE_API_URL ?? '/api'

// O que vai na busca. Marca e ano o servidor já aplica na coleta.
export interface Pedido {
  texto: string
  marca?: string
  ano_min?: number
  ano_max?: number
}

export interface PaginaStream {
  numero: number
  max_paginas: number
  anuncios: Anuncio[]
  coletados: number
  cortados_por_filtro: Record<string, number>
  acumulado: number
  total_na_fonte: number | null
}

export type FimStream = Omit<ResultadoBusca, 'anuncios'>

export interface Ouvintes {
  aoChegarPagina: (p: PaginaStream) => void
  aoTerminar: (fim: FimStream) => void
  aoFalhar: () => void // a coleta não chegou ao fim (rede, servidor caiu, erro do servidor)
}

export function montarUrl(pedido: Pedido, dev: boolean): string {
  const q = new URLSearchParams({ texto: pedido.texto })
  if (pedido.marca) q.set('marca', pedido.marca)
  if (pedido.ano_min !== undefined) q.set('ano_min', String(pedido.ano_min))
  if (pedido.ano_max !== undefined) q.set('ano_max', String(pedido.ano_max))
  if (dev) q.set('dev', '1')
  return `${API}/buscar/stream?${q}`
}

// Resolve quando a busca acaba. Chama aoTerminar ou aoFalhar, uma só vez. Se o signal for
// abortado (cancelou ou começou outra busca), não chama nenhum dos dois.
export async function buscarAoVivo(pedido: Pedido, dev: boolean, ouvintes: Ouvintes, signal: AbortSignal): Promise<void> {
  let acabou = false
  const leitor = criarLeitorSse(({ nome, dados }) => {
    if (acabou || signal.aborted) return
    if (nome === 'pagina') ouvintes.aoChegarPagina(dados as PaginaStream)
    else if (nome === 'fim') { acabou = true; ouvintes.aoTerminar(dados as FimStream) }
    else if (nome === 'erro') { acabou = true; ouvintes.aoFalhar() }
  })
  try {
    const r = await fetch(montarUrl(pedido, dev), { signal, headers: { Accept: 'text/event-stream' } })
    if (!r.ok || !r.body) throw new Error(`HTTP ${r.status}`)
    const leitorBytes = r.body.getReader()
    const decodificador = new TextDecoder()
    for (;;) {
      const { done, value } = await leitorBytes.read()
      if (done) break
      leitor.empurrar(decodificador.decode(value, { stream: true }))
    }
  } catch {
    // cai no teste abaixo
  }
  if (!acabou && !signal.aborted) ouvintes.aoFalhar()
}
