// A tela do Garimpar: o carro visto como revenda. Mostra o que conta a favor, o que pede cuidado e o que
// não deu pra medir, cada linha com a conta e de onde ela veio. Não tem nota.
import { useEffect, useRef } from 'react'
import { AlertTriangle, ArrowLeft, CheckCircle2, ExternalLink, Flame, HelpCircle, MapPin, ShieldCheck, Sparkles, ThumbsUp } from 'lucide-react'
import type { Anuncio } from '../types'
import type { Analise, Criterio } from './analise'
import { T } from './textos'

const reais = (v: number) => `R$ ${Math.round(v).toLocaleString('pt-BR')}`

function Linha({ c, tom }: { c: Criterio; tom: string }) {
  return (
    <li className="analysis-item">
      <p className="font-mono text-[9px] uppercase tracking-[0.15em] text-gray-600">{c.titulo}</p>
      <p className={`mt-1 font-bold ${tom}`}>{c.resultado}</p>
      <p className="mt-1.5 text-sm leading-relaxed text-gray-400">{c.fato}</p>
    </li>
  )
}

function Coluna({ titulo, Icone, tom, itens, vazio }: {
  titulo: string; Icone: typeof CheckCircle2; tom: string; itens: Criterio[]; vazio: string
}) {
  return (
    <section className="analysis-column">
      <h3 className={`mb-4 flex items-center gap-2 text-base font-bold ${tom}`}>
        <span className="grid h-8 w-8 place-items-center rounded-lg border border-current/20 bg-current/[0.06]"><Icone size={17} aria-hidden="true" /></span> {titulo}
      </h3>
      {itens.length === 0 ? (
        <p className="rounded-xl border border-dashed border-white/10 p-4 text-sm text-gray-500">{vazio}</p>
      ) : (
        <ul className="flex flex-col gap-2">{itens.map((c) => <Linha key={c.id} c={c} tom={tom} />)}</ul>
      )}
    </section>
  )
}

