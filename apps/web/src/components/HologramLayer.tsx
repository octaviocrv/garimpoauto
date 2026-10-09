// Camada de hologramas (Z-10) atrás do mascote.
// Tudo é SVG genérico com as classes de glow (.neon-teal / .neon-teal-dim / .neon-amber
// em index.css). Cada bloco está isolado num <g> nomeado pra trocar os paths depois.
// Sistema de coordenadas: viewBox 1000x1000, ancorado à direita (xMaxYMid slice).

// Silhueta lateral genérica de carro (sedã/esportivo), ~340x110
const CAR_BODY =
  'M10,80 L20,60 Q60,52 100,50 L140,22 Q160,12 200,12 L250,14 Q275,16 295,40 L320,50 Q340,56 340,70 L338,86 L300,86 A26,26 0 0 0 248,86 L100,86 A26,26 0 0 0 48,86 L14,86 Z'
const CAR_WINDOWS = 'M110,48 L148,24 Q160,18 200,18 L206,18 L206,48 Z M214,18 L248,20 Q268,22 284,44 L214,46 Z'
const CAR_DETAILS = 'M20,66 L335,64 M300,56 L330,58 M14,72 L30,72'

// Contorno aproximado do Brasil, 100x100
const BRAZIL =
  'M30,8 L42,4 L50,10 L58,6 L66,12 L72,18 L84,24 L96,30 L94,40 L88,50 L84,62 L76,70 L70,80 L62,90 L56,98 L52,92 L56,84 L50,76 L44,68 L36,64 L34,54 L22,50 L12,46 L4,40 L8,30 L16,26 L22,16 Z'
const BRAZIL_STATES = 'M42,4 L44,30 L66,40 L84,24 M44,30 L34,54 M66,40 L62,62 L76,70 M62,62 L44,68'

// Pino de localização, origem na ponta
const PIN = 'M0,0 C-3,-6 -8,-10 -8,-15 A8,8 0 1 1 8,-15 C8,-10 3,-6 0,0 Z'

function WireCar({ x, y, scale = 1, flip = false }: { x: number; y: number; scale?: number; flip?: boolean }) {
  const sx = flip ? -scale : scale
  return (
    <g transform={`translate(${x} ${y}) scale(${sx} ${scale})`} className="neon-teal">
      <path d={CAR_BODY} />
      <path d={CAR_WINDOWS} opacity={0.7} />
      <path d={CAR_DETAILS} opacity={0.6} />
      {[74, 274].map((cx) => (
        <g key={cx}>
          <circle cx={cx} cy={86} r={22} />
          <circle cx={cx} cy={86} r={10} opacity={0.6} />
        </g>
      ))}
    </g>
  )
}

