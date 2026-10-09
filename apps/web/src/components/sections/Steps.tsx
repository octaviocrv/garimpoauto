import {
  BadgeCheck,
  CalendarDays,
  Car,
  ChartNoAxesCombined,
  Columns3,
  CopyCheck,
  Globe,
  MapPin,
  Route,
  Search,
  SlidersHorizontal,
  Sparkles,
  Store,
  Tag,
  TrendingDown,
  type LucideIcon,
} from 'lucide-react'
import { useEffect, useRef, useState, type CSSProperties, type PointerEvent } from 'react'
import { Circuit } from './Circuit'
import { useLive, useMediaQuery, useSeenOnce } from './hooks'

// Seção "Como funciona": 3 painéis de vidro fumê ligados por uma trilha de circuito.
// Ao passar o mouse (ou, no celular, quando o card chega no meio da tela) o card
// dá um glitch rápido nas bordas e solta pop-ups com o que está "entrando" nele.

interface Pop {
  icon: LucideIcon
  label: string
  at: 'tl' | 'tr' | 'bl' | 'br'
  amber?: boolean
}

interface Step {
  n: string
  kanji: string
  reading: string
  icon: LucideIcon
  title: string
  text: string
  pops: Pop[]
}

const STEPS: Step[] = [
  {
    n: '01',
    kanji: '検索',
    reading: 'KENSAKU',
    icon: Search,
    title: 'Você procura',
    text: 'Informe o carro que você quer encontrar e os critérios que fazem sentido pro seu estoque.',
    pops: [
      { icon: Globe, label: 'OLX', at: 'tl' },
      { icon: Store, label: 'Mercado Livre', at: 'tr' },
      { icon: MapPin, label: 'BH e região', at: 'bl', amber: true },
      { icon: Car, label: 'WebMotors', at: 'br' },
    ],
  },
  {
    n: '02',
    kanji: '整理',
    reading: 'SEIRI',
    icon: SlidersHorizontal,
    title: 'A gente organiza',
    text: 'Os anúncios chegam padronizados para você bater o olho em ano, km, preço e origem.',
    pops: [
      { icon: CalendarDays, label: 'Ano 2019', at: 'tl' },
      { icon: Route, label: '54 mil km', at: 'tr' },
      { icon: CopyCheck, label: 'Sem repetido', at: 'bl' },
      { icon: Tag, label: 'R$ 98.400', at: 'br', amber: true },
    ],
  },
  {
    n: '03',
    kanji: '比較',
    reading: 'HIKAKU',
    icon: ChartNoAxesCombined,
    title: 'Você compara',
    text: 'O foco é facilitar a escolha do carro que vale sua atenção, sem enrolação.',
    pops: [
      { icon: Columns3, label: 'Lado a lado', at: 'tl' },
      { icon: TrendingDown, label: 'Abaixo da FIPE', at: 'tr' },
      { icon: BadgeCheck, label: 'Vale a visita', at: 'bl' },
      { icon: Sparkles, label: 'Bom negócio', at: 'br', amber: true },
    ],
  },
]

