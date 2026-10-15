import { useCallback, useEffect, useState } from 'react'
import { ArrowLeft, CarFront, ChevronDown, Gauge, RefreshCw, Search, SlidersHorizontal } from 'lucide-react'
import { CardCarro } from './CardCarro'
import { Diagnostico } from './Diagnostico'
import { Garimpar } from './Garimpar'
import { SearchHologram } from './SearchHologram'
import {
  ANUNCIANTES, CAMBIOS, COMBUSTIVEIS, ESTADOS, FILTROS_DO_RASCUNHO, ORDENS, RASCUNHO_VAZIO, montarPedidoOuVitrine,
  nomeDoEstado, type Rascunho,
} from './pedido'
import { useRegioes, useZonas } from './regioes'
import { T, buscadoAs, novosDesde } from './textos'
import { useBusca } from './useBusca'
import type { Anuncio } from '../types'

const DEV = new URLSearchParams(window.location.search).get('dev') === '1'

const campo = 'search-field min-h-11 w-full rounded-xl border border-white/10 bg-black/30 px-3 text-sm text-white placeholder:text-gray-600 focus:border-cyan-300/60 focus:outline-none focus:ring-2 focus:ring-cyan-300/10'
const botao = 'inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/[0.03] px-4 text-gray-300 transition-colors hover:border-cyan-300/30 hover:bg-cyan-300/[0.06] hover:text-white'

// "informacao" chega como frase pronta do servidor (ex.: "Mostrando 50 de 2.294 carros. Toca em
// Ver mais pra ver o resto."). Só a 1ª frase aparece, com os números em ciano; o resto some (o
// botão "Ver mais" já deixa claro que dá pra carregar mais).
function Informacao({ texto }: { texto: string }) {
  const [primeira] = texto.split(/(?<=\.) +/)
  const numeros = (s: string) => s.split(/(\d[\d.,]*\d|\d)/g).map((parte, i) => (
    /\d/.test(parte) ? <strong key={i} className="text-cyan-300">{parte}</strong> : parte
  ))
  return <span className="text-gray-50">{numeros(primeira)}</span>
}

function Campo({ nome, children }: { nome: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5 font-mono text-[10px] uppercase tracking-[0.12em] text-gray-500">
      <span>{nome}</span>
      {children}
    </label>
  )
}

