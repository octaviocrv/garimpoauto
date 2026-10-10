import { useEffect, useMemo, useState } from 'react'
import { ArrowLeft, SlidersHorizontal } from 'lucide-react'
import { buscarAnuncios, listarBuscasSalvas, type BuscaSalva } from '../api'
import type { ResultadoBusca } from '../types'
import { CardCarro } from './CardCarro'
import { Diagnostico } from './Diagnostico'
import { FILTROS_VAZIOS, filtrar, ordenar, type Filtros, type Ordem } from './filtros'

const POR_PEDACO = 24
const DEV = new URLSearchParams(window.location.search).get('dev') === '1'

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
  const [salvas, setSalvas] = useState<BuscaSalva[]>([])
  const [atual, setAtual] = useState('')
  const [resultado, setResultado] = useState<ResultadoBusca | null>(null)
  const [estado, setEstado] = useState<'carregando' | 'erro' | 'ok'>('carregando')
  const [filtros, setFiltros] = useState<Filtros>(FILTROS_VAZIOS)
  const [painel, setPainel] = useState(false)
  const [ordem, setOrdem] = useState<Ordem>('menor_preco')
  const [visiveis, setVisiveis] = useState(POR_PEDACO)

  useEffect(() => {
    listarBuscasSalvas()
      .then((l) => { setSalvas(l); setAtual(l[0]?.busca.texto ?? ''); if (!l.length) setEstado('erro') })
      .catch(() => setEstado('erro'))
  }, [])

  useEffect(() => {
    const busca = salvas.find((s) => s.busca.texto === atual)?.busca
    if (!busca) return
    let vivo = true
    setEstado('carregando')
    buscarAnuncios(busca)
      .then((r) => { if (vivo) { setResultado(r); setEstado('ok') } })
      .catch(() => { if (vivo) setEstado('erro') })
    return () => { vivo = false }
  }, [atual, salvas])

  const { aprovados, cortados } = useMemo(
    () => (resultado ? filtrar(resultado.anuncios, filtros) : { aprovados: [], cortados: {} }),
    [resultado, filtros],
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
        <div className="flex flex-col gap-3 sm:flex-row">
          <select
            aria-label="Busca salva"
            className={`${campo} sm:max-w-[14rem]`}
            value={atual}
            onChange={(e) => { setAtual(e.target.value); setVisiveis(POR_PEDACO) }}
          >
            {salvas.map((s) => <option key={s.arquivo} value={s.busca.texto}>{s.busca.texto}</option>)}
          </select>
          <input
            aria-label="Filtrar a lista"
            className={campo}
            placeholder="Filtrar por nome, cidade..."
            value={filtros.texto}
            onChange={(e) => mudar('texto', e.target.value)}
          />
          <button
            type="button"
            onClick={() => setPainel((p) => !p)}
            aria-expanded={painel}
            className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-gray-600 bg-black/40 px-4 text-gray-300 transition-all hover:border-gray-400"
          >
            <SlidersHorizontal size={16} aria-hidden="true" /> Filtros
          </button>
        </div>

        {painel && (
          <div className="mt-3 grid grid-cols-2 gap-3 rounded-lg border border-white/10 bg-[#0a0a0a] p-4 sm:grid-cols-3 lg:grid-cols-5">
            <Campo nome="Marca"><input className={campo} value={filtros.marca} onChange={(e) => mudar('marca', e.target.value)} /></Campo>
            <Campo nome="Modelo"><input className={campo} value={filtros.modelo} onChange={(e) => mudar('modelo', e.target.value)} /></Campo>
            {num('anoMin', 'Ano mínimo')}
            {num('anoMax', 'Ano máximo')}
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
              onClick={() => { setFiltros({ ...FILTROS_VAZIOS, texto: filtros.texto }); setVisiveis(POR_PEDACO) }}
              className="min-h-11 self-end rounded-lg border border-gray-600 px-4 text-sm text-gray-300 hover:border-gray-400"
            >
              Limpar filtros
            </button>
          </div>
        )}

        <div className="mt-4 flex items-center justify-between gap-3">
          <p className="text-sm text-gray-400" aria-live="polite">
            {estado === 'ok' && `${lista.length} ${lista.length === 1 ? 'carro' : 'carros'}`}
          </p>
          <select aria-label="Ordenar" className={`${campo} max-w-[11rem]`} value={ordem} onChange={(e) => setOrdem(e.target.value as Ordem)}>
            <option value="menor_preco">Menor preço</option>
            <option value="maior_preco">Maior preço</option>
            <option value="menor_km">Menor km</option>
            <option value="mais_novo">Mais novo</option>
          </select>
        </div>

        {resultado && estado === 'ok' && resultado.avisos.length > 0 && (
          <div className="mt-3 space-y-1 rounded-lg border border-yellow-200/20 bg-yellow-200/5 px-4 py-3 text-sm text-yellow-100/90">
            {resultado.avisos.map((a) => <p key={a.codigo}>{a.mensagem}</p>)}
          </div>
        )}

        <div className="mt-4">
          {DEV && resultado && estado === 'ok' && (
            <Diagnostico resultado={resultado} depoisDosFiltros={lista} cortadosTela={cortados} />
          )}

          {estado === 'carregando' && <p className="py-16 text-center text-gray-400">Garimpando...</p>}
          {estado === 'erro' && <p className="py-16 text-center text-gray-400">Não achei esse carro agora, tenta de novo?</p>}
          {estado === 'ok' && lista.length === 0 && (
            <p className="py-16 text-center text-gray-400">Nenhum carro com esses filtros. Que tal afrouxar algum?</p>
          )}
          {estado === 'ok' && lista.length > 0 && (
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
