import { useEffect, useMemo, useRef, useState, type CSSProperties, type MutableRefObject, type RefObject } from 'react'

// Trilha de circuito que liga os 3 cards, como rota de GPS ou placa-mãe.
// Fica por trás do vidro dos cards (aparece borrada dentro deles e nítida nos
// vãos). Um pulso de luz percorre a trilha e, quando passa por um card, acende
// a porta de entrada e varre o card com um scan. Tudo medido em px a partir do
// layout real, então funciona em 3 colunas (rota horizontal) e empilhado no
// celular (espinha vertical à esquerda).

type Pt = [number, number]

interface CardBox {
  x: number
  y: number
  w: number
  h: number
  /** Altura da porta (centro do número 01/02/03) a partir do topo do card */
  port: number
}

interface Geo {
  w: number
  h: number
  vertical: boolean
  cards: CardBox[]
}

interface Hit {
  x: number
  y: number
  /** Distância ao longo da trilha principal */
  at: number
  card: number
  /** Ramal até o card (só no modo vertical) */
  stub?: string
}

interface Route {
  main: string
  mainLen: number
  pair?: string
  bus?: string
  busLen: number
  branches: string[]
  vias: Pt[]
  pads: Pt[]
  hits: Hit[]
}

const PERIOD = 6200 // ms de um ciclo do pulso
const MOVE = 0.68 // parte do ciclo em que o pulso anda (o resto é pausa)
const TAIL = 110 // comprimento do rastro (px)
const HEAD = 16 // comprimento da cabeça brilhante (px)
const SCAN_W = 90 // largura da faixa do scan dentro do card

const len = (pts: Pt[]) => pts.slice(1).reduce((sum, p, i) => sum + Math.hypot(p[0] - pts[i][0], p[1] - pts[i][1]), 0)
const toPath = (pts: Pt[]) => 'M' + pts.map(([x, y]) => `${Math.round(x * 10) / 10},${Math.round(y * 10) / 10}`).join(' L')

function measure(grid: HTMLElement, cards: HTMLElement[]): Geo {
  const boxes = cards.map((card) => {
    const num = card.querySelector('.step-number')
    const top = card.getBoundingClientRect().top
    const port = num ? num.getBoundingClientRect().top - top + num.getBoundingClientRect().height / 2 : 44
    return { x: card.offsetLeft, y: card.offsetTop, w: card.offsetWidth, h: card.offsetHeight, port: Math.round(port) }
  })
  const vertical = boxes.length > 1 && boxes[1].y > boxes[0].y + 8
  return { w: grid.clientWidth, h: grid.clientHeight, vertical, cards: boxes }
}

function horizontalRoute(c: CardBox[]): Route {
  const first = c[0]
  const last = c[c.length - 1]
  const y = first.y + first.port
  const sx = first.x - 40
  const ex = last.x + last.w + 40

  // Trilha principal: entra pela esquerda com chanfro de 45°, atravessa os cards e sai pela direita
  const main: Pt[] = [[sx, y + 64], [sx, y + 22], [sx + 22, y]]
  const marks: { at: number; x: number; card: number }[] = []
  c.forEach((card, i) => {
    main.push([card.x, y])
    marks.push({ at: len(main), x: card.x, card: i })
    main.push([card.x + card.w, y])
    marks.push({ at: len(main), x: card.x + card.w, card: i })
  })
  main.push([ex - 22, y], [ex, y + 22], [ex, y + 64])

  // Trilha paralela, mais fina, que mergulha em "U" nos vãos (cara de placa)
  const pair: Pt[] = [[sx + 8, y + 64], [sx + 8, y + 25], [sx + 25, y + 8]]
  const vias: Pt[] = []
  for (let i = 0; i < c.length - 1; i++) {
    const a = c[i].x + c[i].w
    const b = c[i + 1].x
    pair.push([a + 6, y + 8], [a + 18, y + 20], [b - 18, y + 20], [b - 6, y + 8])
    vias.push([(a + b) / 2, y], [(a + b) / 2, y + 20])
  }
  pair.push([ex - 25, y + 8], [ex - 8, y + 25], [ex - 8, y + 64])

  // Barramento de baixo: volta da direita pra esquerda, com ramal no card do meio
  const yb = Math.max(...c.map((k) => k.y + k.h)) + 46
  const bus: Pt[] = [
    [last.x + last.w - 44, last.y + last.h],
    [last.x + last.w - 44, yb - 14],
    [last.x + last.w - 58, yb],
    [first.x + 58, yb],
    [first.x + 44, yb - 14],
    [first.x + 44, first.y + first.h],
  ]
  const branches = c.slice(1, -1).map((k) => toPath([[k.x + k.w / 2, k.y + k.h], [k.x + k.w / 2, yb]]))
  c.slice(1, -1).forEach((k) => vias.push([k.x + k.w / 2, yb]))

  return {
    main: toPath(main),
    mainLen: len(main),
    pair: toPath(pair),
    bus: toPath(bus),
    busLen: len(bus),
    branches,
    vias,
    pads: [main[0], main[main.length - 1]],
    hits: marks.map((m) => ({ x: m.x, y, at: m.at, card: m.card })),
  }
}