function Numeros({ a, an }: { a: Anuncio; an: Analise }) {
  const m = an.mercado
  const g = an.margem
  if (!m || !g || a.preco === null) return null
  const linhas: [string, string][] = [
    ['Preço do anúncio', reais(a.preco)],
    [`Mediana de ${m.n} ${a.modelo} ${a.ano} carregados`, reais(m.mediana)],
    ['Menor e maior preço dos iguais', `${reais(m.minimo)} e ${reais(m.maximo)}`],
    ['Diferença bruta pro mercado', `${g.bruta >= 0 ? '' : '-'}${reais(Math.abs(g.bruta))}`],
    ['Custo estimado de revenda', `-${reais(g.custo)}`],
    ['Margem estimada', `${g.estimada >= 0 ? '' : '-'}${reais(Math.abs(g.estimada))}`],
  ]
  return (
    <section className="mt-8">
      <h3 className="mb-4 flex items-center gap-2 text-base font-bold text-white"><ShieldCheck size={18} className="text-cyan-300" aria-hidden="true" /> {T.numeros}</h3>
      <dl className="divide-y divide-white/[0.07] overflow-hidden rounded-2xl border border-white/10 bg-white/[0.025]">
        {linhas.map(([nome, valor]) => (
          <div key={nome} className="flex items-baseline justify-between gap-4 px-4 py-3 text-sm">
            <dt className="text-gray-400">{nome}</dt>
            <dd className="flex-none font-semibold text-white">{valor}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}

export function Garimpar({ a, analise, onFechar }: { a: Anuncio; analise: Analise | undefined; onFechar: () => void }) {
  const fechar = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    fechar.current?.focus()
    const antes = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const tecla = (e: KeyboardEvent) => { if (e.key === 'Escape') onFechar() }
    window.addEventListener('keydown', tecla)
    return () => { window.removeEventListener('keydown', tecla); document.body.style.overflow = antes }
  }, [onFechar])

  const nivel = analise?.nivel ?? null
  const foto = a.imagens[0]
  const local = [a.cidade, a.estado].filter(Boolean).join(', ')
  const detalhes = [a.ano, a.km !== null ? `${a.km.toLocaleString('pt-BR')} km` : null, local].filter(Boolean).join(' · ')
  const lista = analise?.criterios ?? []

  return (
    <div role="dialog" aria-modal="true" aria-label={T.analiseTitulo} className="analysis-page fixed inset-0 z-50 overflow-y-auto text-white">
      <header className="analysis-header sticky top-0 z-10">
        <div className="mx-auto flex h-[4.5rem] max-w-5xl items-center justify-between gap-3 px-5">
          <button ref={fechar} type="button" onClick={onFechar} className="inline-flex min-h-11 items-center gap-2 rounded-xl px-3 text-sm text-gray-300 transition-colors hover:bg-white/5 hover:text-white">
            <ArrowLeft size={16} aria-hidden="true" /> {T.voltar}
          </button>
          <span className="hidden items-center gap-2 font-mono text-[9px] uppercase tracking-[0.18em] text-cyan-300/60 sm:flex">
            <Sparkles size={13} aria-hidden="true" /> Leitura de oportunidade
          </span>
          <a href={a.url} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-11 items-center gap-2 rounded-xl border border-white/10 px-3 text-sm text-gray-300 transition-colors hover:border-cyan-300/30 hover:text-cyan-200">
            {T.verAnuncio} <ExternalLink size={14} aria-hidden="true" />
          </a>
        </div>
      </header>

      <main className="relative mx-auto max-w-5xl px-5 py-7 sm:py-10">
        <section className="analysis-hero">
          <div className="analysis-hero__media">
            {foto ? <img src={foto} alt="" decoding="async" referrerPolicy="no-referrer" className="h-full w-full object-cover" /> : <div className="h-full bg-black/40" />}
            <div className="absolute inset-0 bg-gradient-to-t from-[#071012] via-transparent to-transparent" />
          </div>
          <div className="min-w-0 flex-1 p-5 sm:p-7">
            <p className="font-mono text-[9px] uppercase tracking-[0.18em] text-cyan-300/70">Análise de revenda</p>
            <h2 className="mt-2 text-2xl font-extrabold leading-tight tracking-[-0.035em] sm:text-3xl">{a.modelo_original ?? a.titulo ?? 'Modelo não informado'}</h2>
            <p className="mt-3 text-3xl font-extrabold tracking-[-0.045em] text-white">{a.preco === null ? 'Preço não informado' : reais(a.preco)}</p>
            <p className="mt-3 flex items-center gap-1.5 text-sm text-gray-400"><MapPin size={14} aria-hidden="true" /> {detalhes}</p>
          </div>
        </section>

        <div className={`analysis-verdict ${nivel === 'quente' ? 'is-hot' : nivel === 'boa' ? 'is-good' : ''}`}>
          <div className={`grid h-11 w-11 flex-none place-items-center rounded-xl ${nivel === 'quente' ? 'bg-amber-300/15 text-amber-200' : nivel === 'boa' ? 'bg-cyan-300/10 text-cyan-200' : 'bg-white/5 text-gray-400'}`}>
            {nivel === 'quente' ? <Flame size={22} aria-hidden="true" /> : nivel === 'boa' ? <ThumbsUp size={22} aria-hidden="true" /> : <HelpCircle size={22} aria-hidden="true" />}
          </div>
          <div>
            <p className={`font-mono text-[9px] uppercase tracking-[0.16em] ${nivel === 'quente' ? 'text-amber-300/70' : 'text-cyan-300/60'}`}>Veredito do Garimpo</p>
            <p className={`mt-0.5 text-xl font-bold ${nivel === 'quente' ? 'text-amber-100' : nivel === 'boa' ? 'text-cyan-100' : 'text-gray-200'}`}>
              {nivel === 'quente' ? T.quente : nivel === 'boa' ? T.boa : 'Sem destaque'}
            </p>
            <p className="mt-1 text-sm leading-relaxed text-gray-400">{analise?.motivo ?? 'Esse carro ainda não foi analisado.'}</p>
          </div>
        </div>
        <p className="mt-3 text-xs leading-relaxed text-gray-600">{T.comoLer}</p>

        <div className="mt-8 grid gap-5 md:grid-cols-2">
          <Coluna titulo={T.porQueVale} Icone={CheckCircle2} tom="text-teal-300" itens={lista.filter((c) => c.veredito === 'favor')} vazio={T.nadaAFavor} />
          <Coluna titulo={T.porQueNao} Icone={AlertTriangle} tom="text-amber-300" itens={lista.filter((c) => c.veredito === 'atencao')} vazio={T.nadaContra} />
        </div>

        {analise && <Numeros a={a} an={analise} />}

        {lista.some((c) => c.veredito === 'neutro' || c.veredito === 'semdado') && (
          <section className="mt-8">
            <h3 className="mb-3 flex items-center gap-2 text-base font-bold text-gray-300">
              <HelpCircle size={18} aria-hidden="true" /> {T.naoMedido}
            </h3>
            <ul className="flex flex-col gap-2">
              {lista.filter((c) => c.veredito === 'neutro' || c.veredito === 'semdado').map((c) => <Linha key={c.id} c={c} tom="text-gray-200" />)}
            </ul>
          </section>
        )}

        <p className="mt-8 rounded-xl border border-dashed border-white/10 p-4 text-xs leading-relaxed text-gray-600">{T.aindaNaoEntra}</p>
      </main>
    </div>
  )
}
