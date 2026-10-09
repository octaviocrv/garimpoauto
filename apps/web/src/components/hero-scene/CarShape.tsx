import type { CSSProperties } from 'react'
import { CAR_MODELS, type CarKind } from './data'

interface Props {
  kind: CarKind
  /** Duração (s) de uma volta da roda. Sem valor, as rodas ficam paradas. */
  spin?: number
  /** Farol (feixe) e lanterna. O feixe usa o gradiente #hs-beam definido na camada da estrada. */
  lights?: boolean
}

export function CarShape({ kind, spin, lights = false }: Props) {
  const m = CAR_MODELS[kind]
  const [hx, hy] = m.head
  const [tx, ty] = m.tail
  const wheelStyle = spin ? ({ '--spin': `${spin}s` } as CSSProperties) : undefined

  return (
    <g>
      {lights && <path d={`M${hx},${hy} L${hx - 110},${hy - 16} L${hx - 110},${hy + 18} Z`} fill="url(#hs-beam)" />}
      {/* Traço sem filtro: quem usa o carro aplica .holo-glow num grupo não escalado */}
      <g className="neon-line">
        <path d={m.body} style={{ fill: 'rgba(0,240,255,0.05)' }} />
        <path d={m.windows} opacity={0.7} />
        <path d={m.details} opacity={0.55} />
        {m.wheels.map((cx) => (
          <g key={cx} className={spin ? 'hs-spin' : undefined} style={wheelStyle}>
            <circle cx={cx} cy={m.base} r={m.r} style={{ fill: 'rgba(0,0,0,0.6)' }} />
            <circle cx={cx} cy={m.base} r={m.r * 0.45} opacity={0.6} />
            <path
              d={`M${cx - m.r * 0.85},${m.base} H${cx + m.r * 0.85} M${cx},${m.base - m.r * 0.85} V${m.base + m.r * 0.85}`}
              opacity={0.45}
            />
          </g>
        ))}
      </g>
      {lights && <rect x={tx - 3} y={ty - 3} width={5} height={7} rx={1.5} className="neon-amber" style={{ fill: '#f59e0b' }} />}
    </g>
  )
}
