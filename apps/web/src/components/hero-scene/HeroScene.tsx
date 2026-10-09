import { useRef, type ReactNode } from 'react'
import { HoloBloom, KanjiSigns, MarketChart, PhoneSparks } from './Ambient'
import { SCENE_SVG } from './data'
import { useInView, usePageVisible, useReducedMotion } from './hooks'
import { MapPanel } from './MapPanel'
import { Popups } from './Popups'
import { SearchHolo } from './SearchHolo'
import { Showroom } from './Showroom'
import { Shrine } from './Shrine'
import { Traffic } from './Traffic'

// Hologramas atrás do Hiro, em 4 camadas com profundidades diferentes.
// Todas usam o sistema de coordenadas de SCENE_SVG (ver data.ts), o mesmo do Hiro.
// O parallax lê --mx/--my (mouse, -1..1) e --sy (rolagem, 0..1), definidas no Hero.
// A animação só roda com a seção visível, a aba ativa e sem prefers-reduced-motion.

function Layer({ depth, children }: { depth: number; children: ReactNode }) {
  return (
    <div
      className="absolute inset-0 transition-transform duration-700 ease-out"
      style={{
        transform: `translate3d(calc(var(--mx, 0) * ${-9 * depth}px), calc(var(--my, 0) * ${-6 * depth}px + var(--sy, 0) * ${-50 * depth}px), 0)`,
      }}
    >
      <svg {...SCENE_SVG} className="h-full w-full overflow-visible" focusable="false">
        {children}
      </svg>
    </div>
  )
}

// Gradientes de brilho usados pelas camadas (url(#...) vale pro documento todo)
function SceneDefs() {
  return (
    <defs>
      <radialGradient id="hs-spark-teal">
        <stop offset="0" stopColor="#a5f9fc" stopOpacity={0.95} />
        <stop offset="0.3" stopColor="#00f0ff" stopOpacity={0.45} />
        <stop offset="1" stopColor="#00f0ff" stopOpacity={0} />
      </radialGradient>
      <radialGradient id="hs-spark-amber">
        <stop offset="0" stopColor="#fde68a" stopOpacity={0.95} />
        <stop offset="0.3" stopColor="#f59e0b" stopOpacity={0.45} />
        <stop offset="1" stopColor="#f59e0b" stopOpacity={0} />
      </radialGradient>
      <radialGradient id="hs-bloom">
        <stop offset="0" stopColor="#00f0ff" stopOpacity={0.2} />
        <stop offset="0.5" stopColor="#00f0ff" stopOpacity={0.07} />
        <stop offset="1" stopColor="#00f0ff" stopOpacity={0} />
      </radialGradient>
    </defs>
  )
}

export function HeroScene() {
  const rootRef = useRef<HTMLDivElement>(null)
  const reduced = useReducedMotion()
  const inView = useInView(rootRef)
  const visible = usePageVisible()
  const live = !reduced && inView && visible

  return (
    <div ref={rootRef} className="absolute inset-0">
      <Layer depth={0.3}>
        <SceneDefs />
        <HoloBloom live={live} />
        <Shrine live={live} />
      </Layer>
      <Layer depth={0.65}>
        <KanjiSigns live={live} />
        <MapPanel live={live} still={reduced} />
        <MarketChart live={live} />
        <Showroom live={live} />
      </Layer>
      <Layer depth={1}>
        <Traffic live={live} still={reduced} />
        <PhoneSparks live={live} />
      </Layer>
      <Layer depth={1.35}>
        <SearchHolo live={live} still={reduced} />
        <Popups live={live} />
      </Layer>
    </div>
  )
}
