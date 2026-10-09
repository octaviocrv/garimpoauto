import { HIRO, SCENE_SVG } from './data'

// Camada 3: o Hiro da cintura pra cima, no mesmo sistema de coordenadas dos
// hologramas (assim celular, cabeça e portal ficam sempre alinhados).
// - Sombra suave atrás do corpo, pra destacá-lo dos carros da foto
// - Luz de borda (rim light) teal nos contornos da esquerda/topo, vinda dos hologramas
// - Brilho do celular iluminando a mão

export function Mascot() {
  const { x, y, width, height, phone } = HIRO
  return (
    <svg {...SCENE_SVG} className="pointer-events-none absolute inset-0 h-full w-full overflow-visible [will-change:transform]" focusable="false">
      <defs>
        <radialGradient id="hiro-shadow">
          <stop offset="0" stopColor="#000" stopOpacity={0.6} />
          <stop offset="1" stopColor="#000" stopOpacity={0} />
        </radialGradient>
        <radialGradient id="hiro-phone-glow">
          <stop offset="0" stopColor="#5ffbf1" stopOpacity={0.42} />
          <stop offset="0.45" stopColor="#00f0ff" stopOpacity={0.16} />
          <stop offset="1" stopColor="#00f0ff" stopOpacity={0} />
        </radialGradient>
        <filter id="hiro-rim" x="-8%" y="-8%" width="116%" height="116%" colorInterpolationFilters="sRGB">
          {/* faixa interna da borda: silhueta menos ela mesma deslocada pra direita/baixo */}
          <feMorphology in="SourceAlpha" operator="erode" radius="2" result="eroded" />
          <feOffset in="eroded" dx="5" dy="3" result="shifted" />
          <feComposite in="SourceAlpha" in2="shifted" operator="out" result="edge" />
          <feGaussianBlur in="edge" stdDeviation="1.8" result="edgeSoft" />
          <feFlood floodColor="#2ef2f2" floodOpacity="0.9" />
          <feComposite in2="edgeSoft" operator="in" result="rimColor" />
          <feComposite in="rimColor" in2="SourceAlpha" operator="in" result="rim" />
          <feBlend in="rim" in2="SourceGraphic" mode="screen" result="lit" />
          {/* halo bem leve por fora */}
          <feDropShadow in="lit" dx="0" dy="0" stdDeviation="10" floodColor="#00f0ff" floodOpacity="0.24" />
        </filter>
      </defs>

      <ellipse cx={x + width * 0.5} cy={y + height * 0.78} rx={width * 0.62} ry={height * 0.36} fill="url(#hiro-shadow)" />
      <image href="/mascot/hiro-busto.svg" x={x} y={y} width={width} height={height} filter="url(#hiro-rim)" />
      <ellipse cx={phone[0] - 18} cy={phone[1] + 30} rx={95} ry={85} fill="url(#hiro-phone-glow)" style={{ mixBlendMode: 'screen' }} />
    </svg>
  )
}
