import { useRef } from 'react'
import { BH, BRAZIL_DOTS, BRAZIL_PATH, CITIES } from './data'
import { usePlayOnce, useSceneEvent, useSpawner, type Spawned } from './hooks'
import { chance, pick, rand } from './random'

// Painel do mapa: Brasil pontilhado, pins que surgem em lugares diferentes,
// rotas até BH ("você") e pontos que acendem como se houvesse movimento.

// Pino já no tamanho final (sem scale), pra o brilho não encolher junto
const PIN = 'M0,0 C-1.5,-3 -4,-5 -4,-7.5 A4,4 0 1 1 4,-7.5 C4,-5 1.5,-3 0,0 Z'
const [BHX, BHY] = BH

interface Pin {
  x: number
  y: number
  amber: boolean
  life: number
  route: boolean
  progress?: number
}

function MapPin({ item, onDone }: { item: Spawned<Pin>; onDone: (id: number) => void }) {
  const pinRef = useRef<SVGGElement>(null)
  const ringRef = useRef<SVGCircleElement>(null)
  const routeRef = useRef<SVGPathElement>(null)

  usePlayOnce(
    pinRef,
    () => ({
      keyframes: [
        { opacity: 0, transform: 'translateY(-9px)', easing: 'cubic-bezier(.3,1.7,.5,1)' },
        { opacity: 1, transform: 'translateY(0px)', offset: 0.09 },
        { opacity: 1, transform: 'translateY(0px)', offset: 0.86 },
        { opacity: 0, transform: 'translateY(0px)' },
      ],
      options: { duration: item.life },
      progress: item.progress,
    }),
    () => onDone(item.id),
  )
  usePlayOnce(ringRef, () => ({
    keyframes: [
      { opacity: 0.9, transform: 'scale(0.2)' },
      { opacity: 0, transform: 'scale(2.8)' },
    ],
    options: { duration: 1500, easing: 'ease-out', delay: 120 },
    progress: item.progress ? 1 : 0,
  }))
  usePlayOnce(routeRef, () => ({
    keyframes: [
      { strokeDashoffset: 1, opacity: 0.9 },
      { strokeDashoffset: 0, opacity: 0.9, offset: 0.45 },
      { strokeDashoffset: 0, opacity: 0 },
    ],
    options: { duration: Math.min(item.life, 3200), easing: 'ease-in-out', delay: 300 },
  }))

  const midX = (item.x + BHX) / 2
  const midY = Math.min(item.y, BHY) - Math.abs(item.x - BHX) * 0.35 - 8
  const color = item.amber ? 'neon-amber' : 'neon-teal'

  return (
    <g>
      {item.route && (
        <path
          ref={routeRef}
          d={`M${item.x},${item.y} Q${midX},${midY} ${BHX},${BHY}`}
          pathLength={1}
          strokeDasharray="1"
          className={color}
          opacity={0}
        />
      )}
      <g transform={`translate(${item.x} ${item.y})`}>
        <circle ref={ringRef} r={6} className={`${color} fill-box`} opacity={0} />
        <g ref={pinRef} opacity={0}>
          <path d={PIN} className={color} style={{ fill: item.amber ? 'rgba(245,158,11,0.35)' : 'rgba(0,240,255,0.3)' }} />
        </g>
      </g>
    </g>
  )
}

interface Twinkle {
  x: number
  y: number
  life: number
}

function DotTwinkle({ item, onDone }: { item: Spawned<Twinkle>; onDone: (id: number) => void }) {
  const ref = useRef<SVGGElement>(null)
  usePlayOnce(
    ref,
    () => ({ keyframes: [{ opacity: 0 }, { opacity: 1, offset: 0.35 }, { opacity: 0 }], options: { duration: item.life } }),
    () => onDone(item.id),
  )
  return (
    <g ref={ref} opacity={0}>
      <circle cx={item.x} cy={item.y} r={5} fill="url(#hs-spark-teal)" />
      <circle cx={item.x} cy={item.y} r={1.4} fill="#a5f9fc" />
    </g>
  )
}