export function PaginaBusca() {
  const { estado: busca, buscar, verMais, parar, atualizarFipe } = useBusca(DEV)
  const [r, setR] = useState<Rascunho>(RASCUNHO_VAZIO)
  const [painel, setPainel] = useState(false)
  const [demorando, setDemorando] = useState(false)
  const [aberto, setAberto] = useState<Anuncio | null>(null) // o carro da tela do Garimpar
  const fecharGarimpar = useCallback(() => setAberto(null), [])
  const aplicarFipe = useCallback((anuncio: Anuncio) => {
    setAberto(anuncio)
    atualizarFipe(anuncio.external_id, {
      fipe: anuncio.fipe ?? null,
      fipe_bloqueio: anuncio.fipe_bloqueio ?? null,
      fipe_ausencia: anuncio.fipe_ausencia ?? null,
    })
  }, [atualizarFipe])
  const regioes = useRegioes(r.estado)
  const zonas = useZonas(r.estado, r.regiao)

  const buscando = busca.fase === 'buscando'
  const resposta = busca.resposta

  // Ao abrir a tela, a vitrine: o estado padrão, mais recentes, página 1. O "Ver mais" é manual.
  useEffect(() => {
    buscar(montarPedidoOuVitrine(RASCUNHO_VAZIO))
  }, [buscar])

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
    buscar(montarPedidoOuVitrine(r)) // campo vazio e sem filtro volta pra vitrine
  }
  const filtrosAtivos = FILTROS_DO_RASCUNHO.filter((k) => r[k] !== '').length

  const lista = busca.anuncios
  const primeira = busca.primeira
  const meta = [
    resposta ? nomeDoEstado(resposta.estado_aplicado) : null,
    primeira?.coletado_em ? buscadoAs(primeira.coletado_em) : null,
  ].filter(Boolean)
  const avisos = busca.avisos.filter((a) => a.codigo !== 'fonte_parcial') // a falha a tela já conta do jeito dela
  // Selo e contagem de novos só quando o servidor tem banco e já houve busca igual antes. null é "não sei".
  const sabeSeTemNovo = busca.primeira?.primeira_busca === false
  const novos = sabeSeTemNovo ? resposta?.novos ?? 0 : 0
  const nadaAchado = busca.fase === 'pronto' && lista.length === 0

  return (
    <div className="search-page min-h-svh font-sans text-white">
      <header className="search-header">
        <div className="mx-auto flex h-[4.5rem] max-w-[90rem] items-center justify-between gap-3 px-5 lg:px-8">
          <span className="flex items-center gap-3">
            <span className="relative grid h-11 w-11 flex-none place-items-center overflow-hidden rounded-full border border-cyan-300/50 bg-teal-950 shadow-[0_0_24px_rgba(0,240,255,0.16)]">
              <img src="/mascot/han-profile.jpeg" alt="" className="h-full w-full object-cover" />
            </span>
            <span>
              <span className="block whitespace-nowrap text-base font-extrabold leading-none tracking-[-0.02em]">Garimpo Auto</span>
              <span className="mt-1 block font-mono text-[9px] uppercase tracking-[0.2em] text-cyan-300/60">Central de oportunidades</span>
            </span>
          </span>
          <a href="#inicio" className="inline-flex min-h-11 items-center gap-1.5 rounded-xl px-3 text-sm text-gray-400 transition-colors hover:bg-white/5 hover:text-white">
            <ArrowLeft size={16} aria-hidden="true" /> Início
          </a>
        </div>
      </header>

      <main className="relative mx-auto max-w-[90rem] px-4 py-7 sm:px-5 lg:px-8 lg:py-10">
        <section className="search-console" aria-labelledby="search-title">
          <div className="search-console__intro">
            <SearchHologram />
            <div className="search-console__copy">
              <p className="mb-4 font-mono text-[10px] font-semibold uppercase tracking-[0.2em] text-cyan-300">
                Central de oportunidades
              </p>
              <h1 id="search-title" className="search-title max-w-2xl text-4xl leading-[1.08] tracking-[-0.02em] text-white sm:text-5xl lg:text-[3.5rem]">
                Encontre o carro certo.<br /><span className="search-title__accent text-cyan-300">Antes de todo mundo.</span>
              </h1>
              <p className="mt-3 max-w-xl text-sm leading-relaxed text-gray-400">
                Busque, filtre e compare anúncios recentes em uma leitura só.
              </p>
            </div>
            <div className="search-console__mascot" aria-hidden="true">
              <img src="/mascot/hiro-metade-half-body.svg" alt="" />
            </div>
          </div>

          <form onSubmit={buscarAgora} className="search-console__form">
            <label className="search-console__query">
              <Search size={20} className="flex-none text-cyan-300" aria-hidden="true" />
              <span className="sr-only">Qual carro você quer?</span>
              <input
                type="search"
                aria-label="Qual carro você quer?"
                className="min-w-0 flex-1 bg-transparent text-base text-white outline-none placeholder:text-gray-600 sm:text-lg"
                placeholder={T.placeholder}
                value={r.texto}
                onChange={(e) => mudar('texto', e.target.value)}
                enterKeyHint="search"
                autoFocus
              />
            </label>
            <label className="relative flex items-center border-t border-white/10 sm:border-l sm:border-t-0">
              <span className="sr-only">Estado</span>
              <select aria-label="Estado" className="h-14 w-full appearance-none bg-transparent px-4 pr-9 text-sm text-gray-200 outline-none sm:w-48" value={r.estado} onChange={(e) => mudarEstado(e.target.value)}>
                {ESTADOS.map(([sigla, nome]) => <option key={sigla} value={sigla}>{nome}</option>)}
              </select>
              <ChevronDown size={15} className="pointer-events-none absolute right-4 text-gray-500" aria-hidden="true" />
            </label>
            <button
              type="submit"
              className="search-console__submit"
            >
              <Search size={17} aria-hidden="true" /> {T.buscar}
            </button>
          </form>
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
            <p className="hidden items-center gap-2 text-xs tracking-normal text-gray-400 sm:flex">
              <Gauge size={13} aria-hidden="true" /> Busca atualizada em tempo real
            </p>
            <button type="button" onClick={() => setPainel((p) => !p)} aria-expanded={painel} className={`${botao} ml-auto`}>
              <SlidersHorizontal size={16} aria-hidden="true" /> {T.filtros}
              {filtrosAtivos > 0 && <span className="grid h-5 min-w-5 place-items-center rounded-full bg-cyan-300 px-1 text-[10px] font-bold text-cyan-950">{filtrosAtivos}</span>}
              <ChevronDown size={14} className={`transition-transform ${painel ? 'rotate-180' : ''}`} aria-hidden="true" />
            </button>
          </div>
        </section>

        {painel && (
          <div className="filter-panel">
            <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="font-semibold text-gray-100">Refine seu garimpo</p>
                <p className="mt-1 text-xs text-gray-500">{T.dicaFiltros}</p>
              </div>
              <button
                type="button"
                onClick={() => setR((x) => ({ ...RASCUNHO_VAZIO, texto: x.texto, estado: x.estado }))}
                className="min-h-9 rounded-lg px-3 text-xs font-semibold text-gray-400 transition-colors hover:bg-white/5 hover:text-white"
              >
                {T.limparFiltros}
              </button>
            </div>
            <div className="grid grid-cols-2 gap-x-3 gap-y-4 sm:grid-cols-3 lg:grid-cols-5">
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
            </div>
            {(regioes.erro || zonas.erro) && <p className="mt-3 text-sm text-yellow-100/90">{regioes.erro ?? zonas.erro}</p>}
          </div>
        )}

        {buscando && (
          <div className="search-status is-loading" aria-live="polite">
            <div className="flex items-center justify-between gap-3">
              <p className="flex items-center gap-2 font-semibold text-cyan-300"><span className="search-status__pulse" />{T.garimpando}</p>
              <button type="button" onClick={parar} className="min-h-10 rounded-xl border border-white/10 px-4 text-sm text-gray-300 hover:border-white/25">
                {T.parar}
              </button>
            </div>
            <p className="mt-1 text-sm text-gray-400">{demorando ? T.demorando : T.garimpandoSub}</p>
          </div>
        )}

        {busca.fase === 'parada' && (
          <p className="search-status text-sm text-gray-300">{T.parada}</p>
        )}

        {busca.fase === 'falhou' && (
          <div className="search-status flex flex-wrap items-center justify-between gap-3 border-yellow-200/20 bg-yellow-200/5 text-sm text-yellow-100/90">
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
          <div className="results-toolbar">
            <div className="min-w-0">
              <p className="flex items-start gap-2.5 text-[15px] font-bold leading-snug sm:items-center sm:text-base" aria-live="polite">
                <CarFront size={22} className="mt-0.5 flex-none text-cyan-300 sm:mt-0" aria-hidden="true" />
                <Informacao texto={resposta.informacao} />
              </p>
              <p className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1.5 font-mono text-[10px] uppercase tracking-[0.1em] text-gray-500 sm:tracking-[0.12em]">
                {meta.map((item, i) => i === 0 ? (
                  <span key={i} className="rounded-md bg-teal-400/15 px-2 py-1 font-bold text-teal-300">{item}</span>
                ) : (
                  <span key={i} className="flex items-center gap-2">
                    <span className="text-gray-700" aria-hidden="true">·</span>{item}
                  </span>
                ))}
              </p>
            </div>
            <div className="flex w-full flex-col gap-2.5 sm:w-auto sm:flex-row sm:flex-nowrap sm:items-center sm:gap-3">
              {novos > 0 && (
                <p className="inline-flex min-h-11 items-center justify-center rounded-xl border border-cyan-200/30 bg-cyan-300/15 px-4 text-sm font-bold text-cyan-200">{novosDesde(novos)}</p>
              )}
              <button type="button" onClick={() => busca.pedido && buscar(busca.pedido, true)} className={`${botao} w-full justify-center whitespace-nowrap text-sm sm:w-auto`}>
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

        <div className="mt-5">
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
              {busca.blocos.map((bloco, n) => (
                <ul key={n} className={`vehicle-grid grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4 ${n > 0 ? 'mt-5' : ''}`}>
                  {bloco.map((a) => (
                    <CardCarro key={a.external_id} a={a} sinais={busca.sinais[a.external_id]} agora={busca.agora}
                      novo={sabeSeTemNovo && a.novo}
                      analise={busca.analises[a.external_id]} onGarimpar={setAberto} />
                  ))}
                </ul>
              ))}
              {busca.falhouMais && <p className="mt-6 text-center text-sm text-yellow-100/90">{T.maisFalhou}</p>}
              {resposta?.tem_mais && (
                <button
                  type="button"
                  onClick={verMais}
                  disabled={busca.carregandoMais}
                  className="search-console__submit mx-auto mt-8 min-h-12 rounded-xl px-8 disabled:opacity-60"
                >
                  {busca.carregandoMais ? T.buscandoMais : busca.falhouMais ? T.tentarDeNovo : T.verMais}
                </button>
              )}
            </>
          )}
        </div>
      </main>
      {aberto && (
        <Garimpar
          a={aberto}
          analise={busca.analises[aberto.external_id]}
          onFechar={fecharGarimpar}
          onFipe={aplicarFipe}
        />
      )}
    </div>
  )
}
