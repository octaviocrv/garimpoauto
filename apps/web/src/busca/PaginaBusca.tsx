import { useEffect, useState } from 'react'
import { ArrowLeft, RefreshCw, Search, SlidersHorizontal } from 'lucide-react'
import { CardCarro } from './CardCarro'
import { Diagnostico } from './Diagnostico'
import { DEMO } from './fipe'
import {
  ANUNCIANTES, CAMBIOS, COMBUSTIVEIS, ESTADOS, FILTROS_DO_RASCUNHO, ORDENS, RASCUNHO_VAZIO, montarPedido,
  nomeDoEstado, type Rascunho,
} from './pedido'
import { useRegioes, useZonas } from './regioes'
import { T, buscadoAs, naOlx, novosDesde } from './textos'
import { useBusca } from './useBusca'

const DEV = new URLSearchParams(window.location.search).get('dev') === '1'

const campo = 'min-h-11 w-full rounded-lg border border-white/10 bg-black/40 px-3 text-white placeholder:text-gray-600 focus:border-teal-500 focus:outline-none'
const botao = 'inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-gray-600 bg-black/40 px-4 text-gray-300 transition-all hover:border-gray-400'

function Campo({ nome, children }: { nome: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-xs text-gray-400">
      {nome}
      {children}
    </label>
  )
}

