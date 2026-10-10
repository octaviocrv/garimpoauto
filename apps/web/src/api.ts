// Única porta de entrada dos dados. Hoje lê as buscas salvas em public/dados (copiadas de dados/
// por npm run copiar-dados). Quando existir endpoint, só estas funções mudam.
import type { Busca, ResultadoBusca } from './types'

export interface BuscaSalva {
  arquivo: string
  busca: Busca
  anuncios: number
}

export async function listarBuscasSalvas(): Promise<BuscaSalva[]> {
  const r = await fetch('/dados/index.json')
  if (!r.ok) throw new Error(`index.json HTTP ${r.status}`)
  return r.json()
}

export async function buscarAnuncios(busca: Busca): Promise<ResultadoBusca> {
  const salvas = await listarBuscasSalvas()
  const achada = salvas.find((s) => s.busca.texto === busca.texto)
  if (!achada) throw new Error(`busca salva não encontrada: ${busca.texto}`)
  const r = await fetch(`/dados/${achada.arquivo}`)
  if (!r.ok) throw new Error(`${achada.arquivo} HTTP ${r.status}`)
  const { resultado, anuncios } = await r.json()
  return { ...resultado, anuncios }
}
