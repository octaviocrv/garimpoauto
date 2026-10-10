import { BRAZIL_DOTS, BRAZIL_PATH, CAR_MODELS } from '../components/hero-scene/data'

const MAP_DOTS = BRAZIL_DOTS.filter((_, index) => index % 2 === 0)
const SEDAN = CAR_MODELS.sedan
const COUPE = CAR_MODELS.coupe

function WireCar({ model, transform, opacity }: {
  model: typeof SEDAN
  transform: string
  opacity: number
}) {
  return (
    <g transform={transform} opacity={opacity} className="search-hologram__lit">
      <path d={model.body} />
      <path d={model.windows} />
      <path d={model.details} strokeDasharray="3 3" />
      {model.wheels.map((cx) => (
        <g key={cx}>
          <circle cx={cx} cy={model.base} r={model.r} />
          <circle cx={cx} cy={model.base} r={model.r * 0.45} />
        </g>
      ))}
    </g>
  )
}

export function SearchHologram() {
  return (
    <div className="search-hologram" aria-hidden="true">
      <svg viewBox="0 0 760 430" role="presentation" focusable="false">
        <defs>
          <linearGradient id="search-holo-fade" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stopColor="black" />
            <stop offset="0.26" stopColor="white" stopOpacity="0.18" />
            <stop offset="0.5" stopColor="white" stopOpacity="0.88" />
            <stop offset="0.9" stopColor="white" />
            <stop offset="1" stopColor="black" stopOpacity="0.2" />
          </linearGradient>
          <linearGradient id="search-holo-vertical-fade" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="black" stopOpacity="0.35" />
            <stop offset="0.18" stopColor="white" />
            <stop offset="0.78" stopColor="white" stopOpacity="0.9" />
            <stop offset="1" stopColor="black" />
          </linearGradient>
          <mask id="search-holo-mask">
            <rect width="760" height="430" fill="url(#search-holo-fade)" />
            <rect width="760" height="430" fill="url(#search-holo-vertical-fade)" style={{ mixBlendMode: 'screen' }} />
          </mask>
          <filter id="search-holo-glow" x="-35%" y="-35%" width="170%" height="170%">
            <feGaussianBlur stdDeviation="2.4" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <g mask="url(#search-holo-mask)" className="search-hologram__scene">
          <g className="search-hologram__distant">
            <path d="M68 328 Q145 248 224 310 Q288 240 362 315 Q430 264 505 322 Q585 256 708 329" />
            <path d="M70 346 H720" />
            <path d="M535 330 V268 M555 330 V268 M520 268 H570 M514 258 Q545 247 576 258 M524 238 Q545 227 566 238 M531 218 Q545 206 559 218 M545 206 V188" />
            <path d="M497 286 H594 M507 258 H584 M519 238 H572" />
          </g>

          <g transform="translate(494 42) scale(0.78)" opacity="0.32">
            <path d={BRAZIL_PATH} className="search-hologram__outline" strokeDasharray="3 5" />
            <g className="search-hologram__dots">
              {MAP_DOTS.map(([x, y], index) => <circle key={index} cx={x} cy={y} r="1.2" />)}
            </g>
            <circle cx="104" cy="108" r="12" className="search-hologram__radar" />
            <circle cx="104" cy="108" r="3" />
          </g>

          <g className="search-hologram__rings" opacity="0.28">
            <circle cx="555" cy="205" r="76" />
            <circle cx="555" cy="205" r="112" strokeDasharray="2 8" />
            <path d="M407 205 H702 M555 58 V352" strokeDasharray="1 9" />
          </g>

          <WireCar model={SEDAN} transform="translate(338 274) scale(0.52)" opacity={0.58} />
          <WireCar model={COUPE} transform="translate(574 160) scale(0.34)" opacity={0.36} />

          <g className="search-hologram__data search-hologram__lit">
            <rect x="352" y="65" width="142" height="42" rx="4" />
            <text x="364" y="81">SCAN_0482 / ONLINE</text>
            <text x="364" y="97" className="search-hologram__value">R$ 78.800</text>

            <rect x="600" y="282" width="116" height="48" rx="4" />
            <text x="610" y="299">MATCH 94.8%</text>
            <path d="M610 318 H704 M610 312 H680" />

            <rect x="288" y="148" width="112" height="30" rx="15" />
            <circle cx="305" cy="163" r="4" />
            <text x="317" y="167">GARIMPANDO...</text>
          </g>

          <g className="search-hologram__chart" opacity="0.52">
            <path d="M612 98 V130 M628 88 V130 M644 108 V130 M660 77 V130 M676 94 V130" />
            <path d="M602 130 H690" />
          </g>

          <g className="search-hologram__kanji">
            <text x="690" y="76">車</text>
            <text x="414" y="232">ガリンボ</text>
          </g>

          <g className="search-hologram__particles">
            {[
              [325, 108], [347, 125], [388, 204], [433, 122], [474, 346], [527, 27],
              [580, 359], [623, 50], [705, 186], [720, 242], [664, 362], [446, 54],
            ].map(([cx, cy], index) => <circle key={index} cx={cx} cy={cy} r={index % 3 === 0 ? 2 : 1} />)}
          </g>
        </g>
      </svg>
    </div>
  )
}
