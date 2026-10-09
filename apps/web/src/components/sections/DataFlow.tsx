import { useState, type CSSProperties } from 'react'
import { CarShape } from '../hero-scene/CarShape'
import { makeListing } from '../hero-scene/data'
import { useMediaQuery } from './hooks'

// Diagrama da seção "Agora", contando o mesmo que o texto: uma fonte ligada de
// ponta a ponta, as outras duas em espera, o "organiza" no meio, o resultado
// simples no fim e os filtros chegando depois. Os pontos de luz correm pelas
// trilhas com stroke-dasharray (pathLength=100), sincronizados só por CSS:
// - Fonte 1: 3 pontos num ciclo de 3,6s (chega um a cada 1,2s, a partir de 2,47s)
// - Saída: 1 ponto a cada 1,2s, a partir de 2,47s
// - Resultado: troca de anúncio a cada 3,6s, quando o ponto de saída chega (3,02s)
// Os tempos ficam no App.css (.flow-dot, .flow-dot-out, .flow-hex-hit, .flow-result-hit).

type Pt = [number, number]

interface Layout {
  viewBox: string
  /** Canto superior esquerdo de cada fonte */
  sources: Pt[]
  source: { w: number; h: number }
  /** Ponto onde cada trilha sai da fonte */
  starts: Pt[]
  tracks: [string, string, string]
  hex: { cx: number; cy: number; r: number; pointy: boolean }
  label: { x: number; y: number; anchor: 'middle' | 'start' }
  out: string
  result: Pt
  toFilter: string
  filter: Pt
}

const WIDE: Layout = {
  viewBox: '-6 28 572 336',
  sources: [[0, 40], [0, 174], [0, 308]],
  source: { w: 132, h: 52 },
  starts: [[132, 66], [132, 200], [132, 334]],
  tracks: [
    'M132,66 H176 L206,96 V151 L236,181 H285',
    'M132,200 H274',
    'M132,334 H176 L206,304 V249 L236,219 H285',
  ],
  hex: { cx: 318, cy: 200, r: 44, pointy: false },
  label: { x: 318, y: 278, anchor: 'middle' },
  out: 'M362,200 H404',
  result: [404, 128],
  toFilter: 'M479,272 V306',
  filter: [404, 306],
}

const TALL: Layout = {
  viewBox: '-4 -6 348 516',
  sources: [[0, 0], [120, 0], [240, 0]],
  source: { w: 100, h: 46 },
  starts: [[50, 46], [170, 46], [290, 46]],
  tracks: [
    'M50,46 V90 L84,124 H124 L152.7,152.7 V180',
    'M170,46 V170',
    'M290,46 V90 L256,124 H216 L187.3,152.7 V180',
  ],
  hex: { cx: 170, cy: 210, r: 40, pointy: true },
  label: { x: 226, y: 214, anchor: 'start' },
  out: 'M170,250 V290',
  result: [95, 290],
  toFilter: 'M170,434 V462',
  filter: [95, 462],
}

function hexPoints({ cx, cy, r, pointy }: Layout['hex']) {
  return Array.from({ length: 6 }, (_, i) => {
    const a = ((i * 60 + (pointy ? -90 : 0)) * Math.PI) / 180
    return `${(cx + r * Math.cos(a)).toFixed(1)},${(cy + r * Math.sin(a)).toFixed(1)}`
  }).join(' ')
}

const delay = (s: number) => ({ animationDelay: `${s}s` }) as CSSProperties

