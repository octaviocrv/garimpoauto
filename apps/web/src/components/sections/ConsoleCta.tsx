import { Fragment, useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import { useReducedMotion } from '../hero-scene/hooks'
import { seeded } from '../hero-scene/random'
import { useLive, useSeenOnce } from './hooks'

// CTA como painel de comando: console preto com brilho interno azul-petróleo,
// título que "decodifica" de katakana quando aparece, log de terminal e um
// botão de HUD com cursor piscando.

const GLYPHS = 'アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワンガギグゲゴ'

// Andamento real do projeto (ver _memoria/estrategia.md)
const LOG = [
  { text: 'ideia e plano fechados', status: 'ok' },
  { text: 'ligando a primeira fonte', status: 'agora', now: true },
  { text: 'tela de busca de carros', status: 'depois' },
]

/** Texto que começa como katakana apagado e se revela letra por letra quando `start` vira true. */
function ScrambleText({ text, start }: { text: string; start: boolean }) {
  const ref = useRef<HTMLSpanElement>(null)
  const reduced = useReducedMotion()
  const [phase, setPhase] = useState<'wait' | 'run' | 'done'>(reduced ? 'done' : 'wait')

  const words = useMemo(() => {
    const rnd = seeded(7)
    return text.split(' ').map((w) => [...w].map((ch) => ({ ch, glyph: GLYPHS[Math.floor(rnd() * GLYPHS.length)] })))
  }, [text])

  useEffect(() => {
    if (reduced) setPhase('done')
    else if (start) setPhase((p) => (p === 'wait' ? 'run' : p))
  }, [start, reduced])

  // Embaralha direto no DOM (sem re-render por frame)
  useEffect(() => {
    if (phase !== 'run') return
    const chars = Array.from(ref.current?.querySelectorAll<HTMLElement>('[data-glyph]') ?? [])
    const t0 = performance.now()
    let frame = 0
    let last = 0
    const tick = (now: number) => {
      const shuffle = now - last > 55
      if (shuffle) last = now
      let pending = 0
      chars.forEach((el, i) => {
        if (el.classList.contains('is-set')) return
        if (now - t0 > 180 + (i / chars.length) * 1000) el.classList.add('is-set')
        else {
          pending++
          if (shuffle) el.dataset.glyph = GLYPHS[Math.floor(Math.random() * GLYPHS.length)]
        }
      })
      if (pending) frame = requestAnimationFrame(tick)
      else setPhase('done')
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [phase])

  return (
    <span ref={ref} className={`scramble is-${phase}`}>
      <span className="sr-only">{text}</span>
      <span aria-hidden="true">
        {words.map((word, wi) => (
          <Fragment key={wi}>
            {wi > 0 && ' '}
            <span className="scramble-word">
              {word.map((c, ci) => (
                <span key={ci} data-glyph={c.glyph}>
                  {c.ch}
                </span>
              ))}
            </span>
          </Fragment>
        ))}
      </span>
    </span>
  )
}

export function ConsoleCta() {
  const sectionRef = useRef<HTMLElement>(null)
  const consoleRef = useRef<HTMLDivElement>(null)
  const live = useLive(sectionRef)
  const seen = useSeenOnce(consoleRef, '0px 0px -20% 0px')

  return (
    <section ref={sectionRef} className={`cta${live ? '' : ' is-paused'}`} id="acompanhar" aria-labelledby="cta-title">
      <div ref={consoleRef} className={`console${seen ? ' is-on' : ''}`}>
        <div className="console-fx" aria-hidden="true">
          <span className="console-kanji font-jp">始動</span>
          <span className="console-sweep" />
        </div>
        <span className="hud-corners" aria-hidden="true" />

        <div className="console-bar" aria-hidden="true">
          <span className="console-led" />
          <span>
            <span className="font-jp">始動</span> · partida
          </span>
          <span className="console-ruler" />
          <span className="console-signal">
            <i />
            <i />
            <i />
            <i />
          </span>
          <span>CH 01</span>
        </div>

        <div className="console-body">
          <div className="console-copy">
            <p className="eyebrow eyebrow-prompt">Garimpo Auto</p>
            <h2 id="cta-title" className="section-title console-title">
              <ScrambleText text="Estamos colocando a primeira busca na rua." start={seen} />
            </h2>
            <p className="console-text">Esta página é o ponto de partida. A próxima tela será a busca de carros.</p>
            <ol className="console-log" aria-hidden="true">
              {LOG.map((line, k) => (
                <li key={line.text} style={{ '--k': k } as CSSProperties}>
                  <span className="console-log-text">{line.text}</span>
                  <span className={`console-log-status${line.now ? ' is-now' : ''}`}>{line.status}</span>
                </li>
              ))}
            </ol>
          </div>

          <div className="console-action">
            <span className="hud-glow">
              <a className="hud-btn" href="mailto:contato@garimpoauto.local">
                <span className="hud-btn-fill" aria-hidden="true" />
                <span className="hud-bracket is-left" aria-hidden="true">
                  [
                </span>
                Quero acompanhar
                <span className="hud-bracket is-right" aria-hidden="true">
                  ]
                </span>
                <span className="hud-caret" aria-hidden="true">
                  _
                </span>
              </a>
            </span>
            <span className="console-hint">manda um oi que a gente te avisa</span>
          </div>
        </div>
      </div>
    </section>
  )
}
