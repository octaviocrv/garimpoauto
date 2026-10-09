import { ArrowRight } from 'lucide-react'
import { useEffect, useRef, useState, type PointerEvent } from 'react'
import { Backdrop } from './hero-scene/Backdrop'
import { HeroScene } from './hero-scene/HeroScene'
import { useReducedMotion } from './hero-scene/hooks'
import { Mascot } from './hero-scene/Mascot'

const METRICS = [
  { to: 2.4, decimals: 1, suffix: 'k+', label: 'Revendedores', color: 'text-teal-400' },
  { to: 18, decimals: 0, suffix: 'k+', label: 'Carros listados', color: 'text-yellow-500' },
  { to: 98, decimals: 0, suffix: '%', label: 'Satisfação', color: 'text-white' },
]

/** Número que conta até o valor final uma vez, quando a página abre. */
function CountUp({ to, decimals, suffix, delay }: { to: number; decimals: number; suffix: string; delay: number }) {
  const reduced = useReducedMotion()
  const [value, setValue] = useState(reduced ? to : 0)
  useEffect(() => {
    if (reduced) return
    let frame = 0
    const start = performance.now() + delay
    const tick = (now: number) => {
      const t = Math.min(1, Math.max(0, (now - start) / 1400))
      setValue(to * (1 - Math.pow(1 - t, 3)))
      if (t < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [to, delay, reduced])
  return (
    <>
      {value.toFixed(decimals)}
      {suffix}
    </>
  )
}

const rise = (i: number) => ({ animationDelay: `${120 + i * 110}ms` })

// Caixa da cena (hologramas + Hiro): ocupa a área do hero, mas no desktop a altura
// é limitada pela largura, pra o Hiro não invadir o texto em telas menos largas.
const SCENE_BOX = 'absolute bottom-0 right-0 h-full w-full lg:h-[min(100%,52vw)]'

export function Hero() {
  const artRef = useRef<HTMLDivElement>(null)
  const frame = useRef(0)

  // Parallax pela rolagem: --sy vai de 0 a 1 enquanto o hero sai da tela
  useEffect(() => {
    const onScroll = () => {
      artRef.current?.style.setProperty('--sy', Math.min(1, window.scrollY / window.innerHeight).toFixed(3))
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  // Parallax pelo mouse: --mx/--my de -1 a 1 a partir do centro da seção
  const onPointerMove = (e: PointerEvent<HTMLElement>) => {
    if (e.pointerType !== 'mouse') return
    const rect = e.currentTarget.getBoundingClientRect()
    const mx = ((e.clientX - rect.left) / rect.width) * 2 - 1
    const my = ((e.clientY - rect.top) / rect.height) * 2 - 1
    cancelAnimationFrame(frame.current)
    frame.current = requestAnimationFrame(() => {
      artRef.current?.style.setProperty('--mx', mx.toFixed(3))
      artRef.current?.style.setProperty('--my', my.toFixed(3))
    })
  }
  const onPointerLeave = () => {
    artRef.current?.style.setProperty('--mx', '0')
    artRef.current?.style.setProperty('--my', '0')
  }

  return (
    <section
      id="inicio"
      onPointerMove={onPointerMove}
      onPointerLeave={onPointerLeave}
      className="relative flex min-h-screen flex-col overflow-hidden bg-[#050505] font-sans text-white"
    >
      {/* Glow de fundo (aparece no mobile, acima da foto) */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 z-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-teal-900/30 via-black to-black"
      />

      {/* Camada 4: navbar */}
      <header className="relative z-30 border-b border-white/10 bg-[#0a0a0a]">
        <div className="mx-auto flex h-20 max-w-7xl items-center justify-between px-6 lg:max-w-none lg:px-[2.5%]">
          <a href="#inicio" className="flex items-center gap-3" aria-label="Garimpo Auto, ir para o início">
            <span className="grid h-11 w-11 place-items-center overflow-hidden rounded-full border-2 border-teal-600 bg-teal-900">
              <img src="/mascot/han-profile.jpeg" alt="" className="h-full w-full object-cover" />
            </span>
            <span className="text-lg font-bold">Garimpo Auto</span>
          </a>
          <nav aria-label="Navegação principal" className="flex items-center gap-6 sm:gap-10">
            <a href="#foco" className="hidden text-gray-400 transition-colors hover:text-white sm:inline">Sobre</a>
            <a href="#como-funciona" className="hidden text-gray-400 transition-colors hover:text-white sm:inline">Recursos</a>
            <a href="#acompanhar" className="rounded-lg bg-teal-600 px-5 py-2.5 font-semibold transition-all hover:bg-teal-500">Entrar</a>
          </nav>
        </div>
      </header>

      {/* Camada 4: conteúdo à esquerda, sempre na frente e sobre a parte preta da foto.
          pointer-events-none no wrapper pra não bloquear a busca e a vitrine da cena. */}
      <div className="pointer-events-none relative z-30 flex w-full flex-1 px-6 lg:pl-[8%] lg:pr-0">
        <div className="pointer-events-auto w-full py-16 lg:max-w-[42vw] lg:self-center lg:py-20">
          <p style={rise(0)} className="hs-rise flex items-center gap-3 text-sm font-semibold tracking-widest text-teal-500 xl:text-base">
            <span aria-hidden="true" className="h-px w-8 bg-teal-500" />
            <span><span className="font-jp">ガリンボ</span> · GARIMPO</span>
          </p>

          <h1
            style={rise(1)}
            className="hs-rise mt-6 text-5xl font-extrabold leading-tight tracking-tight lg:text-[clamp(3.25rem,3.6vw,5.25rem)] lg:leading-[1.1]"
          >
            O jeito mais{' '}
            <span className="bg-gradient-to-r from-teal-400 to-yellow-200 bg-clip-text text-transparent">esperto</span>{' '}
            de garimpar carros
          </h1>

          <p
            style={rise(2)}
            className="hs-rise mt-6 max-w-md text-lg font-normal text-gray-400 lg:max-w-[31vw] lg:text-[clamp(1.125rem,1.2vw,1.5rem)]"
          >
            Tecnologia e inteligência pra revendedores que não perdem tempo. Encontre, compare e feche negócio mais rápido.
          </p>

          <div style={rise(3)} className="hs-rise mt-10 flex flex-wrap gap-4">
            <a
              href="#acompanhar"
              className="group inline-flex items-center gap-2 rounded-lg bg-teal-600 px-6 py-3 font-medium text-white transition-all hover:bg-teal-500 xl:px-9 xl:py-4 xl:text-lg"
            >
              Entrar no sistema{' '}
              <ArrowRight size={18} aria-hidden="true" className="transition-transform duration-300 group-hover:translate-x-1" />
            </a>
            <a
              href="#como-funciona"
              className="rounded-lg border border-gray-600 bg-black/40 px-6 py-3 text-gray-300 transition-all hover:border-gray-400 xl:px-9 xl:py-4 xl:text-lg"
            >
              Conhecer mais
            </a>
          </div>

          <dl style={rise(4)} className="hs-rise mt-16 flex flex-wrap gap-8 border-t border-gray-800 pt-8 xl:gap-12">
            {METRICS.map((m, i) => (
              <div key={m.label} className="flex flex-col-reverse">
                <dt className="text-sm text-gray-500 xl:text-base">{m.label}</dt>
                <dd className={`text-3xl font-bold tabular-nums xl:text-[clamp(2.25rem,2.3vw,3rem)] ${m.color}`}>
                  <CountUp to={m.to} decimals={m.decimals} suffix={m.suffix} delay={600 + i * 150} />
                </dd>
              </div>
            ))}
          </dl>
        </div>
      </div>

      {/* Arte: no desktop ocupa a área abaixo da navbar; no mobile vira um bloco abaixo do texto.
          Sem z-index no wrapper, pra as camadas 1–3 competirem direto com o conteúdo (z-30). */}
      <div
        ref={artRef}
        aria-hidden="true"
        className="relative h-[460px] overflow-hidden sm:h-[560px] lg:absolute lg:inset-x-0 lg:bottom-0 lg:top-20 lg:h-auto"
      >
        {/* Camada 1: foto do galpão com degradê preto na esquerda */}
        <Backdrop />

        {/* Camada 2: hologramas. A máscara apaga tudo antes da coluna de texto. */}
        <div className="pointer-events-none absolute inset-0 z-10 [mask-image:linear-gradient(to_bottom,transparent_0%,black_25%)] lg:[mask-image:linear-gradient(to_right,transparent_43%,black_48%)]">
          <div className={SCENE_BOX}>
            <HeroScene />
          </div>
        </div>

        {/* Camada 3: Hiro, na frente dos hologramas */}
        <div className={`z-20 ${SCENE_BOX}`}>
          <Mascot />
        </div>
      </div>
    </section>
  )
}
