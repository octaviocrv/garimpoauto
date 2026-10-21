import { memo } from 'react'
import { ArrowUpRight, ChevronRight, Clock3, Flame, MapPin, Pickaxe, Route, Star, ThumbsUp, TrendingDown, type LucideIcon } from 'lucide-react'
import type { Anuncio } from '../types'
import { ABAIXO_BOM, PRECO_SUSPEITO, type Analise } from './analise'
import { fipeDe, type ReferenciaFipe } from './fipe'
import { dataCurta, prefixoData, type Sinal, type TipoSinal } from './sinais'
import { seloFipeAbaixo, seloFipeAcima, T } from './textos'

const preco = (v: number) => `R$ ${v.toLocaleString('pt-BR')}`
const SEM_SINAIS: Sinal[] = []

const ICONE: Record<TipoSinal, LucideIcon> = { km: Route, recente: Clock3 }
const COR_SINAL: Record<TipoSinal, string> = {
  km: 'bg-teal-400/10 text-teal-300',
  recente: 'bg-teal-400/10 text-teal-300',
}

function FipeDoCard({ f }: { f: ReferenciaFipe }) {
  const diferenca = f.diferencaPercentual
  const proporcao = (f.valor - f.diferencaReais) / f.valor
  const alerta = proporcao <= 1 - PRECO_SUSPEITO
  const oportunidade = proporcao <= 1 - ABAIXO_BOM && !alerta
  const texto = alerta
    ? T.fipePrecoEstranho
    : diferenca < 0
      ? seloFipeAcima(Math.abs(diferenca))
      : diferenca === 0
        ? T.fipeNoValor
        : oportunidade
          ? seloFipeAbaixo(diferenca)
          : null
  if (!texto) return null
  return (
    <li
      title={`FIPE ${preco(f.valor)}`}
      className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs ${
        oportunidade ? 'bg-teal-400/10 text-teal-300'
          : alerta ? 'bg-amber-300/10 text-amber-200'
            : 'bg-white/[0.05] text-gray-400'
      }`}
    >
      <TrendingDown size={14} className="flex-none" aria-hidden="true" />
      <span className="font-semibold">{texto}</span>
    </li>
  )
}

interface Props {
  a: Anuncio
  sinais?: Sinal[] // calculados quando o carro chegou
  agora: number // hora de referência da busca, pra a data não mudar sozinha
  novo: boolean // a página já decidiu se pode mostrar o selo
  analise?: Analise // calculada quando o carro chegou
  onGarimpar: (a: Anuncio) => void // abre a tela do Garimpar. Tem que ser uma função estável por causa do memo
}

function Card({ a, sinais = SEM_SINAIS, agora, novo, analise, onGarimpar }: Props) {
  const foto = a.imagens[0]
  const local = [a.cidade, a.estado].filter(Boolean).join(', ')
  const quando = dataCurta(a.anunciado_em, agora)
  const fipe = fipeDe(a)
  const nivel = analise?.nivel ?? null
  const sinalRecente = sinais.find((s) => s.tipo === 'recente')
  const outrosSinais = sinais.filter((s) => s.tipo !== 'recente')
  const textoTempo = sinalRecente?.texto ?? (quando ? `${prefixoData(a)} ${quando}` : null)
  const vale = sinais.length + (novo ? 1 : 0) >= 2
  const tom = nivel === 'quente' ? 'is-hot' : vale || nivel === 'boa' ? 'is-good' : ''
  return (
    <li className={`vehicle-card group ${tom}`}>
      <div className="vehicle-card__media">
        {foto && (
          <img src={foto} alt="" loading="lazy" decoding="async" referrerPolicy="no-referrer" className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.025]" />
        )}
        <div className="vehicle-card__shade" aria-hidden="true" />
        {novo && (
          <span className="absolute left-3 top-3 rounded-full border border-cyan-200/50 bg-cyan-300 px-3 py-1 font-mono text-[10px] font-bold uppercase tracking-[0.14em] text-cyan-950 shadow-[0_0_20px_rgba(34,211,238,0.35)]">{T.novo}</span>
        )}
        {textoTempo && (
          <div className="vehicle-card__time">
            <span className="vehicle-card__pulse" aria-hidden="true" />
            <Clock3 size={14} aria-hidden="true" />
            <span>{textoTempo}</span>
          </div>
        )}
        {a.source === 'olx' ? (
          <img
            src="/logos/olx.png"
            alt="OLX"
            className="absolute bottom-3 right-3 h-7 w-7 rounded-full border border-white/20 bg-[#6e0ad7] p-1 object-contain shadow"
          />
        ) : (
          <span className="absolute bottom-3 right-3 rounded-full border border-white/20 bg-black/70 px-2.5 py-1 text-[11px] font-semibold uppercase text-white/80">
            {a.source}
          </span>
        )}
      </div>
      <div className="flex flex-1 flex-col p-4 sm:p-[18px]">
        <div className="mb-3 flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-cyan-300/70">Valor anunciado</p>
            <p className={`mt-0.5 text-[1.7rem] font-extrabold leading-none tracking-[-0.045em] ${a.preco === null ? 'text-gray-500' : 'text-white'}`}>
              {a.preco === null ? 'Sob consulta' : preco(a.preco)}
            </p>
          </div>
          {a.nota_anunciante !== null && (
            <span className="inline-flex flex-none items-center gap-1.5 rounded-full border border-amber-300/25 bg-amber-300/10 px-2.5 py-1.5 text-xs font-bold text-amber-100">
              <Star size={13} className="fill-amber-300 text-amber-300" aria-hidden="true" />
              {a.nota_anunciante.toLocaleString('pt-BR')}
            </span>
          )}
        </div>
        <p className="line-clamp-2 min-h-[2.75rem] text-[1.05rem] font-bold leading-snug tracking-[-0.015em] text-gray-100">
          {a.modelo_original ?? a.titulo ?? 'Modelo não informado'}
        </p>
        <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-gray-400">
          {a.ano && <span className="font-semibold text-gray-300">{a.ano}</span>}
          {a.km !== null && <span>{a.km.toLocaleString('pt-BR')} km</span>}
          {local && <span className="inline-flex items-center gap-1"><MapPin size={12} aria-hidden="true" /> {local}</span>}
        </div>

        {nivel && analise && (
          <button
            type="button"
            onClick={() => onGarimpar(a)}
            className={`mt-4 flex min-h-12 items-center gap-2.5 rounded-xl border px-3 py-2 text-left text-sm transition-colors ${nivel === 'quente' ? 'border-amber-300/25 bg-amber-300/10 text-amber-100 hover:bg-amber-300/15' : 'border-cyan-300/20 bg-cyan-300/[0.07] text-cyan-200 hover:bg-cyan-300/10'}`}
          >
            {nivel === 'quente' ? <Flame size={18} className="flex-none" aria-hidden="true" /> : <ThumbsUp size={18} className="flex-none" aria-hidden="true" />}
            <span className="min-w-0 flex-1">
              <span className="block font-bold">{nivel === 'quente' ? T.quente : T.boa}</span>
              <span className="block text-xs opacity-90">{analise.resumo}</span>
            </span>
            <ChevronRight size={16} className="flex-none" aria-hidden="true" />
          </button>
        )}
        {(fipe || outrosSinais.length > 0) && (
          <ul className="mt-3 flex flex-wrap gap-1.5">
            {fipe && <FipeDoCard f={fipe} />}
            {outrosSinais.map((s) => {
              const Icone = ICONE[s.tipo]
              return (
                <li key={s.tipo} className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs ${COR_SINAL[s.tipo]}`}>
                  <Icone size={14} className="flex-none" aria-hidden="true" />
                  <span className="min-w-0">
                    <span className="block font-semibold">{s.texto}</span>
                    {s.detalhe && <span className="block text-xs opacity-80">{s.detalhe}</span>}
                  </span>
                </li>
              )
            })}
          </ul>
        )}
        <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px]">
          {a.anunciante_profissional !== null && (
            <span className="rounded-md border border-teal-600/60 px-2 py-1 font-semibold text-teal-400">
              {a.anunciante_profissional ? 'Loja' : 'Particular'}
            </span>
          )}
          {a.em_destaque && (
            <span className="rounded-md border border-white/15 px-2 py-1 text-gray-400">{T.destaque}</span>
          )}
        </div>
        <div className="mt-auto flex flex-col gap-2 pt-4">
          <button
            type="button"
            onClick={() => onGarimpar(a)}
            className="vehicle-card__primary"
          >
            <Pickaxe size={16} aria-hidden="true" /> {T.garimpar} <ChevronRight size={15} aria-hidden="true" />
          </button>
          <a
            href={a.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/[0.03] px-4 text-sm font-semibold text-gray-300 transition-colors hover:border-cyan-300/30 hover:bg-cyan-300/[0.04] hover:text-cyan-200"
          >
            Acessar o anúncio <ArrowUpRight size={16} aria-hidden="true" />
          </a>
        </div>
      </div>
    </li>
  )
}

// memo: digitar na busca não redesenha os cards já na tela
export const CardCarro = memo(Card)
