import { ArrowRight } from 'lucide-react'
import { HologramLayer } from './HologramLayer'

const METRICS = [
  { value: '2.4k+', label: 'Revendedores', color: 'text-teal-400' },
  { value: '18k+', label: 'Carros listados', color: 'text-yellow-500' },
  { value: '98%', label: 'Satisfação', color: 'text-white' },
]

export function Hero() {
  return (
    <section id="inicio" className="relative flex min-h-screen flex-col overflow-hidden bg-[#050505] font-sans text-white">
      {/* Z-0: glow radial no canto superior direito */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 z-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-teal-900/30 via-black to-black"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-40 -left-40 z-0 h-[480px] w-[640px] rounded-full bg-teal-900/20 blur-3xl"
      />

      {/* Z-30: navbar */}
      <header className="relative z-30 border-b border-white/10">
        <div className="mx-auto flex h-20 max-w-7xl items-center justify-between px-6 lg:px-8">
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

      {/* Z-30: conteúdo (coluna esquerda) */}
      <div className="relative z-30 mx-auto flex w-full max-w-7xl flex-1 px-6 lg:px-8">
        <div className="w-full py-16 lg:w-1/2 lg:self-center lg:py-24">
          <p className="flex items-center gap-3 text-sm font-semibold tracking-widest text-teal-500">
            <span aria-hidden="true" className="h-px w-8 bg-teal-500" />
            <span><span className="font-jp">ガリンボ</span> · GARIMPO</span>
          </p>

          <h1 className="mt-6 text-5xl font-extrabold leading-tight tracking-tight lg:text-6xl">
            O jeito mais{' '}
            <span className="bg-gradient-to-r from-teal-400 to-yellow-200 bg-clip-text text-transparent">esperto</span>{' '}
            de garimpar carros
          </h1>

          <p className="mt-4 max-w-md text-lg font-normal text-gray-400">
            Tecnologia e inteligência pra revendedores que não perdem tempo. Encontre, compare e feche negócio mais rápido.
          </p>

          <div className="mt-10 flex flex-wrap gap-4">
            <a
              href="#acompanhar"
              className="inline-flex items-center gap-2 rounded-lg bg-teal-600 px-6 py-3 font-medium text-white transition-all hover:bg-teal-500"
            >
              Entrar no sistema <ArrowRight size={18} aria-hidden="true" />
            </a>
            <a
              href="#como-funciona"
              className="rounded-lg border border-gray-600 bg-transparent px-6 py-3 text-gray-300 transition-all hover:border-gray-400"
            >
              Conhecer mais
            </a>
          </div>

          <dl className="mt-16 flex flex-wrap gap-8 border-t border-gray-800 pt-8">
            {METRICS.map((m) => (
              <div key={m.label} className="flex flex-col-reverse">
                <dt className="text-sm text-gray-500">{m.label}</dt>
                <dd className={`text-3xl font-bold ${m.color}`}>{m.value}</dd>
              </div>
            ))}
          </dl>
        </div>
      </div>

      {/* Arte: no desktop ocupa a seção inteira (absoluta); no mobile vira um bloco abaixo do texto.
          Sem z-index no wrapper, pra Z-10 / Z-20 competirem direto com o conteúdo Z-30. */}
      <div aria-hidden="true" className="relative h-[460px] sm:h-[560px] lg:absolute lg:inset-0 lg:h-auto">
        {/* Z-10: hologramas, com fade-to-black pro lado do texto */}
        <div className="pointer-events-none absolute inset-y-0 right-0 z-10 w-full opacity-70 [mask-image:linear-gradient(to_bottom,transparent_0%,black_30%)] lg:top-20 lg:w-[60%] lg:opacity-100 lg:[mask-image:linear-gradient(to_right,transparent_0%,black_30%)]">
          <HologramLayer />
        </div>

        {/* Z-20: mascote */}
        <img
          src="/mascot/hiro-hero.svg"
          alt=""
          width={700}
          height={1080}
          decoding="async"
          className="pointer-events-none absolute bottom-0 right-1/2 z-20 h-full w-auto max-w-none translate-x-1/2 drop-shadow-[0_0_40px_rgba(0,240,255,0.15)] lg:right-[5%] lg:h-[85%] lg:translate-x-0"
        />
      </div>
    </section>
  )
}