export function DataFlow() {
  const tall = useMediaQuery('(max-width: 639px)')
  const L = tall ? TALL : WIDE
  const [listing, setListing] = useState(() => makeListing())
  const next = () => setListing((prev) => makeListing(prev.kind))
  const hex = hexPoints(L.hex)
  const { cx, cy, r } = L.hex

  return (
    <svg viewBox={L.viewBox} className={`flow-svg${tall ? ' is-tall' : ''}`} focusable="false">
      {/* Trilhas */}
      <path d={L.tracks[0]} className="flow-track" />
      <path d={L.tracks[1]} className="flow-track is-off" />
      <path d={L.tracks[2]} className="flow-track is-off" />
      <path d={L.out} className="flow-track" />
      <path d={L.toFilter} className="flow-track is-off" />
      {L.starts.map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r={2.6} className={`flow-joint${i ? ' is-off' : ''}`} />
      ))}

      {/* Pontos de luz: a fonte ligada manda anúncios; as outras só "testam o sinal" */}
      {[0, 1.2, 2.4].map((s) => (
        <g key={s}>
          <path d={L.tracks[0]} pathLength={100} className="flow-tail" style={delay(s)} />
          <path d={L.tracks[0]} pathLength={100} className="flow-dot" style={delay(s)} />
        </g>
      ))}
      <path d={L.tracks[1]} pathLength={100} className="flow-ping" style={delay(1.4)} />
      <path d={L.tracks[2]} pathLength={100} className="flow-ping" style={delay(4)} />
      <path d={L.out} pathLength={100} className="flow-dot flow-dot-out" />

      {/* Fontes */}
      {L.sources.map(([x, y], i) => (
        <g key={i} transform={`translate(${x} ${y})`} className={`flow-src${i ? ' is-off' : ''}`}>
          <rect width={L.source.w} height={L.source.h} rx={6} className="flow-node" />
          <text x={12} y={21} className="flow-label">
            Fonte {i + 1}
          </text>
          <circle cx={15} cy={L.source.h - 14} r={2.5} className="flow-led" />
          <text x={23} y={L.source.h - 10.5} className="flow-status">
            {i ? 'em breve' : 'ligada'}
          </text>
        </g>
      ))}

      {/* Organiza: hexágono com anéis girando */}
      <g className="flow-core">
        <circle cx={cx} cy={cy} r={r + 12} className="flow-ring" />
        <circle cx={cx} cy={cy} r={r + 20} className="flow-ring flow-ring-arcs" pathLength={100} />
        <polygon points={hex} className="flow-node flow-hex" />
        <polygon points={hex} className="flow-hex-hit" />
        <text x={cx} y={cy + 10} textAnchor="middle" className="flow-kanji font-jp">
          整
        </text>
        <text x={L.label.x} y={L.label.y} textAnchor={L.label.anchor} className="flow-kicker">
          ORGANIZA
        </text>
      </g>

      {/* Resultado simples: um anúncio por vez, trocando quando o ponto chega */}
      <g transform={`translate(${L.result[0]} ${L.result[1]})`}>
        <rect width={150} height={144} rx={8} className="flow-node" />
        <rect width={150} height={144} rx={8} className="flow-result-hit" onAnimationStart={next} onAnimationIteration={next} />
        <text x={12} y={19} className="flow-kicker">
          RESULTADO
        </text>
        <circle cx={138} cy={15} r={2.5} className="flow-led" />
        <path d="M12,28 H138" className="flow-rule" />
        <g key={listing.key} className="flow-swap">
          <g className="holo-glow">
            <g transform="translate(14 38) scale(0.34)">
              <CarShape kind={listing.kind} />
            </g>
          </g>
          <text x={12} y={94} className="flow-name">
            {listing.name}
          </text>
          <text x={12} y={114} className="flow-price">
            {listing.price}
          </text>
          <text x={12} y={131} className="flow-meta">
            {listing.city} · {listing.km} km
          </text>
        </g>
      </g>

      {/* Filtros: próxima etapa */}
      <g transform={`translate(${L.filter[0]} ${L.filter[1]})`} className="flow-src is-off">
        <rect width={150} height={40} rx={6} className="flow-node" />
        <text x={12} y={25} className="flow-label">
          Filtros
        </text>
        <text x={138} y={24.5} textAnchor="end" className="flow-status">
          em breve
        </text>
      </g>
    </svg>
  )
}