function StepCard({
  step,
  index,
  active,
  onActive,
  cardRef,
}: {
  step: Step
  index: number
  active: boolean
  onActive: (on: boolean) => void
  cardRef: (el: HTMLElement | null) => void
}) {
  const Icon = step.icon

  // Brilho do vidro segue o mouse (--mx/--my em % do card)
  const onPointerMove = (e: PointerEvent<HTMLElement>) => {
    if (e.pointerType !== 'mouse') return
    const r = e.currentTarget.getBoundingClientRect()
    e.currentTarget.style.setProperty('--mx', `${(((e.clientX - r.left) / r.width) * 100).toFixed(1)}%`)
    e.currentTarget.style.setProperty('--my', `${(((e.clientY - r.top) / r.height) * 100).toFixed(1)}%`)
  }

  return (
    <article
      ref={cardRef}
      data-index={index}
      className={`step-card${active ? ' is-active' : ''}`}
      style={{ '--i': index } as CSSProperties}
      onPointerEnter={(e) => e.pointerType === 'mouse' && onActive(true)}
      onPointerLeave={(e) => e.pointerType === 'mouse' && onActive(false)}
      onPointerMove={onPointerMove}
    >
      <div className="step-glass" aria-hidden="true">
        <span className="step-kanji font-jp">{step.kanji}</span>
        <span className="step-scan" />
      </div>
      <span className="hud-corners" aria-hidden="true" />
      <span className="step-glitch" aria-hidden="true" />

      <div className="step-body">
        <div className="step-top">
          <span className="step-number">
            {step.n}
            <small aria-hidden="true">/03</small>
          </span>
          <span className="step-tag" aria-hidden="true">
            <span className="font-jp">{step.kanji}</span>
            {step.reading}
          </span>
        </div>
        <span className="step-icon">
          <Icon size={22} aria-hidden="true" />
        </span>
        <h3>{step.title}</h3>
        <p>{step.text}</p>
      </div>

      <ul className="step-pops" aria-hidden="true">
        {step.pops.map((pop, k) => {
          const PopIcon = pop.icon
          return (
            <li key={pop.label} className={`pop pop-${pop.at}${pop.amber ? ' is-amber' : ''}`} style={{ '--k': k } as CSSProperties}>
              <span className="pop-chip">
                <PopIcon size={13} />
                {pop.label}
              </span>
              <span className="pop-link">
                <i />
              </span>
            </li>
          )
        })}
      </ul>
    </article>
  )
}

export function Steps() {
  const sectionRef = useRef<HTMLElement>(null)
  const gridRef = useRef<HTMLDivElement>(null)
  const cardRefs = useRef<(HTMLElement | null)[]>([])
  const seen = useSeenOnce(gridRef)
  const live = useLive(sectionRef)
  const [active, setActive] = useState<number | null>(null)
  const touch = useMediaQuery('(hover: none)')
  const stacked = useMediaQuery('(max-width: 899px)')

  // Sem hover e com os cards empilhados: ativa o card que está passando pelo meio da tela
  useEffect(() => {
    if (!touch || !stacked) return
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) if (e.isIntersecting) setActive(Number((e.target as HTMLElement).dataset.index))
      },
      { rootMargin: '-42% 0px -42% 0px' },
    )
    cardRefs.current.forEach((c) => c && io.observe(c))
    return () => io.disconnect()
  }, [touch, stacked])

  // Sem hover e lado a lado (tablet deitado): os cards vão se revezando sozinhos
  useEffect(() => {
    if (!touch || stacked || !live) return
    const id = window.setInterval(() => setActive((cur) => (cur === null ? 0 : (cur + 1) % STEPS.length)), 3200)
    return () => window.clearInterval(id)
  }, [touch, stacked, live])

  return (
    <section ref={sectionRef} className="steps" id="como-funciona" aria-labelledby="steps-title">
      <div className="steps-bg" aria-hidden="true">
        <span className="steps-bg-kanji font-jp">仕組み</span>
      </div>

      <div className="section-inner">
        <div className="section-head">
          <div>
            <p className="eyebrow">
              <span>
                <span className="font-jp">手順</span> · Direto ao ponto
              </span>
            </p>
            <h2 id="steps-title" className="section-title">
              Menos aba aberta. <em>Mais carro na tela.</em>
            </h2>
          </div>
          <p className="hud-meta" aria-hidden="true">
            BH · 19°55′S 43°56′W
          </p>
        </div>

        <div ref={gridRef} className={`steps-grid${seen ? ' is-seen' : ''}`}>
          <Circuit gridRef={gridRef} cardRefs={cardRefs} live={live} />
          {STEPS.map((step, i) => (
            <StepCard
              key={step.n}
              step={step}
              index={i}
              active={active === i}
              onActive={(on) => setActive((cur) => (on ? i : cur === i ? null : cur))}
              cardRef={(el) => (cardRefs.current[i] = el)}
            />
          ))}
        </div>
      </div>
    </section>
  )
}
