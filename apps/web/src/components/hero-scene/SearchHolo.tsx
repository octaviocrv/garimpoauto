import { useEffect, useState } from 'react'
import { makeQuery, type Listing, type SearchQuery } from './data'
import { emitScene } from './hooks'
import { rand } from './random'

// Barra de busca holográfica: digita sozinha (com ritmo humano, não fixo),
// "pesquisa", mostra sugestões e avisa o mapa e os anúncios.
// Passar o mouse pausa e destaca; clicar pula pra próxima etapa;
// clicar numa sugestão manda o carro pra vitrine.

type Phase = 'idle' | 'typing' | 'searching' | 'results' | 'clearing'

const W = 300
const H = 44
// Sugestões mais estreitas que a barra, pra não passarem atrás do celular do Han
const SUG_W = 212

function delayFor(phase: Phase, typed: string, query: SearchQuery) {
  switch (phase) {
    case 'idle':
      return rand(700, 1600)
    case 'typing': {
      const prev = typed[typed.length - 1]
      return prev === ' ' ? rand(140, 320) : rand(55, 135)
    }
    case 'searching':
      return rand(700, 1150)
    case 'results':
      return rand(2800, 4400)
    case 'clearing':
      return typed.length > query.text.length * 0.5 ? rand(18, 34) : rand(28, 50)
  }
}

export function SearchHolo({ live, still }: { live: boolean; still: boolean }) {
  const [query, setQuery] = useState<SearchQuery>(() => makeQuery())
  const [typed, setTyped] = useState('')
  const [phase, setPhase] = useState<Phase>('idle')
  const [hover, setHover] = useState(false)

  useEffect(() => {
    if (!live) return
    if (hover && phase !== 'searching') return
    const timer = window.setTimeout(() => {
      switch (phase) {
        case 'idle': {
          setQuery((q) => makeQuery(q))
          setTyped('')
          setPhase('typing')
          break
        }
        case 'typing':
          if (typed.length < query.text.length) setTyped(query.text.slice(0, typed.length + 1))
          else setPhase('searching')
          break
        case 'searching':
          setPhase('results')
          emitScene('search', query)
          break
        case 'results':
          setPhase('clearing')
          break
        case 'clearing':
          if (typed.length > 0) setTyped(typed.slice(0, -1))
          else setPhase('idle')
          break
      }
    }, delayFor(phase, typed, query))
    return () => window.clearTimeout(timer)
  }, [live, hover, phase, typed, query])

  const text = still ? query.text : typed
  const showResults = phase === 'results' || (hover && phase !== 'searching' && typed.length > 0)

  const onBarClick = () => {
    if (phase === 'typing' || phase === 'idle') {
      setTyped(query.text)
      setPhase('searching')
    } else if (phase === 'results') {
      setPhase('clearing')
    }
  }

  const onPick = (listing: Listing) => emitScene('focus', listing)

  return (
    <g id="busca" transform="translate(20 228)">
      <g
        className="hs-search pointer-events-auto"
        onPointerEnter={() => setHover(true)}
        onPointerLeave={() => setHover(false)}
      >
        {/* Área de hover que inclui as sugestões */}
        <rect x={-6} y={-6} width={W + 12} height={showResults ? H + 104 : H + 12} fill="transparent" />

        <g className="cursor-pointer" onClick={onBarClick}>
          <rect width={W} height={H} rx={12} className="hs-search-box neon-teal" />
          {/* pino de localização */}
          <path d="M22,30 C20,26 15,23 15,19 A7,7 0 1 1 29,19 C29,23 24,26 22,30 Z" className="neon-amber" transform="translate(0 -2)" />
          <circle cx={22} cy={17} r={2} fill="#f59e0b" />
          <text x={40} y={27} fontSize={14} fill="#f0fdfd" className="glow-text" fontFamily="Inter, sans-serif">
            {text || <tspan fill="#5eead4" opacity={0.55}>Buscar carro perto de você</tspan>}
            {!still && <tspan className="hs-caret" fill="#00f0ff" dx={1}>|</tspan>}
          </text>
          {phase === 'searching' ? (
            <circle cx={W - 24} cy={H / 2} r={8} className="neon-teal hs-spin" strokeDasharray="30 20" style={{ ['--spin' as string]: '0.8s' }} />
          ) : (
            <g className="neon-teal">
              <circle cx={W - 26} cy={H / 2 - 2} r={7} />
              <path d={`M${W - 21},${H / 2 + 3} L${W - 15},${H / 2 + 9}`} />
            </g>
          )}
        </g>

        {showResults && (
          <g transform={`translate(0 ${H + 8})`}>
            {query.listings.map((l, i) => (
              <g key={l.key} transform={`translate(0 ${i * 30})`}>
                <g className="hs-sug hs-sug-row cursor-pointer" style={{ animationDelay: `${i * 90}ms` }} onClick={() => onPick(l)}>
                  <rect width={SUG_W} height={26} rx={7} className="hs-sug-bg" stroke="rgba(0,240,255,0.35)" />
                  <circle cx={14} cy={13} r={2.5} fill={i === 0 ? '#f59e0b' : '#00f0ff'} />
                  <text x={24} y={17} fontSize={10} fill="#ccfbf1" fontFamily="Inter, sans-serif">
                    {l.name}
                    <tspan fill="#5eead4" opacity={0.7}>{`  ·  ${l.km} km`}</tspan>
                  </text>
                  <text x={SUG_W - 10} y={17} fontSize={10} textAnchor="end" fill="#fde68a" className="glow-text-amber" fontFamily="Inter, sans-serif" fontWeight={600}>
                    {l.price}
                  </text>
                </g>
              </g>
            ))}
          </g>
        )}
      </g>
    </g>
  )
}
