import { useRef } from 'react'
import { DataFlow } from './DataFlow'
import { useLive, useSeenOnce } from './hooks'

// Seção "Agora": malha em perspectiva correndo no fundo e, ao lado do texto,
// o diagrama com o caminho da primeira busca.

export function FocusNow() {
  const ref = useRef<HTMLElement>(null)
  const live = useLive(ref)
  const seen = useSeenOnce(ref)

  return (
    <section
      ref={ref}
      className={`focus${live ? '' : ' is-paused'}${seen ? ' is-seen' : ''}`}
      id="foco"
      aria-labelledby="focus-title"
    >
      <div className="focus-bg" aria-hidden="true">
        <div className="focus-floor" />
        <div className="focus-horizon" />
      </div>

      <div className="focus-inner">
        <div className="focus-copy">
          <span className="focus-kanji font-jp" aria-hidden="true">
            今
          </span>
          <p className="eyebrow">
            <span>
              <span className="font-jp">今</span> · Agora
            </span>
          </p>
          <h2 id="focus-title" className="section-title">
            Primeiro, fazer a busca <em>funcionar bem.</em>
          </h2>
          <p className="focus-text">
            A primeira etapa é consultar uma fonte de ponta a ponta, tratar os dados e mostrar um resultado simples. Depois entram as
            outras fontes e os filtros.
          </p>
        </div>

        <figure className="flow-frame" aria-hidden="true">
          <figcaption className="flow-head">
            <span>
              <span className="font-jp">検索ルート</span> · rota da busca
            </span>
            <span className="flow-live">em teste</span>
          </figcaption>
          <DataFlow />
          <span className="hud-corners" />
        </figure>
      </div>
    </section>
  )
}
