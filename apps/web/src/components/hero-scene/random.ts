export const rand = (min: number, max: number) => min + Math.random() * (max - min)
export const randInt = (min: number, max: number) => Math.floor(rand(min, max + 1))
export const pick = <T,>(list: readonly T[]): T => list[Math.floor(Math.random() * list.length)]
export const chance = (p: number) => Math.random() < p

/** Gerador determinístico (mulberry32) pra composições que não podem mudar a cada render. */
export function seeded(seed: number) {
  return () => {
    seed = (seed + 0x6d2b79f5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

let uid = 0
export const nextId = () => ++uid
