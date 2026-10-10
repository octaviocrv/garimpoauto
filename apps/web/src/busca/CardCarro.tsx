import { ExternalLink, Star } from 'lucide-react'
import type { Anuncio } from '../types'

const preco = (v: number) => `R$ ${v.toLocaleString('pt-BR')}`

export function CardCarro({ a }: { a: Anuncio }) {
  const foto = a.imagens[0]
  const local = [a.cidade, a.estado].filter(Boolean).join(', ')
  const detalhes = [a.ano, a.km !== null ? `${a.km.toLocaleString('pt-BR')} km` : null, local].filter(Boolean)
  return (
    <li className="flex flex-col overflow-hidden rounded-lg border border-white/10 bg-[#0a0a0a]">
      <div className="aspect-[4/3] w-full bg-black/60">
        {foto && (
          <img src={foto} alt="" loading="lazy" referrerPolicy="no-referrer" className="h-full w-full object-cover" />
        )}
      </div>
      <div className="flex flex-1 flex-col gap-2 p-4">
        <p className={`text-xl font-bold ${a.preco === null ? 'text-gray-500' : 'text-white'}`}>
          {a.preco === null ? 'Preço não informado' : preco(a.preco)}
        </p>
        <p className="text-base font-medium leading-snug text-gray-200">{a.modelo_original ?? a.titulo ?? 'Modelo não informado'}</p>
        <p className="text-sm text-gray-400">{detalhes.join(' · ')}</p>
        <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
          {a.anunciante_profissional !== null && (
            <span className="rounded-md border border-teal-600/60 px-2 py-1 font-semibold text-teal-400">
              {a.anunciante_profissional ? 'Loja' : 'Particular'}
            </span>
          )}
          {a.nota_anunciante !== null && (
            <span className="inline-flex items-center gap-1 text-yellow-200">
              <Star size={13} aria-hidden="true" /> Nota {a.nota_anunciante.toLocaleString('pt-BR')}
            </span>
          )}
        </div>
        <a
          href={a.url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-auto inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-gray-600 bg-black/40 px-4 pt-0 text-sm text-gray-300 transition-all hover:border-gray-400 hover:text-white"
        >
          Ver anúncio original <ExternalLink size={14} aria-hidden="true" />
        </a>
      </div>
    </li>
  )
}
