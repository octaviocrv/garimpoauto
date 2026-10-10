import { memo } from 'react'
import { ChevronRight, Clock, ExternalLink, Flame, Pickaxe, Route, Star, ThumbsUp, TrendingDown, type LucideIcon } from 'lucide-react'
import type { Anuncio } from '../types'
import type { Analise } from './analise'
import { fipeDe, type ReferenciaFipe } from './fipe'
import { dataCurta, prefixoData, type Sinal, type TipoSinal } from './sinais'
import { T } from './textos'

const preco = (v: number) => `R$ ${v.toLocaleString('pt-BR')}`
const SEM_SINAIS: Sinal[] = []

const ICONE: Record<TipoSinal, LucideIcon> = { preco: TrendingDown, km: Route, recente: Clock }
// Ouro Garimpo é só do preço (o brand-kit reserva o ouro pra bom negócio). O resto é teal.
const COR_SINAL: Record<TipoSinal, string> = {
  preco: 'bg-amber-300/10 text-amber-300',
  km: 'bg-teal-400/10 text-teal-300',
  recente: 'bg-teal-400/10 text-teal-300',
}

function FipeDoCard({ f }: { f: ReferenciaFipe }) {
  const abaixo = f.diferencaReais > 0
  const igual = f.diferencaReais === 0
  return (
    <div className="rounded-lg border border-dashed border-orange-400/70 bg-orange-400/5 px-3 py-2 text-sm">
      {f.exemplo && (
        <p className="mb-1 inline-block rounded-full bg-orange-400 px-2 py-0.5 text-xs font-bold text-black">{T.exemplo}</p>
      )}
      <p className="text-gray-300">FIPE {preco(f.valor)}</p>
      <p className={abaixo ? 'font-semibold text-teal-300' : 'text-gray-400'}>
        {igual ? 'No valor da FIPE' : `${preco(Math.abs(f.diferencaReais))} ${abaixo ? 'abaixo' : 'acima'} (${Math.abs(f.diferencaPercentual)}%)`}
      </p>
    </div>
  )
}

interface Props {
  a: Anuncio
  sinais?: Sinal[] // calculados quando o carro chegou
  agora: number // hora de referência da busca, pra a data não mudar sozinha
  novo: boolean // a página já decidiu se pode mostrar o selo
  demo: boolean // FIPE de exemplo ligada
  analise?: Analise // calculada quando o carro chegou
  onGarimpar: (a: Anuncio) => void // abre a tela do Garimpar. Tem que ser uma função estável por causa do memo
}

function Card({ a, sinais = SEM_SINAIS, agora, novo, demo, analise, onGarimpar }: Props) {
  const foto = a.imagens[0]
  const local = [a.cidade, a.estado].filter(Boolean).join(', ')
  const detalhes = [a.ano, a.km !== null ? `${a.km.toLocaleString('pt-BR')} km` : null, local].filter(Boolean)
  const quando = dataCurta(a.anunciado_em, agora)
  const jaTemDataNoSinal = sinais.some((s) => s.tipo === 'recente')
  const fipe = demo ? fipeDe(a) : null
  const nivel = analise?.nivel ?? null
  const vale = sinais.length + (novo ? 1 : 0) >= 2
  const borda = nivel === 'quente' ? 'border-amber-300/80 ring-1 ring-amber-300/60'
    : vale || nivel === 'boa' ? 'border-teal-400/70 ring-1 ring-teal-400/50' : 'border-white/10'
  return (
    <li className={`flex flex-col overflow-hidden rounded-lg border bg-[#0a0a0a] ${borda}`}>
      <div className="relative aspect-[4/3] w-full bg-black/60">
        {foto && (
          <img src={foto} alt="" loading="lazy" referrerPolicy="no-referrer" className="h-full w-full object-cover" />
        )}
        {novo && (
          <span className="absolute left-2 top-2 rounded-full bg-teal-400 px-3 py-1 text-xs font-bold text-black">{T.novo}</span>
        )}
      </div>
      <div className="flex flex-1 flex-col gap-2 p-4">
        {nivel && analise && (
          <button
            type="button"
            onClick={() => onGarimpar(a)}
            className={`flex min-h-11 items-center gap-2 rounded-lg px-3 py-2 text-left text-sm ${nivel === 'quente' ? 'bg-amber-300/15 text-amber-200' : 'bg-teal-400/10 text-teal-300'}`}
          >
            {nivel === 'quente' ? <Flame size={18} className="flex-none" aria-hidden="true" /> : <ThumbsUp size={18} className="flex-none" aria-hidden="true" />}
            <span className="min-w-0 flex-1">
              <span className="block font-bold">{nivel === 'quente' ? T.quente : T.boa}</span>
              <span className="block text-xs opacity-90">{analise.resumo}</span>
            </span>
            <ChevronRight size={16} className="flex-none" aria-hidden="true" />
          </button>
        )}
        <p className={`text-xl font-bold ${a.preco === null ? 'text-gray-500' : 'text-white'}`}>
          {a.preco === null ? 'Preço não informado' : preco(a.preco)}
        </p>
        {fipe && <FipeDoCard f={fipe} />}
        <p className="text-base font-medium leading-snug text-gray-200">{a.modelo_original ?? a.titulo ?? 'Modelo não informado'}</p>
        <p className="text-sm text-gray-400">{detalhes.join(' · ')}</p>
        {quando && !jaTemDataNoSinal && <p className="text-xs text-gray-500">{prefixoData(a)} {quando}</p>}
        {sinais.length > 0 && (
          <ul className="flex flex-col gap-1.5">
            {sinais.map((s) => {
              const Icone = ICONE[s.tipo]
              return (
                <li key={s.tipo} className={`flex items-start gap-2 rounded-lg px-2.5 py-1.5 text-sm ${COR_SINAL[s.tipo]}`}>
                  <Icone size={16} className="mt-0.5 flex-none" aria-hidden="true" />
                  <span className="min-w-0">
                    <span className="block font-semibold">{s.texto}</span>
                    {s.detalhe && <span className="block text-xs opacity-80">{s.detalhe}</span>}
                  </span>
                </li>
              )
            })}
          </ul>
        )}
        <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
          {a.anunciante_profissional !== null && (
            <span className="rounded-md border border-teal-600/60 px-2 py-1 font-semibold text-teal-400">
              {a.anunciante_profissional ? 'Loja' : 'Particular'}
            </span>
          )}
          {a.em_destaque && (
            <span className="rounded-md border border-white/15 px-2 py-1 text-gray-400">{T.destaque}</span>
          )}
          {a.nota_anunciante !== null && (
            <span className="inline-flex items-center gap-1 text-yellow-200">
              <Star size={13} aria-hidden="true" /> Nota {a.nota_anunciante.toLocaleString('pt-BR')}
            </span>
          )}
        </div>
        <div className="mt-auto flex flex-col gap-2 pt-1">
          <button
            type="button"
            onClick={() => onGarimpar(a)}
            className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-teal-600 px-4 text-sm font-medium text-white transition-all hover:bg-teal-500"
          >
            <Pickaxe size={16} aria-hidden="true" /> {T.garimpar}
          </button>
          <a
            href={a.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-gray-600 bg-black/40 px-4 text-sm text-gray-300 transition-all hover:border-gray-400 hover:text-white"
          >
            {T.verAnuncio} <ExternalLink size={14} aria-hidden="true" />
          </a>
        </div>
      </div>
    </li>
  )
}

// memo: digitar na busca não redesenha os cards já na tela
export const CardCarro = memo(Card)
