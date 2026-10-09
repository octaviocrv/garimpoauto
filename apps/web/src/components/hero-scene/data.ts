import { chance, nextId, pick, randInt } from './random'

// ---------------------------------------------------------------------------
// Sistema de coordenadas da cena: quadrado 1000x1000 ancorado embaixo à direita,
// com altura = altura da área do hero. x negativo avança pra esquerda (overflow
// visível). Hiro, hologramas e sombra usam o mesmo sistema, então ficam
// alinhados em qualquer resolução.
// ---------------------------------------------------------------------------

export const SCENE_SVG = { viewBox: '0 0 1000 1000', preserveAspectRatio: 'xMaxYMax meet' } as const

/** Hiro da cintura pra cima (hiro-busto.svg, proporção 680x930). `phone` = topo do celular. */
export const HIRO = { x: 180, y: 140, width: 629, height: 860, phone: [282, 520] as [number, number] }

// ---------------------------------------------------------------------------
// Carros: silhuetas laterais diferentes, todas com a frente virada pra esquerda.
// `base` é a linha do chão (centro das rodas); `head`/`tail` são farol e lanterna.
// ---------------------------------------------------------------------------

export type CarKind = 'sedan' | 'hatch' | 'suv' | 'pickup' | 'coupe' | 'van'

export interface CarModel {
  body: string
  windows: string
  details: string
  wheels: number[]
  r: number
  base: number
  width: number
  head: [number, number]
  tail: [number, number]
}

export const CAR_MODELS: Record<CarKind, CarModel> = {
  sedan: {
    body: 'M10,80 L20,60 Q60,52 100,50 L140,22 Q160,12 200,12 L250,14 Q275,16 295,40 L320,50 Q340,56 340,70 L338,86 L300,86 A26,26 0 0 0 248,86 L100,86 A26,26 0 0 0 48,86 L14,86 Z',
    windows: 'M110,48 L148,24 Q160,18 200,18 L206,18 L206,48 Z M214,18 L248,20 Q268,22 284,44 L214,46 Z',
    details: 'M20,66 L335,64 M300,56 L330,58 M150,56 H170',
    wheels: [74, 274],
    r: 22,
    base: 86,
    width: 340,
    head: [16, 64],
    tail: [334, 58],
  },
  hatch: {
    body: 'M8,82 L12,62 Q40,52 80,50 L118,22 Q130,14 160,14 L230,16 Q248,18 262,30 L280,56 Q288,62 288,72 L286,84 L252,84 A24,24 0 0 0 204,84 L88,84 A24,24 0 0 0 40,84 L10,84 Z',
    windows: 'M90,48 L122,24 Q132,19 160,19 L168,19 L168,48 Z M176,19 L226,21 Q242,23 254,34 L264,48 L176,48 Z',
    details: 'M16,64 L284,62 M268,40 L278,40 M130,56 H146',
    wheels: [64, 228],
    r: 20,
    base: 84,
    width: 288,
    head: [14, 64],
    tail: [282, 58],
  },
  suv: {
    body: 'M10,90 L12,58 Q30,48 70,46 L100,14 Q106,8 120,8 L280,8 Q300,8 310,24 L326,48 Q338,54 338,66 L336,94 L302,94 A28,28 0 0 0 246,94 L104,94 A28,28 0 0 0 48,94 L12,94 Z',
    windows: 'M80,44 L106,16 L180,16 L180,44 Z M188,16 L276,16 Q294,16 302,30 L310,44 L188,44 Z',
    details: 'M14,62 L336,62 M120,3 L290,3 M318,52 L334,54 M150,54 H170',
    wheels: [76, 274],
    r: 26,
    base: 94,
    width: 338,
    head: [16, 58],
    tail: [334, 56],
  },
  pickup: {
    body: 'M8,88 L10,60 Q24,52 60,50 L92,18 Q98,12 112,12 L180,12 Q190,12 192,22 L196,50 L352,50 L354,88 L318,88 A26,26 0 0 0 266,88 L100,88 A26,26 0 0 0 48,88 L10,88 Z',
    windows: 'M70,48 L98,20 L140,20 L140,48 Z M148,20 L184,20 L188,48 L148,48 Z',
    details: 'M196,62 L352,62 M10,66 L196,66 M340,54 L352,54 M120,58 H136',
    wheels: [74, 292],
    r: 24,
    base: 88,
    width: 354,
    head: [14, 62],
    tail: [350, 58],
  },
  coupe: {
    body: 'M6,74 L14,58 Q50,50 96,46 L150,24 Q170,18 206,18 L240,20 Q262,24 286,42 L330,48 Q346,52 346,62 L344,78 L304,78 A24,24 0 0 0 256,78 L98,78 A24,24 0 0 0 50,78 L8,78 Z',
    windows: 'M110,44 L154,26 Q170,22 200,22 L204,44 Z M212,22 L240,24 Q256,28 272,42 L212,44 Z',
    details: 'M300,42 L304,30 L346,28 L344,34 L306,36 M16,62 L342,60 M28,70 H50',
    wheels: [74, 280],
    r: 22,
    base: 78,
    width: 346,
    head: [12, 60],
    tail: [342, 56],
  },
  van: {
    body: 'M8,86 L10,46 L30,12 Q34,8 44,8 L250,8 Q266,8 266,24 L266,86 L234,86 A22,22 0 0 0 190,86 L78,86 A22,22 0 0 0 34,86 L8,86 Z',
    windows: 'M16,44 L34,16 L84,16 L84,44 Z M92,16 L150,16 L150,44 L92,44 Z M158,16 L210,16 L210,44 L158,44 Z',
    details: 'M10,56 L266,56 M150,16 L150,80 M218,16 L258,16',
    wheels: [56, 212],
    r: 22,
    base: 86,
    width: 266,
    head: [12, 58],
    tail: [264, 52],
  },
}

