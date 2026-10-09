import { useRef, useState } from 'react'
import { CarShape } from './CarShape'
import { CAR_MODELS, makeListing, type Listing } from './data'
import { useRandomTicker, useSceneEvent } from './hooks'

// Vitrine: um carro em destaque na plataforma, com etiqueta de preço.
// De tempos em tempos (ou no clique) um feixe "escaneia" e troca por outro anúncio.

const CX = 150
const FLOOR = 112
const SCALE = 0.8

export function Showroom({ live }: { live: boolean }) {
  const [listing, setListing] = useState<Listing>(() => makeListing())
  const scanRef = useRef<SVGRectElement>(null)

  const swap = (next?: Listing) => {
    const target = next ?? makeListing(listing.kind)
    scanRef.current?.animate(
      [
        { transform: 'translateX(-10px)', opacity: 0 },
        { opacity: 0.9, offset: 0.15 },
        { opacity: 0.9, offset: 0.85 },
        { transform: 'translateX(300px)', opacity: 0 },
      ],
      { duration: 1100, easing: 'cubic-bezier(.4,0,.2,1)' },
    )
    window.setTimeout(() => setListing(target), 480)
  }

  useRandomTicker(live, () => swap(), [6500, 12000])
  // Ao clicar numa sugestão da busca, o carro escolhido vai pra vitrine
  useSceneEvent<Listing>('focus', (l) => swap(l))

  const m = CAR_MODELS[listing.kind]
  const carX = CX - (m.width * SCALE) / 2
  const carY = FLOOR - (m.base + m.r) * SCALE - 2

  return (
    <g id="vitrine" transform="translate(-30 388)">
      <g
        className="group pointer-events-auto cursor-pointer"
        onClick={() => swap()}
      >
        {/* Área de clique generosa */}
        <rect x={0} y={0} width={300} height={190} fill="transparent" />

        <ellipse cx={CX} cy={FLOOR + 2} rx={150} ry={13} className="neon-teal transition-opacity duration-500 group-hover:opacity-100" opacity={0.75} style={{ fill: 'rgba(0,240,255,0.05)' }} />
        <ellipse cx={CX} cy={FLOOR + 2} rx={112} ry={8} className="neon-teal-dim" />

        <g className="holo-car holo-glow transition-transform duration-500 ease-out group-hover:-translate-y-1.5">
          <g key={listing.key} className="hs-fade-in" transform={`translate(${carX} ${carY}) scale(${SCALE})`}>
            <CarShape kind={listing.kind} />
          </g>
        </g>

        <rect ref={scanRef} x={0} y={-6} width={3} height={FLOOR + 14} rx={1.5} fill="#00f0ff" opacity={0} className="neon-teal" />

        {/* Etiqueta de preço, presa na frente da plataforma */}
        <g key={`tag-${listing.key}`} className="hs-fade-in" transform="translate(70 132)">
          <path
            d="M0,20 Q0,12 8,12 H54 L64,0 L74,12 H138 Q146,12 146,20 V48 Q146,56 138,56 H8 Q0,56 0,48 Z"
            className="neon-amber"
            style={{ fill: 'rgba(20,12,2,0.55)' }}
          />
          <text x={16} y={32} fontSize={13} fontWeight={700} fill="#fde68a" className="glow-text-amber" fontFamily="Inter, sans-serif">
            {listing.price}
          </text>
          <text x={16} y={48} fontSize={9} fill="#99f6e4" fontFamily="Inter, sans-serif">
            {listing.city} · {listing.km} km
          </text>
        </g>
      </g>
    </g>
  )
}
