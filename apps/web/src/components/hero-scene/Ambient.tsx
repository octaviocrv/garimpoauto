import { useRef, useState } from 'react'
import { HIRO } from './data'
import { useFlicker, usePlayOnce, useRandomTicker, useSceneEvent, useSpawner, type Spawned } from './hooks'
import { chance, rand } from './random'

// Peças menores da cena: brilho dos painéis, kanji em neon, gráfico de preço e
// partículas do celular.

export function KanjiSigns({ live }: { live: boolean }) {
  const ref = useRef<SVGGElement>(null)
  useFlicker(ref, live, [4500, 13000])
  return (
    <g id="kanji" ref={ref} className="font-jp">
      <g data-flicker="" className="holo-text">
        <text x={104} y={198} fontSize={54} fontWeight={500} className="neon-teal" style={{ fill: 'rgba(0,240,255,0.2)' }}>
          ガリンボ
        </text>
      </g>
      <path d="M104,212 H160" strokeWidth={2.5} className="neon-amber holo-soft" />
    </g>
  )
}

// Halo de luz atrás de cada grupo de hologramas, "respirando" em ritmos diferentes
const BLOOMS = [
  { cx: 782, cy: 335, rx: 150, ry: 170 }, // mapa
  { cx: 170, cy: 250, rx: 210, ry: 80 }, // busca
  { cx: 120, cy: 480, rx: 200, ry: 70 }, // vitrine
  { cx: 500, cy: 112, rx: 190, ry: 64 }, // portal
  { cx: 928, cy: 517, rx: 110, ry: 80 }, // gráfico
]

export function HoloBloom({ live }: { live: boolean }) {
  const [levels, setLevels] = useState(() => BLOOMS.map(() => 0.85))
  useRandomTicker(live, () => {
    setLevels((ls) => ls.map((l) => (chance(0.5) ? Math.min(1, Math.max(0.55, l + rand(-0.22, 0.22))) : l)))
  }, [1600, 4200])
  return (
    <g id="brilho">
      {BLOOMS.map((b, i) => (
        <ellipse key={i} {...b} fill="url(#hs-bloom)" style={{ opacity: levels[i], transition: 'opacity 2.6s ease-in-out' }} />
      ))}
    </g>
  )
}

const BARS = 8
const BAR_H = 44

/** Barras de preço médio que se reajustam aos poucos (passeio aleatório, sem ciclo). */
export function MarketChart({ live }: { live: boolean }) {
  const [values, setValues] = useState(() => Array.from({ length: BARS }, (_, i) => 0.35 + i * 0.07))
  useRandomTicker(live, () => {
    setValues((vs) => vs.map((v) => (chance(0.6) ? Math.min(1, Math.max(0.18, v + rand(-0.22, 0.22))) : v)))
  }, [2600, 7200])

  return (
    <g id="grafico" transform="translate(860 470)">
      <rect width={136} height={94} rx={8} className="neon-teal holo-glass" />
      <text x={10} y={16} fontSize={7.5} letterSpacing={1.4} fill="#a5f9fc" className="glow-text" fontFamily="Inter, sans-serif" fontWeight={600}>
        PREÇO MÉDIO · BH
      </text>
      <path d={`M10,${80 - BAR_H * 0.62} H126`} className="neon-amber" strokeDasharray="3 3" opacity={0.7} />
      <text x={126} y={80 - BAR_H * 0.62 - 3} fontSize={6.5} textAnchor="end" fill="#fbbf24" fontFamily="Inter, sans-serif">
        FIPE
      </text>
      {values.map((v, i) => (
        <rect
          key={i}
          x={12 + i * 14}
          y={80 - BAR_H}
          width={8}
          height={BAR_H}
          rx={1.5}
          className="hs-bar neon-teal"
          style={{ fill: 'rgba(0,240,255,0.16)', transform: `scaleY(${v})`, transitionDelay: `${i * 55}ms` }}
        />
      ))}
      <path d="M8,82 H128" className="neon-teal-dim" />
    </g>
  )
}

interface Spark {
  x: number
  y: number
  dx: number
  dy: number
  r: number
  life: number
  amber: boolean
}

const PHONE = HIRO.phone

function newSpark(): Spark {
  return {
    x: PHONE[0] + rand(-8, 8),
    y: PHONE[1] + rand(-6, 6),
    dx: rand(-70, 20),
    dy: rand(-110, -30),
    r: rand(0.8, 2.2),
    life: rand(1300, 2900),
    amber: chance(0.15),
  }
}

function SparkDot({ item, onDone }: { item: Spawned<Spark>; onDone: (id: number) => void }) {
  const ref = useRef<SVGGElement>(null)
  usePlayOnce(
    ref,
    () => ({
      keyframes: [
        { opacity: 0, transform: 'translate(0px, 0px)' },
        { opacity: 1, offset: 0.15 },
        { transform: `translate(${item.dx * 0.4 + rand(-8, 8)}px, ${item.dy * 0.55}px)`, offset: 0.5 },
        { opacity: 0, transform: `translate(${item.dx}px, ${item.dy}px)` },
      ],
      options: { duration: item.life, easing: 'cubic-bezier(.2,.6,.4,1)' },
    }),
    () => onDone(item.id),
  )
  return (
    <g ref={ref} opacity={0}>
      <circle cx={item.x} cy={item.y} r={item.r * 4.5} fill={`url(#hs-spark-${item.amber ? 'amber' : 'teal'})`} />
      <circle cx={item.x} cy={item.y} r={item.r} fill={item.amber ? '#fde68a' : '#a5f9fc'} />
    </g>
  )
}

export function PhoneSparks({ live }: { live: boolean }) {
  const sparks = useSpawner<Spark>(live, newSpark, [110, 520], 22, 300)
  // Rajada quando a busca encontra resultados
  useSceneEvent('search', () => {
    for (let i = 0; i < 9; i++) sparks.push(newSpark())
  })
  return (
    <g id="particulas">
      {sparks.items.map((s) => (
        <SparkDot key={s.id} item={s} onDone={sparks.remove} />
      ))}
    </g>
  )
}
