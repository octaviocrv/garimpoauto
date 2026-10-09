import { useEffect, useState, type RefObject } from 'react'
import { useInView, usePageVisible, useReducedMotion } from '../hero-scene/hooks'

/** Vira true na primeira vez que o elemento aparece na tela e fica assim. */
export function useSeenOnce(ref: RefObject<Element>, rootMargin = '0px 0px -12% 0px') {
  const reduced = useReducedMotion()
  const [seen, setSeen] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el || seen) return
    const io = new IntersectionObserver(([entry]) => entry.isIntersecting && setSeen(true), { rootMargin })
    io.observe(el)
    return () => io.disconnect()
  }, [ref, rootMargin, seen])
  return seen || reduced
}

/** Animação contínua só com a seção na tela, a aba ativa e sem prefers-reduced-motion (igual ao hero). */
export function useLive(ref: RefObject<Element>) {
  const reduced = useReducedMotion()
  const inView = useInView(ref)
  const visible = usePageVisible()
  return !reduced && inView && visible
}

export function useMediaQuery(query: string) {
  const [matches, setMatches] = useState(() => window.matchMedia(query).matches)
  useEffect(() => {
    const mq = window.matchMedia(query)
    const onChange = () => setMatches(mq.matches)
    onChange()
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [query])
  return matches
}
