// Camada 1: foto do galpão + degradês.
// - Preto absoluto na esquerda, dissolvendo até revelar o galpão na direita
// - Tom azul-petróleo leve na direita, pra casar com os hologramas
// - Leve parallax oposto ao dos hologramas (lê --mx/--my do Hero)

const SRC = '/backgrounds/garagem'

export function Backdrop() {
  return (
    <div className="pointer-events-none absolute inset-0 z-0 overflow-hidden">
      <div
        className="absolute inset-[-2%] transition-transform duration-1000 ease-out"
        style={{ transform: 'translate3d(calc(var(--mx, 0) * 5px), calc(var(--my, 0) * 3px), 0)' }}
      >
        <img
          src={`${SRC}-1920.webp`}
          srcSet={`${SRC}-1280.webp 1280w, ${SRC}-1920.webp 1920w, ${SRC}-2752.webp 2752w`}
          sizes="100vw"
          alt=""
          decoding="async"
          className="hero-photo h-full w-full object-cover object-[70%_45%] lg:object-[64%_45%]"
        />
      </div>
      <div className="hero-shade-teal absolute inset-0" />
      <div className="hero-shade absolute inset-0" />
    </div>
  )
}
