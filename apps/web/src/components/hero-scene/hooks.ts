import { useCallback, useEffect, useRef, useState, type RefObject } from 'react'
import { nextId, rand } from './random'

export function useReducedMotion() {
  const query = '(prefers-reduced-motion: reduce)'
  const [reduced, setReduced] = useState(() => window.matchMedia(query).matches)
  useEffect(() => {
    const mq = window.matchMedia(query)
    const onChange = () => setReduced(mq.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])
  return reduced
}

export function useInView(ref: RefObject<Element>) {
  const [inView, setInView] = useState(true)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const io = new IntersectionObserver(([entry]) => setInView(entry.isIntersecting), { threshold: 0.05 })
    io.observe(el)
    return () => io.disconnect()
  }, [ref])
  return inView
}

export function usePageVisible() {
  const [visible, setVisible] = useState(() => !document.hidden)
  useEffect(() => {
    const onChange = () => setVisible(!document.hidden)
    document.addEventListener('visibilitychange', onChange)
    return () => document.removeEventListener('visibilitychange', onChange)
  }, [])
  return visible
}

/** Chama `fn` em intervalos aleatórios entre min e max (ms) enquanto `live`. */
export function useRandomTicker(live: boolean, fn: () => void, [min, max]: [number, number], first?: number) {
  const fnRef = useRef(fn)
  useEffect(() => {
    fnRef.current = fn
  })
  useEffect(() => {
    if (!live) return
    let timer = 0
    const tick = () => {
      fnRef.current()
      timer = window.setTimeout(tick, rand(min, max))
    }
    timer = window.setTimeout(tick, first ?? rand(min, max))
    return () => window.clearTimeout(timer)
  }, [live, min, max, first])
}

export type Spawned<T> = T & { id: number }

/**
 * Lista de elementos efêmeros: `spawn` cria um novo em intervalos aleatórios
 * (ou devolve null pra pular a vez); cada elemento se remove com `remove(id)`
 * quando a própria animação termina.
 */
export function useSpawner<T>(
  live: boolean,
  spawn: (current: Spawned<T>[]) => T | null,
  range: [number, number],
  max: number,
  first?: number,
) {
  const [items, setItems] = useState<Spawned<T>[]>([])
  const itemsRef = useRef(items)
  useEffect(() => {
    itemsRef.current = items
  })
  const push = useCallback((item: T) => setItems((list) => [...list, { ...item, id: nextId() }]), [])
  const remove = useCallback((id: number) => setItems((list) => list.filter((i) => i.id !== id)), [])
  useRandomTicker(
    live,
    () => {
      if (itemsRef.current.length >= max) return
      const item = spawn(itemsRef.current)
      if (item) push(item)
    },
    range,
    first,
  )
  return { items, push, remove }
}

/**
 * Roda uma animação (Web Animations API) uma única vez quando o elemento monta.
 * `progress` (0–1) permite começar no meio, pra cena já nascer "em andamento".
 */
export function usePlayOnce(
  ref: RefObject<Element>,
  build: () => { keyframes: Keyframe[]; options: KeyframeAnimationOptions & { duration: number }; progress?: number },
  onDone?: () => void,
) {
  const buildRef = useRef(build)
  const doneRef = useRef(onDone)
  useEffect(() => {
    doneRef.current = onDone
  })
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const { keyframes, options, progress } = buildRef.current()
    const anim = el.animate(keyframes, { fill: 'both', ...options })
    if (progress) anim.currentTime = progress * options.duration
    anim.onfinish = () => doneRef.current?.()
    return () => anim.cancel()
  }, [ref])
}

/** Pisca, de vez em quando, um dos filhos marcados com `data-flicker` (neon falhando). */
export function useFlicker(ref: RefObject<Element>, live: boolean, range: [number, number]) {
  useRandomTicker(live, () => {
    const targets = ref.current?.querySelectorAll('[data-flicker]')
    if (!targets?.length) return
    const el = targets[Math.floor(Math.random() * targets.length)]
    const low = rand(0.15, 0.45)
    el.animate(
      [
        { opacity: 1 },
        { opacity: low, offset: 0.08 },
        { opacity: 0.95, offset: 0.16 },
        { opacity: low + 0.2, offset: 0.3 },
        { opacity: 1 },
      ],
      { duration: rand(450, 900) },
    )
  }, range)
}

// Barramento de eventos da cena: a busca avisa o mapa, os anúncios e as partículas.
const bus = new EventTarget()

export function emitScene<T>(type: 'search' | 'focus', detail: T) {
  bus.dispatchEvent(new CustomEvent(type, { detail }))
}

export function useSceneEvent<T>(type: 'search' | 'focus', handler: (detail: T) => void) {
  const ref = useRef(handler)
  useEffect(() => {
    ref.current = handler
  })
  useEffect(() => {
    const listener = (e: Event) => ref.current((e as CustomEvent<T>).detail)
    bus.addEventListener(type, listener)
    return () => bus.removeEventListener(type, listener)
  }, [type])
}
