// Única porta de entrada dos dados: a busca por página do servidor (/buscar/pagina), o "Ver mais".
// A tela chama /api/... e o Vite repassa para o servidor (veja vite.config.ts).
import type { Lugar, RespostaPagina, RespostaRegioes, RespostaZonas } from './types'
import type { Pedido } from './busca/pedido'
import { T } from './busca/textos'

const API = import.meta.env.VITE_API_URL ?? '/api'

export class ErroBusca extends Error {}

export function montarUrl(pedido: Pedido, pagina: number, dev: boolean, atualizar: boolean): string {
  const q = new URLSearchParams()
  for (const [chave, valor] of Object.entries(pedido)) {
    // o texto vai sempre, mesmo vazio: o servidor exige o parâmetro e vazio é a vitrine
    if (chave === 'texto' || (valor !== undefined && valor !== '')) q.set(chave, String(valor))
  }
  q.set('pagina', String(pagina))
  if (dev) q.set('dev', '1')
  if (atualizar && pagina === 1) q.set('atualizar', '1') // só na página 1, senão a busca recomeça
  return `${API}/buscar/pagina?${q}`
}

// Rede caiu ou o servidor não respondeu direito: ErroBusca com uma frase pronta para a tela.
export async function buscarPagina(
  pedido: Pedido, pagina: number, dev: boolean, atualizar: boolean, signal: AbortSignal,
): Promise<RespostaPagina> {
  let r: Response
  try {
    r = await fetch(montarUrl(pedido, pagina, dev, atualizar), { signal })
  } catch (e) {
    if (signal.aborted) throw e
    throw new ErroBusca(T.semCarro)
  }
  if (!r.ok) {
    const corpo = await r.json().catch(() => null)
    throw new ErroBusca(r.status === 422 ? corpo?.erro ?? T.pedidoRuim : T.semCarro)
  }
  return r.json()
}

// As listas dos seletores de região e zona. Mesmo jeito de erro da busca: 422 vem como o servidor mandou.
async function buscarLista<T>(caminho: string, signal: AbortSignal): Promise<T> {
  let r: Response
  try {
    r = await fetch(`${API}${caminho}`, { signal })
  } catch (e) {
    if (signal.aborted) throw e
    throw new ErroBusca(T.listaFalhou)
  }
  if (!r.ok) {
    const corpo = await r.json().catch(() => null)
    throw new ErroBusca(r.status === 422 ? corpo?.erro ?? T.pedidoRuim : T.listaFalhou)
  }
  return r.json()
}

export async function buscarRegioes(estado: string, signal: AbortSignal): Promise<Lugar[]> {
  const r = await buscarLista<RespostaRegioes>(`/regioes?estado=${encodeURIComponent(estado)}`, signal)
  return r.regioes
}

export async function buscarZonas(estado: string, regiao: string, signal: AbortSignal): Promise<Lugar[]> {
  const q = new URLSearchParams({ estado, regiao })
  const r = await buscarLista<RespostaZonas>(`/zonas?${q}`, signal)
  return r.zonas
}
