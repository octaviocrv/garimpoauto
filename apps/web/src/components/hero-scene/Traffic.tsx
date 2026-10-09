import { useEffect, useRef, useState } from 'react'
import { CarShape } from './CarShape'
import { CAR_KINDS, CAR_MODELS, type CarKind } from './data'
import { usePlayOnce, useSpawner, type Spawned } from './hooks'
import { chance, pick, rand } from './random'

// Carros holográficos deslizando pelo piso do galpão, em duas faixas com escala,
// velocidade e sentido próprios. Os modelos variam e nunca repetem em sequência
// na mesma faixa. Passam por trás do Hiro e reaparecem do outro lado.

interface Lane {
  y: number
  scale: number
  speed: number
  dir: 1 | -1
  gap: [number, number]
}

const LANES: Lane[] = [
  { y: 880, scale: 0.3, speed: 58, dir: -1, gap: [5200, 12500] },
  { y: 975, scale: 0.42, speed: 86, dir: 1, gap: [4200, 10500] },
]

// Saem pela direita da tela e somem no degradê da esquerda
const START = 1080
const END = -560

interface Car {
  kind: CarKind
  speed: number
  dy: number
  progress?: number
}

function MovingCar({ lane, item, onDone }: { lane: Lane; item: Spawned<Car>; onDone: (id: number) => void }) {
  const ref = useRef<SVGGElement>(null)
  const m = CAR_MODELS[item.kind]
  const w = m.width * lane.scale
  const from = lane.dir === -1 ? START : END - w
  const to = lane.dir === -1 ? END - w : START
  const duration = (Math.abs(to - from) / item.speed) * 1000

  usePlayOnce(
    ref,
    () => ({
      keyframes: [{ transform: `translateX(${from}px)` }, { transform: `translateX(${to}px)` }],
      options: { duration, easing: 'linear' },
      progress: item.progress,
    }),
    () => onDone(item.id),
  )

  const top = lane.y + item.dy - (m.base + m.r) * lane.scale
  const spin = (2 * Math.PI * m.r * lane.scale) / item.speed
  const flip = lane.dir === 1 ? `translate(${w} 0) scale(${-lane.scale} ${lane.scale})` : `scale(${lane.scale})`

  return (
    <g transform={`translate(0 ${top})`}>
      <g ref={ref} className="holo-glow" style={{ transform: `translateX(${from}px)` }}>
        <g transform={flip}>
          <CarShape kind={item.kind} spin={spin} lights />
        </g>
      </g>
    </g>
  )
}

function newCar(lane: Lane, last: { current: CarKind | null }, progress?: number): Car {
  let kind = pick(CAR_KINDS)
  while (kind === last.current) kind = pick(CAR_KINDS)
  last.current = kind
  return { kind, speed: lane.speed * rand(0.9, 1.1), dy: rand(-3, 3), progress }
}

function LaneTraffic({ lane, live, seed }: { lane: Lane; live: boolean; seed: boolean }) {
  const last = useRef<CarKind | null>(null)
  const [first] = useState(() => rand(lane.gap[0] * 0.5, lane.gap[1]))
  const { items, push, remove } = useSpawner<Car>(live, () => newCar(lane, last), lane.gap, 4, first)

  // Já começa com um carro no meio do caminho, pra cena não "nascer" vazia
  const seeded = useRef(false)
  useEffect(() => {
    if (!seed || !live || seeded.current) return
    seeded.current = true
    push(newCar(lane, last, rand(0.15, 0.6)))
  }, [seed, live, lane, push])

  return (
    <g>
      {items.map((c) => (
        <MovingCar key={c.id} lane={lane} item={c} onDone={remove} />
      ))}
    </g>
  )
}

// Versão parada (prefers-reduced-motion): dois carros estacionados na pista
function ParkedCars() {
  const parked: { lane: Lane; kind: CarKind; x: number }[] = [
    { lane: LANES[0], kind: 'suv', x: 20 },
    { lane: LANES[1], kind: 'hatch', x: 760 },
  ]
  return (
    <g className="holo-glow">
      {parked.map(({ lane, kind, x }) => {
        const m = CAR_MODELS[kind]
        return (
          <g key={kind} transform={`translate(${x} ${lane.y - (m.base + m.r) * lane.scale}) scale(${lane.scale})`}>
            <CarShape kind={kind} />
          </g>
        )
      })}
    </g>
  )
}

export function Traffic({ live, still }: { live: boolean; still: boolean }) {
  const [seeds] = useState(() => LANES.map(() => chance(0.7)))
  return (
    <g id="estrada">
      <defs>
        <linearGradient id="hs-beam" x1="1" x2="0" y1="0" y2="0">
          <stop offset="0" stopColor="#00f0ff" stopOpacity={0.35} />
          <stop offset="1" stopColor="#00f0ff" stopOpacity={0} />
        </linearGradient>
      </defs>

      {/* Linhas de luz no piso */}
      <path d="M690,792 H1000 M750,812 H1000" className="neon-teal holo-soft" />

      <g className="holo-car">
        {still ? (
          <ParkedCars />
        ) : (
          LANES.map((lane, i) => <LaneTraffic key={i} lane={lane} live={live} seed={seeds[i]} />)
        )}
      </g>
    </g>
  )
}