export function HologramLayer() {
  return (
    <svg
      viewBox="0 0 1000 1000"
      preserveAspectRatio="xMaxYMid slice"
      className="h-full w-full"
      aria-hidden="true"
      focusable="false"
    >
      {/* Cenário de fundo: prédios, templo e palmeiras */}
      <g id="cenario" className="neon-teal-dim" strokeWidth={1.2}>
        {/* Skyline */}
        <path d="M600,230 V150 H650 V230 M660,230 V110 H710 V230 M720,230 V170 H760 V230 M770,230 V80 H820 V230 M830,230 V130 H880 V230 M890,230 V60 H930 V230 M940,230 V140 H1000" />
        {Array.from({ length: 18 }, (_, i) => (
          <rect key={i} x={612 + (i % 6) * 62} y={100 + Math.floor(i / 6) * 34} width={6} height={4} />
        ))}
        {/* Pagoda / templo */}
        <path d="M180,230 H420 M200,230 V200 H400 V230 M170,200 Q300,180 430,200 M215,200 V170 H385 V200 M190,170 Q300,140 410,170 M240,170 V140 H360 V170 M215,140 Q300,105 385,140 M300,118 V70" />
        <path d="M460,230 V190 M440,190 Q470,175 500,190 M448,175 Q470,160 492,175 M470,160 V130" />
        {/* Palmeiras */}
        <path d="M940,520 Q930,420 950,330 M950,330 Q900,320 870,350 M950,330 Q990,310 1010,340 M950,330 Q920,290 890,290 M950,330 Q975,290 1000,285" />
        <path d="M90,640 Q100,560 80,480 M80,480 Q40,470 20,500 M80,480 Q120,460 150,480 M80,480 Q60,440 30,440 M80,480 Q110,440 140,440" />
      </g>

      {/* Piso em perspectiva (garagem) */}
      <g id="piso" className="neon-teal-dim" strokeWidth={1}>
        <path d="M0,1000 L520,700 M200,1000 L540,700 M420,1000 L560,700 M640,1000 L580,700 M860,1000 L600,700 M0,860 H1000 M60,780 H1000" />
      </g>

      {/* Kanjis JDM */}
      <g id="kanjis" className="neon-teal font-jp" strokeWidth={1.4}>
        <text x={210} y={300} fontSize={72} fontWeight={500} style={{ fill: 'rgba(0,240,255,0.08)' }}>
          ガリンボ
        </text>
        <path d="M690,290 H760" strokeWidth={3} className="neon-amber" />
        <text x={770} y={330} fontSize={150} fontWeight={700} style={{ fill: 'rgba(0,240,255,0.1)' }}>
          車
        </text>
      </g>

      {/* Carros em wireframe */}
      <g id="carros">
        <WireCar x={60} y={500} scale={1.05} />
        <WireCar x={20} y={760} scale={1.25} />
        <WireCar x={1020} y={700} scale={0.85} flip />
      </g>

      {/* Mapa do Brasil */}
      <g id="mapa" transform="translate(840 360)">
        <rect width={150} height={220} rx={10} className="neon-teal" style={{ fill: 'rgba(0,240,255,0.04)' }} />
        <g transform="translate(15 45) scale(1.2)">
          <path d={BRAZIL} className="neon-teal" strokeDasharray="3 3" />
          <path d={BRAZIL_STATES} className="neon-teal-dim" strokeDasharray="2 3" />
        </g>
        <path d={PIN} transform="translate(85 150)" className="neon-teal" style={{ fill: 'rgba(0,240,255,0.25)' }} />
        <path d={PIN} transform="translate(125 40) scale(0.8)" className="neon-teal" />
      </g>

      {/* Tags flutuantes perto da cabeça e das mãos */}
      <g id="tags">
        {/* Barra de pesquisa */}
        <g className="neon-teal">
          <rect x={160} y={350} width={330} height={44} rx={10} style={{ fill: 'rgba(0,240,255,0.05)' }} />
          <circle cx={460} cy={370} r={8} />
          <path d="M466,376 L474,384" />
        </g>
        <g className="neon-teal" opacity={0.8}>
          <rect x={520} y={200} width={230} height={36} rx={18} style={{ fill: 'rgba(0,240,255,0.04)' }} />
          <path d="M722,210 L734,226 M734,210 L722,226" />
        </g>

        {/* Preço */}
        <g className="neon-amber">
          <path d="M240,430 L250,415 H370 Q378,415 378,423 V449 Q378,457 370,457 H290 L280,470 L278,457 H250 Z" style={{ fill: 'rgba(245,158,11,0.06)' }} />
        </g>
        <text x={258} y={442} fontSize={17} fill="#fbbf24" fontFamily="Inter, sans-serif" fontWeight={500}>
          R$ 50.000
        </text>

        {/* Card de mensagem */}
        <g className="neon-amber" opacity={0.85}>
          <rect x={70} y={480} width={110} height={50} rx={6} />
          <path d="M85,496 H160 M85,508 H145 M85,520 H130" />
          <path d="M125,530 V560" opacity={0.6} />
        </g>

        {/* Card de perfil */}
        <g opacity={0.9}>
          <rect x={70} y={640} width={170} height={110} rx={8} className="neon-teal-dim" style={{ fill: 'rgba(255,255,255,0.03)' }} />
          <circle cx={100} cy={668} r={9} className="neon-amber" style={{ fill: 'rgba(245,158,11,0.5)' }} />
          <path d="M84,692 Q100,676 116,692" className="neon-amber" />
          <path d="M130,690 H220" className="neon-amber" strokeWidth={2} />
          <path d="M90,712 H220 M90,726 H200" className="neon-teal-dim" />
        </g>

        {/* Mini gráfico de barras */}
        <g className="neon-teal" transform="translate(880 640)">
          {[18, 30, 24, 44, 36, 58].map((h, i) => (
            <rect key={i} x={i * 18} y={70 - h} width={10} height={h} style={{ fill: 'rgba(0,240,255,0.12)' }} />
          ))}
          <path d="M-6,74 H112" opacity={0.6} />
        </g>

        {/* Partículas saindo do celular */}
        <g className="neon-teal" style={{ fill: '#00f0ff' }}>
          {[
            [470, 600], [495, 585], [520, 610], [505, 640], [540, 590], [480, 630], [530, 560], [555, 625], [460, 575],
          ].map(([cx, cy], i) => (
            <circle key={i} cx={cx} cy={cy} r={i % 3 === 0 ? 2.2 : 1.4} />
          ))}
        </g>
      </g>
    </svg>
  )
}