export const CAR_KINDS = Object.keys(CAR_MODELS) as CarKind[]

// ---------------------------------------------------------------------------
// Anúncios ilustrativos (região de BH). Só ambientação, não são dados reais.
// ---------------------------------------------------------------------------

const CATALOG: { name: string; short: string; kind: CarKind; price: string; budget: string }[] = [
  { name: 'Onix LT 2020', short: 'Onix 2020', kind: 'hatch', price: 'R$ 68.900', budget: 'R$ 70 mil' },
  { name: 'HB20 Sense 2019', short: 'HB20 2019', kind: 'hatch', price: 'R$ 59.900', budget: 'R$ 60 mil' },
  { name: 'Corolla XEi 2019', short: 'Corolla 2019', kind: 'sedan', price: 'R$ 112.000', budget: 'R$ 115 mil' },
  { name: 'Virtus 2021', short: 'Virtus 2021', kind: 'sedan', price: 'R$ 99.900', budget: 'R$ 100 mil' },
  { name: 'Compass 2021', short: 'Compass 2021', kind: 'suv', price: 'R$ 129.900', budget: 'R$ 130 mil' },
  { name: 'Renegade 2020', short: 'Renegade', kind: 'suv', price: 'R$ 94.900', budget: 'R$ 95 mil' },
  { name: 'Hilux SRV 2018', short: 'Hilux diesel', kind: 'pickup', price: 'R$ 189.000', budget: 'R$ 190 mil' },
  { name: 'Strada 2022', short: 'Strada 2022', kind: 'pickup', price: 'R$ 98.000', budget: 'R$ 100 mil' },
  { name: 'Civic Si 2015', short: 'Civic Si', kind: 'coupe', price: 'R$ 89.900', budget: 'R$ 90 mil' },
  { name: 'Spin LTZ 2019', short: 'Spin 7 lugares', kind: 'van', price: 'R$ 72.500', budget: 'R$ 75 mil' },
]

const PLACES = [
  { city: 'Contagem', km: 4 },
  { city: 'Barreiro', km: 7 },
  { city: 'Pampulha', km: 9 },
  { city: 'Nova Lima', km: 12 },
  { city: 'Ibirité', km: 14 },
  { city: 'Sabará', km: 16 },
  { city: 'Betim', km: 18 },
  { city: 'Santa Luzia', km: 22 },
]

export interface Listing {
  key: number
  name: string
  short: string
  kind: CarKind
  price: string
  budget: string
  city: string
  km: number
}

export function makeListing(avoidKind?: CarKind): Listing {
  const pool = avoidKind ? CATALOG.filter((c) => c.kind !== avoidKind) : CATALOG
  const car = pick(pool)
  const place = pick(PLACES)
  return { key: nextId(), ...car, ...place, km: place.km + randInt(-1, 2) }
}

function nearbyPrice(price: string) {
  const value = Number(price.replace(/\D/g, ''))
  const varied = Math.round((value * (1 + (Math.random() - 0.5) * 0.12)) / 100) * 100
  return `R$ ${varied.toLocaleString('pt-BR')}`
}

export interface SearchQuery {
  text: string
  listings: Listing[]
}