export function PaginaBusca() {
  const { estado: busca, buscar, verMais, parar } = useBusca(DEV)
  const [r, setR] = useState<Rascunho>(RASCUNHO_VAZIO)
  const [painel, setPainel] = useState(false)
  const [demorando, setDemorando] = useState(false)
  const [fipeLigada, setFipeLigada] = useState(true)
  const regioes = useRegioes(r.estado)
  const zonas = useZonas(r.estado, r.regiao)

  const buscando = busca.fase === 'buscando'
  const resposta = busca.resposta

  // Se o primeiro carro não chega em 15 s, a tela explica em vez de parecer travada.
  useEffect(() => {
    setDemorando(false)
    if (!buscando) return
    const t = setTimeout(() => setDemorando(true), 15000)
    return () => clearTimeout(t)
  }, [buscando, busca.pedido])

  const mudar = (k: keyof Rascunho, v: string) => setR((x) => ({ ...x, [k]: v }))
  const texto = (k: keyof Rascunho, nome: string, numerico = false) => (
    <Campo nome={nome}>
      <input inputMode={numerico ? 'numeric' : undefined} className={campo} value={r[k]} onChange={(e) => mudar(k, e.target.value)} />
    </Campo>
  )
  const escolha = (k: keyof Rascunho, nome: string, opcoes: readonly (readonly [string, string])[]) => (
    <Campo nome={nome}>
      <select className={campo} value={r[k]} onChange={(e) => mudar(k, e.target.value)}>
        {opcoes.map(([valor, rotulo]) => <option key={valor} value={valor}>{rotulo}</option>)}
      </select>
    </Campo>
  )

  const mudarEstado = (estado: string) => setR((x) => ({ ...x, estado, regiao: '', zona: '' })) // região é do estado
  const mudarRegiao = (regiao: string) => setR((x) => ({ ...x, regiao, zona: '' })) // zona é da região

  const buscarAgora = (e: React.FormEvent) => {
    e.preventDefault()
    const pedido = montarPedido(r)
    if (pedido) buscar(pedido)
  }
  const filtrosAtivos = FILTROS_DO_RASCUNHO.filter((k) => r[k] !== '').length

  const lista = busca.anuncios
  const primeira = busca.primeira
  const meta = [
    resposta ? nomeDoEstado(resposta.estado_aplicado) : null,
    resposta?.total_na_fonte ? naOlx(resposta.total_na_fonte) : null,
    primeira?.coletado_em ? buscadoAs(primeira.coletado_em) : null,
  ].filter(Boolean)
  const avisos = busca.avisos.filter((a) => a.codigo !== 'fonte_parcial') // a falha a tela já conta do jeito dela
  // Selo e contagem de novos só quando o servidor tem banco e já houve busca igual antes. null é "não sei".
  const sabeSeTemNovo = busca.primeira?.primeira_busca === false
  const novos = sabeSeTemNovo ? resposta?.novos ?? 0 : 0
  const nadaAchado = busca.fase === 'pronto' && lista.length === 0

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
            placeholder={T.placeholder}
            value={r.texto}
            onChange={(e) => mudar('texto', e.target.value)}
            enterKeyHint="search"
            autoFocus
          />
          <select aria-label="Estado" className={`${campo} sm:max-w-[12rem]`} value={r.estado} onChange={(e) => mudarEstado(e.target.value)}>
            {ESTADOS.map(([sigla, nome]) => <option key={sigla} value={sigla}>{nome}</option>)}
          </select>
          <div className="flex gap-3">
            <button
              type="submit"
              disabled={!r.texto.trim()}
              className="inline-flex min-h-11 flex-1 items-center justify-center gap-2 rounded-lg bg-teal-600 px-6 font-medium text-white transition-all hover:bg-teal-500 disabled:opacity-40"
            >
              <Search size={16} aria-hidden="true" /> {T.buscar}
            </button>
            <button type="button" onClick={() => setPainel((p) => !p)} aria-expanded={painel} className={botao}>
              <SlidersHorizontal size={16} aria-hidden="true" /> {T.filtros}{filtrosAtivos > 0 ? ` (${filtrosAtivos})` : ''}
            </button>
          </div>
        </form>

        {painel && (
          <div className="mt-3 rounded-lg border border-white/10 bg-[#0a0a0a] p-4">
            <p className="mb-3 text-sm text-gray-400">{T.dicaFiltros}</p>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
              {r.estado !== 'todos' && (
                <Campo nome={T.regiao}>
                  <select
                    className={campo}
                    value={r.regiao}
                    disabled={regioes.carregando || regioes.itens.length === 0}
                    onChange={(e) => mudarRegiao(e.target.value)}
                  >
                    <option value="">{regioes.carregando ? T.carregando : T.qualquerRegiao}</option>
                    {regioes.itens.map((l) => <option key={l.slug} value={l.slug}>{l.nome}</option>)}
                  </select>
                </Campo>
              )}
              {r.estado !== 'todos' && r.regiao !== '' && (zonas.carregando || zonas.itens.length > 0) && (
                <Campo nome={T.zona}>
                  <select className={campo} value={r.zona} disabled={zonas.carregando} onChange={(e) => mudar('zona', e.target.value)}>
                    <option value="">{zonas.carregando ? T.carregando : T.qualquerZona}</option>
                    {zonas.itens.map((l) => <option key={l.slug} value={l.slug}>{l.nome}</option>)}
                  </select>
                </Campo>
              )}
              {texto('marca', 'Marca')}
              {texto('modelo', 'Modelo')}
              {texto('versao', 'Versão')}
              {texto('anoMin', 'Ano mínimo', true)}
              {texto('anoMax', 'Ano máximo', true)}
              {texto('precoMin', 'Preço mínimo', true)}
              {texto('precoMax', 'Preço máximo', true)}
              {texto('kmMin', 'Km mínimo', true)}
              {texto('kmMax', 'Km máximo', true)}
              {escolha('cambio', 'Câmbio', CAMBIOS)}
              {escolha('combustivel', 'Combustível', COMBUSTIVEIS)}
              {escolha('anunciante', 'Anunciante', ANUNCIANTES)}
              {texto('cidade', 'Cidade')}
              {escolha('ordenar', 'Ordenar por', ORDENS)}
              <button
                type="button"
                onClick={() => setR((x) => ({ ...RASCUNHO_VAZIO, texto: x.texto, estado: x.estado }))}
                className="min-h-11 self-end rounded-lg border border-gray-600 px-4 text-sm text-gray-300 hover:border-gray-400"
              >
                {T.limparFiltros}
              </button>
            </div>
            {(regioes.erro || zonas.erro) && <p className="mt-3 text-sm text-yellow-100/90">{regioes.erro ?? zonas.erro}</p>}
          </div>
        )}

        {buscando && (
          <div className="mt-4 rounded-lg border border-teal-600/40 bg-teal-900/10 px-4 py-3" aria-live="polite">
            <div className="flex items-center justify-between gap-3">
              <p className="font-medium text-teal-400">{T.garimpando}</p>
              <button type="button" onClick={parar} className="min-h-11 rounded-lg border border-gray-600 px-4 text-sm text-gray-300 hover:border-gray-400">
                {T.parar}
              </button>
            </div>
            <p className="mt-1 text-sm text-gray-400">{demorando ? T.demorando : T.garimpandoSub}</p>
          </div>
        )}

        {busca.fase === 'parada' && (
          <p className="mt-4 rounded-lg border border-white/10 bg-[#0a0a0a] px-4 py-3 text-sm text-gray-300">{T.parada}</p>
        )}

        {busca.fase === 'falhou' && (
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-yellow-200/20 bg-yellow-200/5 px-4 py-3 text-sm text-yellow-100/90">
            <p>{busca.erro ?? T.semCarro}</p>
            <button
              type="button"
              onClick={() => busca.pedido && buscar(busca.pedido)}
              className="min-h-11 rounded-lg border border-yellow-200/40 px-4 text-yellow-100 hover:border-yellow-100"
            >
              {T.tentarDeNovo}
            </button>
          </div>
        )}

        {busca.fase === 'pronto' && resposta && !nadaAchado && (
          <div className="mt-4 flex min-h-[4.5rem] flex-wrap content-start items-center justify-between gap-x-4 gap-y-1 sm:min-h-0">
            <p className="text-sm text-gray-300" aria-live="polite">{resposta.informacao}</p>
            <div className="flex flex-wrap items-center gap-3">
              {novos > 0 && (
                <p className="rounded-full bg-teal-400 px-3 py-1 text-xs font-bold text-black">{novosDesde(novos)}</p>
              )}
              <p className="text-xs text-gray-500">{meta.join(' · ')}</p>
              <button type="button" onClick={() => busca.pedido && buscar(busca.pedido, true)} className={`${botao} text-sm`}>
                <RefreshCw size={14} aria-hidden="true" /> {T.buscarDeNovo}
              </button>
            </div>
          </div>
        )}

        {avisos.length > 0 && busca.fase === 'pronto' && (
          <div className="mt-3 space-y-1 rounded-lg border border-yellow-200/20 bg-yellow-200/5 px-4 py-3 text-sm text-yellow-100/90">
            {avisos.map((a) => <p key={`${a.codigo}|${a.mensagem}`}>{a.mensagem}</p>)}
          </div>
        )}

        <div className="mt-4">
          {DEV && resposta && <Diagnostico resposta={resposta} anuncios={lista} />}

          {busca.fase === 'inicial' && <p className="py-16 text-center text-gray-400">{T.inicial}</p>}
          {nadaAchado && (
            <div className="py-16 text-center text-gray-400">
              <p>{resposta?.informacao ?? T.nenhumComFiltro}</p>
              <button type="button" onClick={() => busca.pedido && buscar(busca.pedido, true)} className={`${botao} mx-auto mt-4 text-sm`}>
                <RefreshCw size={14} aria-hidden="true" /> {T.buscarDeNovo}
              </button>
            </div>
          )}

          {lista.length > 0 && (
            <>
              {DEMO && (
                <div className="mb-3 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-dashed border-orange-400/70 bg-orange-400/5 px-4 py-3 text-sm text-orange-200">
                  <p>{T.demoLigado}</p>
                  <button type="button" onClick={() => setFipeLigada((v) => !v)} className={`${botao} text-sm`}>
                    {fipeLigada ? T.demoEsconder : T.demoMostrar}
                  </button>
                </div>
              )}
              <p className="mb-3 text-xs text-gray-500">{T.legendaSinais}</p>
              {busca.blocos.map((bloco, n) => (
                <ul key={n} className={`grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 ${n > 0 ? 'mt-4' : ''}`}>
                  {bloco.map((a) => (
                    <CardCarro key={a.external_id} a={a} sinais={busca.sinais[a.external_id]} agora={busca.agora}
                      novo={sabeSeTemNovo && a.novo} demo={DEMO && fipeLigada} />
                  ))}
                </ul>
              ))}
              {busca.falhouMais && <p className="mt-6 text-center text-sm text-yellow-100/90">{T.maisFalhou}</p>}
              {resposta?.tem_mais && (
                <button
                  type="button"
                  onClick={verMais}
                  disabled={busca.carregandoMais}
                  className="mx-auto mt-6 flex min-h-12 items-center justify-center rounded-lg bg-teal-600 px-8 font-medium text-white transition-all hover:bg-teal-500 disabled:opacity-60"
                >
                  {busca.carregandoMais ? T.buscandoMais : busca.falhouMais ? T.tentarDeNovo : T.verMais}
                </button>
              )}
            </>
          )}
        </div>
      </main>
    </div>
  )
}
