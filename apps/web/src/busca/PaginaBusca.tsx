import { useEffect, useMemo, useState } from 'react'
import { ArrowLeft, Search, SlidersHorizontal } from 'lucide-react'
import type { Pedido } from '../api'
import type { ResultadoBusca } from '../types'
import { useBusca } from './useBusca'
import { CardCarro } from './CardCarro'
import { Diagnostico } from './Diagnostico'
import { FILTROS_VAZIOS, filtrar, ordenar, type Filtros, type Ordem } from './filtros'

const POR_PEDACO = 24
const DEV = new URLSearchParams(window.location.search).get('dev') === '1'

const MSG_SEM_CARRO = 'Não achei esse carro agora, tenta de novo?'

const campo = 'min-h-11 w-full rounded-lg border border-white/10 bg-black/40 px-3 text-white placeholder:text-gray-600 focus:border-teal-500 focus:outline-none'

function Campo({ nome, children }: { nome: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-xs text-gray-400">
      {nome}
      {children}
    </label>
  )
}

export function PaginaBusca() {
  const { estado: busca, buscar, parar } = useBusca(DEV)
  const [rascunho, setRascunho] = useState({ texto: '', marca: '', anoMin: '', anoMax: '' })
  const [filtros, setFiltros] = useState<Filtros>(FILTROS_VAZIOS)
  const [painel, setPainel] = useState(false)
  const [ordem, setOrdem] = useState<Ordem>('menor_preco')
  const [visiveis, setVisiveis] = useState(POR_PEDACO)
  const [demorando, setDemorando] = useState(false)

  const buscando = busca.fase === 'buscando'
  const semNada = busca.anuncios.length === 0

  // Se o primeiro carro não chega em 15 s, a tela explica em vez de parecer travada.
  useEffect(() => {
    setDemorando(false)
    if (!buscando || busca.pagina > 0) return
    const t = setTimeout(() => setDemorando(true), 15000)
    return () => clearTimeout(t)
  }, [buscando, busca.pedido, busca.pagina])

  const pedidoDoRascunho = (): Pedido | null => {
    const texto = rascunho.texto.trim()
    if (!texto) return null
    const ano = (v: string) => (v.replace(/\D/g, '') ? Number(v.replace(/\D/g, '')) : undefined)
    let [ano_min, ano_max] = [ano(rascunho.anoMin), ano(rascunho.anoMax)]
    if (ano_min !== undefined && ano_max !== undefined && ano_min > ano_max) [ano_min, ano_max] = [ano_max, ano_min]
    return { texto, marca: rascunho.marca.trim() || undefined, ano_min, ano_max }
  }

  const buscarAgora = (e: React.FormEvent) => {
    e.preventDefault()
    const pedido = pedidoDoRascunho()
    if (!pedido) return
    setVisiveis(POR_PEDACO)
    buscar(pedido)
  }

  const resultado: ResultadoBusca | null = busca.fim ? { ...busca.fim, anuncios: busca.anuncios } : null
  const falhouNoMeio = busca.fase === 'falhou' || busca.fim?.motivo_parada === 'falha_fonte'
  const avisos = (busca.fim?.avisos ?? []).filter((a) => a.codigo !== 'fonte_parcial') // a tela fala da falha do jeito dela

  const { aprovados, cortados } = useMemo(
    () => filtrar(busca.anuncios, filtros),
    [busca.anuncios, filtros],
  )
  const lista = useMemo(() => ordenar(aprovados, ordem), [aprovados, ordem])

  const mudar = (k: keyof Filtros, v: string) => { setFiltros((f) => ({ ...f, [k]: v })); setVisiveis(POR_PEDACO) }
  const num = (k: keyof Filtros, nome: string, ph = '') => (
    <Campo nome={nome}>
      <input inputMode="numeric" className={campo} placeholder={ph} value={filtros[k]} onChange={(e) => mudar(k, e.target.value)} />
    </Campo>
  )

  return (
    <div className="min-h-svh bg-[#050505] font-sans text-white">
      <header className="border-b border-white/10 bg-[#0a0a0a]">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-3 px-5">
          <span className="flex items-center gap-3">
            <span className="grid h-10 w-10 flex-none place-items-center overflow-hidden rounded-full border-2 border-teal-600 bg-teal-900">
              <img src="/mascot/han-profile.jpeg" alt="" className="h-full w-full object-cover" />
            </span>
            <span className="whitespace-nowrap text-lg font-bold">Garimpo Auto</span>
          </span>
          <a href="#inicio" className="inline-flex min-h-11 items-center gap-1 text-sm text-gray-400 transition-colors hover:text-white">
            <ArrowLeft size={16} aria-hidden="true" /> Início
          </a>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-5 py-6">
        <form onSubmit={buscarAgora} className="flex flex-col gap-3 sm:flex-row">
          <input
            type="search"
            aria-label="Qual carro você quer?"
            className={campo}
            placeholder="Qual carro você quer? Ex.: gol 2012"
            value={rascunho.texto}
            onChange={(e) => setRascunho((r) => ({ ...r, texto: e.target.value }))}
            enterKeyHint="search"
            autoFocus
          />
          <button
            type="submit"
            disabled={!rascunho.texto.trim()}
            className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-teal-600 px-6 font-medium text-white transition-all hover:bg-teal-500 disabled:opacity-40"
          >
            <Search size={16} aria-hidden="true" /> Buscar
          </button>
          <button
            type="button"
            onClick={() => setPainel((p) => !p)}
            aria-expanded={painel}
            className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-gray-600 bg-black/40 px-4 text-gray-300 transition-all hover:border-gray-400"
          >
            <SlidersHorizontal size={16} aria-hidden="true" /> Filtros
          </button>
        </form>

        {painel && (
          <div className="mt-3 rounded-lg border border-white/10 bg-[#0a0a0a] p-4">
            <p className="mb-3 text-sm text-gray-400">Marca e ano valem na próxima busca. O resto filtra a lista na hora.</p>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
              <Campo nome="Marca"><input className={campo} value={rascunho.marca} onChange={(e) => setRascunho((r) => ({ ...r, marca: e.target.value }))} /></Campo>
              <Campo nome="Ano mínimo"><input inputMode="numeric" className={campo} value={rascunho.anoMin} onChange={(e) => setRascunho((r) => ({ ...r, anoMin: e.target.value }))} /></Campo>
              <Campo nome="Ano máximo"><input inputMode="numeric" className={campo} value={rascunho.anoMax} onChange={(e) => setRascunho((r) => ({ ...r, anoMax: e.target.value }))} /></Campo>
              <Campo nome="Modelo"><input className={campo} value={filtros.modelo} onChange={(e) => mudar('modelo', e.target.value)} /></Campo>
              {num('precoMin', 'Preço mínimo')}
              {num('precoMax', 'Preço máximo')}
              {num('kmMax', 'Km máximo')}
              <Campo nome="Cidade"><input className={campo} value={filtros.cidade} onChange={(e) => mudar('cidade', e.target.value)} /></Campo>
              <Campo nome="Anunciante">
                <select className={campo} value={filtros.tipo} onChange={(e) => mudar('tipo', e.target.value)}>
                  <option value="todos">Todos</option>
                  <option value="loja">Loja</option>
                  <option value="particular">Particular</option>
                </select>
              </Campo>
              <button
                type="button"
                onClick={() => { setFiltros(FILTROS_VAZIOS); setVisiveis(POR_PEDACO) }}
                className="min-h-11 self-end rounded-lg border border-gray-600 px-4 text-sm text-gray-300 hover:border-gray-400"
              >
                Limpar filtros
              </button>
            </div>
          </div>
        )}

        {buscando && (
          <div className="mt-4 rounded-lg border border-teal-600/40 bg-teal-900/10 px-4 py-3" aria-live="polite">
            <div className="flex items-center justify-between gap-3">
              <p className="font-medium text-teal-400">
                Garimpando...{busca.pagina > 0 && busca.paginasTotal ? ` página ${busca.pagina} de ${busca.paginasTotal}` : ''}
              </p>
              <button type="button" onClick={parar} className="min-h-11 rounded-lg border border-gray-600 px-4 text-sm text-gray-300 hover:border-gray-400">
                Parar
              </button>
            </div>
            <p className="mt-1 text-sm text-gray-400">
              {demorando
                ? 'Tá demorando um pouco mais que o normal, segura aí.'
                : 'Busca nova leva um minutinho, mas os carros vão aparecendo aqui.'}
            </p>
          </div>
        )}

        {busca.fase === 'parada' && (
          <p className="mt-4 rounded-lg border border-white/10 bg-[#0a0a0a] px-4 py-3 text-sm text-gray-300">
            Parei a busca. {semNada ? 'Ainda não tinha chegado nenhum carro.' : 'Esses são os carros que já tinham chegado.'}
          </p>
        )}

        {falhouNoMeio && busca.fase !== 'buscando' && (
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-yellow-200/20 bg-yellow-200/5 px-4 py-3 text-sm text-yellow-100/90">
            <p>{semNada ? MSG_SEM_CARRO : 'Deu uma travada no meio da busca, mas esses carros já chegaram. Quer tentar de novo?'}</p>
            <button
              type="button"
              onClick={() => busca.pedido && buscar(busca.pedido)}
              className="min-h-11 rounded-lg border border-yellow-200/40 px-4 text-yellow-100 hover:border-yellow-100"
            >
              Tentar de novo
            </button>
          </div>
        )}

        {!semNada && (
          <div className="mt-4 flex items-center justify-between gap-3">
            <p className="text-sm text-gray-400" aria-live="polite">
              {lista.length} {lista.length === 1 ? 'carro' : 'carros'}{buscando ? ' até agora' : ''}
            </p>
            <select aria-label="Ordenar" className={`${campo} max-w-[11rem]`} value={ordem} onChange={(e) => setOrdem(e.target.value as Ordem)}>
              <option value="menor_preco">Menor preço</option>
              <option value="maior_preco">Maior preço</option>
              <option value="menor_km">Menor km</option>
              <option value="mais_novo">Mais novo</option>
            </select>
          </div>
        )}

        {busca.fase === 'pronto' && avisos.length > 0 && (
          <div className="mt-3 space-y-1 rounded-lg border border-yellow-200/20 bg-yellow-200/5 px-4 py-3 text-sm text-yellow-100/90">
            {avisos.map((a) => <p key={a.codigo}>{a.mensagem}</p>)}
          </div>
        )}

        <div className="mt-4">
          {DEV && resultado && (
            <Diagnostico resultado={resultado} depoisDosFiltros={lista} cortadosTela={cortados} />
          )}

          {busca.fase === 'inicial' && (
            <p className="py-16 text-center text-gray-400">Digita o carro que você quer e aperta Enter. O resto é com a gente.</p>
          )}
          {busca.fase === 'pronto' && !falhouNoMeio && semNada && (
            <p className="py-16 text-center text-gray-400">Não achei nenhum carro com esse nome. Tenta escrever de outro jeito?</p>
          )}
          {!buscando && !semNada && lista.length === 0 && (
            <p className="py-16 text-center text-gray-400">Nenhum carro com esses filtros. Que tal afrouxar algum?</p>
          )}
          {lista.length > 0 && (
            <>
              <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {lista.slice(0, visiveis).map((a) => <CardCarro key={a.external_id} a={a} />)}
              </ul>
              {visiveis < lista.length && (
                <button
                  type="button"
                  onClick={() => setVisiveis((v) => v + POR_PEDACO)}
                  className="mx-auto mt-6 flex min-h-12 items-center justify-center rounded-lg bg-teal-600 px-8 font-medium text-white transition-all hover:bg-teal-500"
                >
                  Ver mais
                </button>
              )}
            </>
          )}
        </div>
      </main>
    </div>
  )
}