export function makeQuery(previous?: SearchQuery): SearchQuery {
  let main = makeListing()
  while (previous && main.short === previous.listings[0].short) main = makeListing()
  const patterns = [`${main.short} em ${main.city}`, `${main.short} até ${main.budget}`, `${main.short} perto de mim`]
  const text = pick(patterns)
  // Mesmo modelo em outro bairro, com preço um pouco diferente
  const place = pick(PLACES.filter((p) => p.city !== main.city))
  const similar = { ...main, ...place, key: nextId(), price: nearbyPrice(main.price) }
  const extra = makeListing(main.kind)
  return { text, listings: [main, chance(0.75) ? similar : makeListing(main.kind), extra] }
}

// ---------------------------------------------------------------------------
// Mapa do Brasil (contorno simplificado em lon/lat, projetado num retângulo).
// ---------------------------------------------------------------------------

const K = 3.9
export const project = (lon: number, lat: number): [number, number] => [(lon + 74) * K, (5.3 - lat) * K]

const OUTLINE: [number, number][] = [
  [-69.9, -4.2], [-69.4, -1.1], [-69.8, 1.1], [-67.3, 2.0], [-66.9, 1.2], [-65.4, 0.9], [-63.4, 2.2], [-64.0, 4.1],
  [-62.7, 4.0], [-60.6, 4.9], [-60.0, 5.2], [-59.8, 4.0], [-59.6, 2.0], [-58.0, 1.5], [-56.5, 1.9], [-54.5, 2.3],
  [-52.9, 2.2], [-51.6, 4.2], [-51.0, 3.2], [-50.0, 1.8], [-50.4, 0.2], [-48.5, -0.8], [-46.0, -1.0], [-44.3, -2.5],
  [-41.8, -2.9], [-38.5, -3.7], [-36.5, -5.0], [-35.2, -5.2], [-34.8, -7.1], [-35.1, -9.0], [-37.0, -11.0],
  [-38.5, -13.0], [-39.0, -15.5], [-39.2, -17.7], [-39.7, -19.6], [-40.9, -21.8], [-42.0, -23.0], [-44.5, -23.3],
  [-46.5, -24.0], [-48.5, -26.0], [-48.6, -28.5], [-50.2, -30.5], [-52.1, -32.1], [-53.4, -33.7], [-53.5, -32.5],
  [-55.0, -31.2], [-56.0, -30.2], [-57.6, -30.2], [-55.8, -28.0], [-53.8, -27.1], [-54.6, -25.6], [-54.3, -24.0],
  [-55.4, -23.9], [-55.7, -22.3], [-57.8, -22.1], [-57.9, -20.0], [-57.6, -18.0], [-58.4, -16.3], [-60.2, -15.1],
  [-60.5, -13.8], [-62.0, -13.0], [-63.0, -12.6], [-65.0, -11.8], [-65.4, -9.8], [-66.6, -9.9], [-68.6, -11.0],
  [-70.5, -11.0], [-70.6, -9.5], [-72.3, -10.0], [-73.0, -9.4], [-73.9, -7.4], [-73.0, -5.6], [-70.9, -4.4],
]

const POLY = OUTLINE.map(([lon, lat]) => project(lon, lat))
export const BRAZIL_PATH = `M${POLY.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' L')} Z`

function insideBrazil(x: number, y: number) {
  let inside = false
  for (let i = 0, j = POLY.length - 1; i < POLY.length; j = i++) {
    const [xi, yi] = POLY[i]
    const [xj, yj] = POLY[j]
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside
  }
  return inside
}

// Grade de pontinhos que preenche o país (efeito "mapa de app")
export const BRAZIL_DOTS: [number, number][] = []
for (let y = 2; y < 156; y += 5.2) {
  for (let x = 2; x < 160; x += 5.2) if (insideBrazil(x, y)) BRAZIL_DOTS.push([x, y])
}

export const BH = project(-43.94, -19.92)

export const CITIES: [number, number][] = [
  [-60.0, -3.1], [-48.5, -1.45], [-38.5, -3.9], [-35.2, -8.05], [-38.6, -12.97], [-47.9, -15.8], [-49.25, -16.68],
  [-56.1, -15.6], [-54.6, -20.4], [-46.63, -23.55], [-43.3, -22.9], [-49.27, -25.43], [-48.7, -27.6], [-51.2, -30.03],
  [-40.4, -20.3], [-48.28, -18.9], [-63.9, -8.76], [-48.3, -10.2], [-42.8, -5.1],
].map(([lon, lat]) => project(lon, lat))
