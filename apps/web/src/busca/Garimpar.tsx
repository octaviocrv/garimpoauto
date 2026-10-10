// A tela do Garimpar: o carro visto como revenda. Mostra o que conta a favor, o que pede cuidado e o que
// não deu pra medir, cada linha com a conta e de onde ela veio. Não tem nota.
import { useEffect, useRef } from 'react'
import { AlertTriangle, ArrowLeft, CheckCircle2, ExternalLink, Flame, HelpCircle, ThumbsUp } from 'lucide-react'
import type { Anuncio } from '../types'
import type { Analise, Criterio } from './analise'
import { T } from './textos'

const reais = (v: number) => `R$ ${Math.round(v).toLocaleString('pt-BR')}`

function Linha({ c, tom }: { c: Criterio; tom: string }) {
  return (
    <li className="rounded-lg border border-white/10 bg-black/30 p-3">
      <p className="text-xs uppercase tracking-wide text-gray-500">{c.titulo}</p>
      <p className={`mt-0.5 font-semibold ${tom}`}>{c.resultado}</p>
      <p className="mt-1 text-sm text-gray-400">{c.fato}</p>
    </li>
  )
}

function Coluna({ titulo, Icone, tom, itens, vazio }: {
  titulo: string; Icone: typeof CheckCircle2; tom: string; itens: Criterio[]; vazio: string
}) {
  return (
    <section>
      <h3 className={`mb-3 flex items-center gap-2 text-base font-bold ${tom}`}>
        <Icone size={18} aria-hidden="true" /> {titulo}
      </h3>
      {itens.length === 0 ? (
        <p className="rounded-lg border border-dashed border-white/10 p-3 text-sm text-gray-500">{vazio}</p>
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
    <section className="mt-6">
      <h3 className="mb-3 text-base font-bold text-white">{T.numeros}</h3>
      <dl className="divide-y divide-white/10 rounded-lg border border-white/10 bg-black/30">
        {linhas.map(([nome, valor]) => (
          <div key={nome} className="flex items-baseline justify-between gap-4 px-3 py-2 text-sm">
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
    <div role="dialog" aria-modal="true" aria-label={T.analiseTitulo} className="fixed inset-0 z-50 overflow-y-auto bg-[#050505] text-white">
      <header className="sticky top-0 z-10 border-b border-white/10 bg-[#0a0a0a]">
        <div className="mx-auto flex h-16 max-w-4xl items-center justify-between gap-3 px-5">
          <button ref={fechar} type="button" onClick={onFechar} className="inline-flex min-h-11 items-center gap-2 text-sm text-gray-300 hover:text-white">
            <ArrowLeft size={16} aria-hidden="true" /> {T.voltar}
          </button>
          <a href={a.url} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-11 items-center gap-2 text-sm text-gray-400 hover:text-white">
            {T.verAnuncio} <ExternalLink size={14} aria-hidden="true" />
          </a>
        </div>
      </header>

      <main className="mx-auto max-w-4xl px-5 py-6">
        <div className="flex gap-4">
          {foto && <img src={foto} alt="" referrerPolicy="no-referrer" className="h-24 w-32 flex-none rounded-lg object-cover sm:h-28 sm:w-40" />}
          <div className="min-w-0">
            <h2 className="text-lg font-bold leading-snug">{a.modelo_original ?? a.titulo ?? 'Modelo não informado'}</h2>
            <p className="mt-1 text-xl font-bold">{a.preco === null ? 'Preço não informado' : reais(a.preco)}</p>
            <p className="mt-1 text-sm text-gray-400">{detalhes}</p>
          </div>
        </div>

        <div className={`mt-5 rounded-lg border p-4 ${nivel === 'quente' ? 'border-amber-300/70 bg-amber-300/10' : nivel === 'boa' ? 'border-teal-400/60 bg-teal-400/10' : 'border-white/10 bg-[#0a0a0a]'}`}>
          <p className={`flex items-center gap-2 text-lg font-bold ${nivel === 'quente' ? 'text-amber-200' : nivel === 'boa' ? 'text-teal-300' : 'text-gray-200'}`}>
            {nivel === 'quente' && <Flame size={20} aria-hidden="true" />}
            {nivel === 'boa' && <ThumbsUp size={20} aria-hidden="true" />}
            {nivel === 'quente' ? T.quente : nivel === 'boa' ? T.boa : 'Sem destaque'}
          </p>
          <p className="mt-1 text-sm text-gray-300">{analise?.motivo ?? 'Esse carro ainda não foi analisado.'}</p>
        </div>
        <p className="mt-3 text-xs text-gray-500">{T.comoLer}</p>

        <div className="mt-6 grid gap-6 md:grid-cols-2">
          <Coluna titulo={T.porQueVale} Icone={CheckCircle2} tom="text-teal-300" itens={lista.filter((c) => c.veredito === 'favor')} vazio={T.nadaAFavor} />
          <Coluna titulo={T.porQueNao} Icone={AlertTriangle} tom="text-amber-300" itens={lista.filter((c) => c.veredito === 'atencao')} vazio={T.nadaContra} />
        </div>

        {analise && <Numeros a={a} an={analise} />}

        {lista.some((c) => c.veredito === 'neutro' || c.veredito === 'semdado') && (
          <section className="mt-6">
            <h3 className="mb-3 flex items-center gap-2 text-base font-bold text-gray-300">
              <HelpCircle size={18} aria-hidden="true" /> {T.naoMedido}
            </h3>
            <ul className="flex flex-col gap-2">
              {lista.filter((c) => c.veredito === 'neutro' || c.veredito === 'semdado').map((c) => <Linha key={c.id} c={c} tom="text-gray-200" />)}
            </ul>
          </section>
        )}

        <p className="mt-6 rounded-lg border border-dashed border-white/15 p-3 text-xs text-gray-500">{T.aindaNaoEntra}</p>
      </main>
    </div>
  )
}