function verticalRoute(c: CardBox[]): Route {
  const first = c[0]
  const last = c[c.length - 1]
  const sx = first.x - 16
  const main: Pt[] = [[sx, first.y - 28]]
  const hits: Hit[] = []
  c.forEach((card, i) => {
    const y = card.y + card.port
    main.push([sx, y])
    hits.push({ x: card.x, y, at: len(main), card: i, stub: toPath([[sx, y], [card.x, y]]) })
  })
  main.push([sx, last.y + last.h + 24])
  return {
    main: toPath(main),
    mainLen: len(main),
    busLen: 0,
    branches: hits.map((h) => h.stub!),
    vias: [],
    pads: [main[0], main[main.length - 1]],
    hits,
  }
}

/** Keyframes de um traço que corre a trilha inteira e some no fim (stroke-dashoffset). */
function runFrames(dash: number, total: number, move = MOVE): Keyframe[] {
  return [
    { offset: 0, strokeDashoffset: `${dash}px` },
    { offset: move, strokeDashoffset: `${dash - total - TAIL}px` },
    { offset: 1, strokeDashoffset: `${dash - total - TAIL}px` },
  ]
}

/** Momento (0–1 do ciclo) em que a cabeça do pulso passa pela distância `at`. */
const hitTime = (at: number, total: number) => (at / (total + TAIL)) * MOVE

interface Props {
  gridRef: RefObject<HTMLElement>
  cardRefs: MutableRefObject<(HTMLElement | null)[]>
  live: boolean
}