function Radar({ item, onDone }: { item: Spawned<{ delay: number }>; onDone: (id: number) => void }) {
  const ref = useRef<SVGCircleElement>(null)
  usePlayOnce(
    ref,
    () => ({
      keyframes: [
        { opacity: 0.8, transform: 'scale(0.3)' },
        { opacity: 0, transform: 'scale(4)' },
      ],
      options: { duration: 2200, easing: 'cubic-bezier(.2,.7,.3,1)', delay: item.delay },
    }),
    () => onDone(item.id),
  )
  return <circle ref={ref} cx={BHX} cy={BHY} r={6} className="neon-teal fill-box" opacity={0} />
}

function localPin(): Pin {
  return {
    x: BHX + rand(-11, 11),
    y: BHY + rand(-10, 10),
    amber: chance(0.3),
    life: rand(3200, 6000),
    route: chance(0.45),
  }
}

function farPin(): Pin {
  const [x, y] = pick(CITIES)
  return { x: x + rand(-2, 2), y: y + rand(-2, 2), amber: chance(0.2), life: rand(3500, 7000), route: chance(0.25) }
}

// Pins fixos para quem prefere menos movimento
const STILL_PINS = [CITIES[5], CITIES[9], CITIES[10], [BHX + 8, BHY - 6], [BHX - 7, BHY + 5]]

export function MapPanel({ live, still }: { live: boolean; still: boolean }) {
  const pins = useSpawner<Pin>(live, () => (chance(0.55) ? localPin() : farPin()), [700, 2600], 9, 400)
  const twinkles = useSpawner<Twinkle>(
    live,
    () => {
      const [x, y] = pick(BRAZIL_DOTS)
      return { x, y, life: rand(1100, 2600) }
    },
    [90, 380],
    14,
    0,
  )
  const radar = useSpawner<{ delay: number }>(live, () => ({ delay: 0 }), [2600, 6000], 3, 800)

  // Quando a barra de busca "encontra" algo, a região de BH reage
  useSceneEvent('search', () => {
    radar.push({ delay: 0 })
    radar.push({ delay: 380 })
    for (let i = 0; i < 3; i++) pins.push({ ...localPin(), route: i === 0, life: rand(3800, 5200) })
  })
  useSceneEvent('focus', () => radar.push({ delay: 0 }))

  return (
    <g id="mapa" transform="translate(700 226)">
      <rect width={164} height={218} rx={10} className="neon-teal holo-glass" />
      <text x={12} y={20} fontSize={8} letterSpacing={2} fill="#a5f9fc" className="glow-text" fontFamily="Inter, sans-serif" fontWeight={600}>
        BRASIL
      </text>
      <text x={152} y={20} fontSize={8} textAnchor="end" fill="#fde68a" className="glow-text-amber" fontFamily="Inter, sans-serif" fontWeight={600}>
        perto de você
      </text>
      <path d="M12,28 H152" className="neon-teal-dim" />

      <g transform="translate(4 36)">
        <g fill="#5ffbf1" opacity={0.6} className="glow-text">
          {BRAZIL_DOTS.map(([x, y], i) => (
            <circle key={i} cx={x} cy={y} r={1.1} />
          ))}
        </g>
        <path d={BRAZIL_PATH} className="neon-teal-dim" strokeDasharray="2 3" />

        {twinkles.items.map((t) => (
          <DotTwinkle key={t.id} item={t} onDone={twinkles.remove} />
        ))}
        {radar.items.map((r) => (
          <Radar key={r.id} item={r} onDone={radar.remove} />
        ))}
        {still &&
          STILL_PINS.map(([x, y], i) => (
            <path key={i} d={PIN} transform={`translate(${x} ${y})`} className="neon-teal" style={{ fill: 'rgba(0,240,255,0.3)' }} />
          ))}
        {pins.items.map((p) => (
          <MapPin key={p.id} item={p} onDone={pins.remove} />
        ))}

        {/* Você está aqui: BH */}
        <g transform={`translate(${BHX} ${BHY})`}>
          <circle r={2.8} fill="#fde68a" className="neon-amber" />
          <text x={6} y={-5} fontSize={7.5} fill="#fbbf24" fontFamily="Inter, sans-serif" fontWeight={600}>
            você
          </text>
        </g>
      </g>

      <text x={12} y={206} fontSize={7.5} fill="#5eead4" opacity={0.75} fontFamily="Inter, sans-serif">
        BH e região · anúncios ao vivo
      </text>
    </g>
  )
}
