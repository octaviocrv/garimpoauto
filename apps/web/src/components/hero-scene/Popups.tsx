import { useRef } from 'react'
import { CarShape } from './CarShape'
import { makeListing, type Listing, type SearchQuery } from './data'
import { usePlayOnce, useSceneEvent, useSpawner, type Spawned } from './hooks'
import { chance, pick, rand } from './random'

// Cards que surgem e somem em pontos diferentes: anúncios (carro, preço,
// distância) e conversas rápidas entre comprador e vendedor.

const SLOTS: [number, number][] = [
  [20, 60],
  [6, 590],
  [812, 594],
  [812, 680],
]

interface Popup {
  slot: number
  type: 'ad' | 'chat'
  listing: Listing
  reply: boolean
  life: number
}

const QUESTIONS = ['Ainda tá disponível?', 'Aceita troca?', 'Posso ver amanhã?', 'Tem laudo cautelar?']
const REPLIES = ['Tá sim! Pode vir ver.', 'Aceito, bora conversar.', 'Pode sim, te espero.', 'Tenho, te mando aqui.']

function PopupCard({ item, onDone }: { item: Spawned<Popup>; onDone: (id: number) => void }) {
  const ref = useRef<SVGGElement>(null)
  const replyRef = useRef<SVGGElement>(null)
  const [x, y] = SLOTS[item.slot]

  usePlayOnce(
    ref,
    () => ({
      keyframes: [
        { opacity: 0, transform: 'translateY(10px) scale(0.94)', easing: 'cubic-bezier(.2,.9,.3,1.2)' },
        { opacity: 1, transform: 'translateY(0px) scale(1)', offset: 0.08 },
        { opacity: 1, transform: 'translateY(0px) scale(1)', offset: 0.88 },
        { opacity: 0, transform: 'translateY(-8px) scale(0.98)' },
      ],
      options: { duration: item.life },
    }),
    () => onDone(item.id),
  )
  usePlayOnce(replyRef, () => ({
    keyframes: [
      { opacity: 0, transform: 'translateY(8px)' },
      { opacity: 1, transform: 'translateY(0px)' },
    ],
    options: { duration: 450, delay: rand(1100, 1800), easing: 'ease-out' },
  }))

  const question = QUESTIONS[item.listing.key % QUESTIONS.length]
  const answer = REPLIES[item.listing.key % REPLIES.length]

  return (
    <g transform={`translate(${x} ${y})`}>
      <g ref={ref} className="fill-box" opacity={0}>
        {item.type === 'ad' ? (
          <g>
            <rect width={168} height={60} rx={8} className="neon-teal holo-glass" />
            <g className="holo-glow">
              <g transform="translate(8 20) scale(0.13)">
                <CarShape kind={item.listing.kind} />
              </g>
            </g>
            <text x={58} y={20} fontSize={10.5} fontWeight={600} fill="#e2fdfd" className="glow-text" fontFamily="Inter, sans-serif">
              {item.listing.name}
            </text>
            <text x={58} y={36} fontSize={12} fontWeight={700} fill="#fde68a" className="glow-text-amber" fontFamily="Inter, sans-serif">
              {item.listing.price}
            </text>
            <circle cx={61} cy={47} r={2} fill="#f59e0b" />
            <text x={67} y={50} fontSize={8.5} fill="#99f6e4" fontFamily="Inter, sans-serif">
              {item.listing.city} · {item.listing.km} km
            </text>
          </g>
        ) : (
          <g>
            <path d="M0,8 Q0,0 8,0 H142 Q150,0 150,8 V24 Q150,32 142,32 H22 L12,40 L14,32 H8 Q0,32 0,24 Z" className="neon-teal" style={{ fill: 'rgba(3,17,19,0.85)' }} />
            <circle cx={14} cy={16} r={5} className="neon-teal" style={{ fill: 'rgba(0,240,255,0.25)' }} />
            <text x={26} y={20} fontSize={10.5} fill="#e2fdfd" className="glow-text" fontFamily="Inter, sans-serif">
              {question}
            </text>
            {item.reply && (
              <g transform="translate(26 40)">
                <g ref={replyRef} opacity={0}>
                  <path d="M0,8 Q0,0 8,0 H134 Q142,0 142,8 V22 Q142,30 134,30 H126 L130,38 L118,30 H8 Q0,30 0,22 Z" className="neon-amber" style={{ fill: 'rgba(20,12,2,0.85)' }} />
                  <text x={10} y={19} fontSize={10.5} fill="#fef3c7" className="glow-text-amber" fontFamily="Inter, sans-serif">
                    {answer}
                  </text>
                </g>
              </g>
            )}
          </g>
        )}
      </g>
    </g>
  )
}

function freeSlot(current: Popup[]) {
  const used = new Set(current.map((p) => p.slot))
  const free = SLOTS.map((_, i) => i).filter((i) => !used.has(i))
  return free.length ? pick(free) : null
}

export function Popups({ live }: { live: boolean }) {
  const popups = useSpawner<Popup>(
    live,
    (current) => {
      const slot = freeSlot(current)
      if (slot === null) return null
      const type = chance(0.65) ? 'ad' : 'chat'
      return { slot, type, listing: makeListing(), reply: chance(0.6), life: rand(type === 'ad' ? 4200 : 5200, 6800) }
    },
    [2600, 6400],
    2,
    1200,
  )

  // A busca "encontra" um anúncio de verdade na cena
  useSceneEvent<SearchQuery>('search', (query) => {
    const slot = freeSlot(popups.items)
    if (slot !== null) popups.push({ slot, type: 'ad', listing: query.listings[0], reply: false, life: rand(4200, 5600) })
  })

  return (
    <g id="anuncios">
      {popups.items.map((p) => (
        <PopupCard key={p.id} item={p} onDone={popups.remove} />
      ))}
    </g>
  )
}