export function Circuit({ gridRef, cardRefs, live }: Props) {
  const [geo, setGeo] = useState<Geo | null>(null)
  const tailRef = useRef<SVGPathElement>(null)
  const headRef = useRef<SVGPathElement>(null)
  const busRef = useRef<SVGPathElement>(null)
  const hotRefs = useRef<(SVGGElement | null)[]>([])

  // Mede os cards sempre que o grid muda de tamanho (e quando as fontes carregam)
  useEffect(() => {
    const grid = gridRef.current
    if (!grid) return
    let frame = 0
    const update = () => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => {
        const cards = cardRefs.current.filter((c): c is HTMLElement => !!c)
        if (cards.length < 2) return
        const next = measure(grid, cards)
        setGeo((prev) => (prev && JSON.stringify(prev) === JSON.stringify(next) ? prev : next))
      })
    }
    const ro = new ResizeObserver(update)
    ro.observe(grid)
    cardRefs.current.forEach((c) => c && ro.observe(c))
    document.fonts?.ready.then(update)
    update()
    return () => {
      ro.disconnect()
      cancelAnimationFrame(frame)
    }
  }, [gridRef, cardRefs])

  const route = useMemo(() => (geo ? (geo.vertical ? verticalRoute(geo.cards) : horizontalRoute(geo.cards)) : null), [geo])

  // Pulso + portas + scan, todos com o mesmo relógio (Web Animations, mesmo startTime)
  useEffect(() => {
    if (!route || !geo || !live) return
    const anims: Animation[] = []
    const startTime = document.timeline.currentTime
    const run = (el: Element | null | undefined, keyframes: Keyframe[], extra: KeyframeAnimationOptions = {}) => {
      if (!el) return
      const anim = el.animate(keyframes, { duration: PERIOD, iterations: Infinity, ...extra })
      anim.startTime = startTime
      anims.push(anim)
    }

    const L = route.mainLen
    run(tailRef.current, runFrames(TAIL, L))
    run(headRef.current, runFrames(HEAD, L))
    if (route.bus) run(busRef.current, runFrames(TAIL, route.busLen, 0.6), { iterationStart: 0.42 })

    route.hits.forEach((hit, i) => {
      const f = hitTime(hit.at, L)
      run(hotRefs.current[i], [
        { offset: 0, opacity: 0 },
        { offset: f, opacity: 0 },
        { offset: Math.min(f + 0.008, 1), opacity: 1 },
        { offset: Math.min(f + 0.11, 1), opacity: 0 },
        { offset: 1, opacity: 0 },
      ])
    })

    // Scan: entra junto com o pulso e atravessa o card até a porta de saída
    geo.cards.forEach((card, i) => {
      const own = route.hits.filter((h) => h.card === i)
      if (!own.length) return
      const fIn = hitTime(own[0].at, L)
      const fOut = Math.max(fIn + 0.02, own.length > 1 ? hitTime(own[own.length - 1].at, L) : fIn + 900 / PERIOD)
      const scan = cardRefs.current[i]?.querySelector('.step-scan')
      const from = `translateX(${-SCAN_W}px)`
      const to = `translateX(${card.w}px)`
      run(scan, [
        { offset: 0, opacity: 0, transform: from },
        { offset: fIn, opacity: 0, transform: from },
        { offset: Math.min(fIn + 0.01, 1), opacity: 1, transform: from },
        { offset: Math.min(fOut, 1), opacity: 1, transform: to },
        { offset: Math.min(fOut + 0.01, 1), opacity: 0, transform: to },
        { offset: 1, opacity: 0, transform: to },
      ])
    })

    return () => anims.forEach((a) => a.cancel())
  }, [route, geo, live, cardRefs])

  if (!geo || !route) return null
  const hidden = (dash: number, total: number) => `${dash - total - TAIL}`
  const box = { width: geo.w, height: geo.h, viewBox: `0 0 ${geo.w} ${geo.h}` }

  return (
    <>
      {/* Atrás dos cards: trilhas e pulso */}
      <svg {...box} className="circuit circuit-back" aria-hidden="true" focusable="false">
        {route.pair && <path d={route.pair} className="trace trace-pair" />}
        {route.bus && <path d={route.bus} className="trace trace-bus" />}
        {route.branches.map((d, i) => (
          <path key={i} d={d} className={geo.vertical ? 'trace trace-stub' : 'trace trace-bus'} />
        ))}
        <path d={route.main} className="trace trace-main" style={{ '--len': route.mainLen } as CSSProperties} />
        {route.bus && (
          <path
            ref={busRef}
            d={route.bus}
            className="trace-pulse trace-pulse-dim"
            strokeDasharray={`${TAIL} ${route.busLen + TAIL + 10}`}
            strokeDashoffset={hidden(TAIL, route.busLen)}
          />
        )}
        <path
          ref={tailRef}
          d={route.main}
          className="trace-pulse"
          strokeDasharray={`${TAIL} ${route.mainLen + TAIL + 10}`}
          strokeDashoffset={hidden(TAIL, route.mainLen)}
        />
        <path
          ref={headRef}
          d={route.main}
          className="trace-pulse trace-pulse-head"
          strokeDasharray={`${HEAD} ${route.mainLen + TAIL + 10}`}
          strokeDashoffset={hidden(HEAD, route.mainLen)}
        />
      </svg>

      {/* Na frente dos cards: pads, vias e as portas que acendem */}
      <svg {...box} className="circuit circuit-front" aria-hidden="true" focusable="false">
        {route.pads.map(([x, y], i) => (
          <g key={i} className="trace-pad">
            <circle cx={x} cy={y} r={5} />
            <circle cx={x} cy={y} r={1.6} className="trace-pad-dot" />
          </g>
        ))}
        {route.vias.map(([x, y], i) => (
          <circle key={i} cx={x} cy={y} r={2.6} className="trace-via" />
        ))}
        {route.hits.map((hit, i) => (
          <g key={i}>
            <rect x={hit.x - 2} y={hit.y - 7} width={4} height={14} rx={1} className="trace-port" />
            <g ref={(el) => (hotRefs.current[i] = el)} opacity={0} className="trace-hot">
              {hit.stub && <path d={hit.stub} className="trace-hot-line" />}
              <rect x={hit.x - 2} y={hit.y - 7} width={4} height={14} rx={1} className="trace-hot-port" />
              <circle cx={hit.x} cy={hit.y} r={9} className="trace-hot-ring" />
            </g>
          </g>
        ))}
      </svg>
    </>
  )
}
