import { useRef } from 'react'
import { useFlicker, usePlayOnce, useSpawner, type Spawned } from './hooks'
import { chance, rand } from './random'

// Camada mais distante: portal (torii) emoldurando a cabeça do Hiro, pagode ao
// fundo em linhas finas e poeira de luz flutuando no galpão.

// Torii: postes ao lado da cabeça (o cabelo ocupa x≈373–631)
const TORII_BEAMS =
  'M268,56 Q500,80 732,56 M276,72 Q500,94 724,72 M268,56 L276,72 M732,56 L724,72 ' +
  'M300,90 H700 M300,100 H700 M318,150 H682 M318,162 H682'
const TORII_POSTS = 'M340,100 L332,470 M358,100 L356,470 M642,100 L644,470 M660,100 L668,470'

// Pagode de 3 andares, só contorno
function pagoda(cx: number, base: number) {
  const tiers = [
    { w: 64, y: base - 22, h: 14 },
    { w: 50, y: base - 58, h: 12 },
    { w: 38, y: base - 90, h: 11 },
  ]
  const roofs = tiers
    .map(({ w, y, h }) => `M${cx - w},${y} Q${cx - w * 0.55},${y - 3} ${cx - w * 0.35},${y - h} H${cx + w * 0.35} Q${cx + w * 0.55},${y - 3} ${cx + w},${y}`)
    .join(' ')
  const bodies = `M${cx - 44},${base} V${base - 22} M${cx + 44},${base} V${base - 22} M${cx - 34},${base - 22} V${base - 58} M${cx + 34},${base - 22} V${base - 58} M${cx - 24},${base - 58} V${base - 90} M${cx + 24},${base - 58} V${base - 90} M${cx - 70},${base} H${cx + 70}`
  const spire = `M${cx},${base - 101} V${base - 160} M${cx - 5},${base - 128} H${cx + 5} M${cx - 5},${base - 138} H${cx + 5}`
  return `${roofs} ${bodies} ${spire}`
}

const PAGODA = pagoda(930, 196)

interface Dust {
  x: number
  y: number
  dx: number
  dy: number
  r: number
  life: number
  amber: boolean
}

function DustMote({ item, onDone }: { item: Spawned<Dust>; onDone: (id: number) => void }) {
  const ref = useRef<SVGGElement>(null)
  usePlayOnce(
    ref,
    () => ({
      keyframes: [
        { opacity: 0, transform: 'translate(0px, 0px)' },
        { opacity: 0.9, offset: 0.25 },
        { opacity: 0.6, transform: `translate(${item.dx * 0.6}px, ${item.dy * 0.5}px)`, offset: 0.6 },
        { opacity: 0, transform: `translate(${item.dx}px, ${item.dy}px)` },
      ],
      options: { duration: item.life, easing: 'ease-in-out' },
    }),
    () => onDone(item.id),
  )
  return (
    <g ref={ref} opacity={0}>
      <circle cx={item.x} cy={item.y} r={item.r * 4} fill={`url(#hs-spark-${item.amber ? 'amber' : 'teal'})`} />
      <circle cx={item.x} cy={item.y} r={item.r} fill={item.amber ? '#fde68a' : '#a5f9fc'} />
    </g>
  )
}

export function Shrine({ live }: { live: boolean }) {
  const ref = useRef<SVGGElement>(null)
  useFlicker(ref, live, [5000, 14000])

  const dust = useSpawner<Dust>(
    live,
    () => ({
      x: rand(-150, 1000),
      y: rand(30, 950),
      dx: rand(-40, 30),
      dy: rand(-90, -30),
      r: rand(0.8, 1.8),
      life: rand(5000, 9500),
      amber: chance(0.18),
    }),
    [350, 1300],
    16,
    200,
  )

  return (
    <g id="templo">
      <g ref={ref} className="holo-soft">
        <g data-flicker="">
          <path d={TORII_BEAMS} className="neon-teal" strokeWidth={1.4} />
          <path d={TORII_POSTS} className="neon-teal" strokeWidth={1.2} />
          <rect x={476} y={104} width={48} height={40} rx={3} className="neon-teal" style={{ fill: 'rgba(0,240,255,0.12)' }} />
          <text x={500} y={133} textAnchor="middle" fontSize={26} fontWeight={700} className="font-jp glow-text" fill="#a5f9fc">
            車
          </text>
        </g>
        <g data-flicker="">
          <path d={PAGODA} className="neon-teal" />
        </g>
      </g>

      <g id="poeira">
        {dust.items.map((item) => (
          <DustMote key={item.id} item={item} onDone={dust.remove} />
        ))}
      </g>
    </g>
  )
}
