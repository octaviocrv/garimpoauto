import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ArrowLeft,
  ArrowSquareOut,
  Camera,
  Check,
  CheckCircle,
  Clock,
  CurrencyCircleDollar,
  Gauge,
  ImageBroken,
  MapPin,
  MagnifyingGlass,
  Question,
  ShieldWarning,
  Sparkle,
  Storefront,
  Tag,
  User,
  Warning,
  type Icon,
} from '@phosphor-icons/react'
import type { Anuncio, DetalheAnuncio } from '../types'
import type { Analise, Criterio, Mercado, Nivel } from './analise'
import { AMOSTRA_MINIMA, IDADE_MINIMA_ANOS, KM_POR_ANO_BAIXO } from './sinais'
import { fipeDaOlx } from './fipe'
import { T } from './textos'
import { GARIMPAR_TEXTOS as GT } from './garimparTextos'
import { IconeRedondo } from './IconeRedondo'
import { FichaAnuncio } from './FichaAnuncio'
import './Garimpar.css'

const reais = (valor: number) => `R$ ${Math.round(valor).toLocaleString('pt-BR')}`
const limitar = (valor: number, minimo: number, maximo: number) => Math.min(maximo, Math.max(minimo, valor))

function useNumeroAnimado(valor: number, duracao = 700) {
  const [atual, setAtual] = useState(valor)

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setAtual(valor)
      return
    }
    let quadro = 0
    const inicio = performance.now()
    const animar = (agora: number) => {
      const progresso = limitar((agora - inicio) / duracao, 0, 1)
      setAtual(valor * (1 - Math.pow(1 - progresso, 3)))
      if (progresso < 1) quadro = requestAnimationFrame(animar)
    }
    quadro = requestAnimationFrame(animar)
    return () => cancelAnimationFrame(quadro)
  }, [duracao, valor])

  return atual
}

function NumeroGrande({ valor, formato }: { valor: number; formato: (valor: number) => string }) {
  const animado = useNumeroAnimado(valor)
  return <>{formato(animado)}</>
}

function criterioDe(lista: Criterio[], id: Criterio['id']) {
  return lista.find((criterio) => criterio.id === id)
}

function totalDeIguais(preco: Criterio | undefined, mercado: Mercado | null | undefined) {
  if (mercado) return mercado.n
  const encontrado = preco?.fato.match(/Há (\d+)/)
  return encontrado ? Number(encontrado[1]) : null
}

function Chip({ children, icon: Icone }: { children: React.ReactNode; icon?: Icon }) {
  return (
    <span className="ga-chip">
      {Icone && <Icone size={15} weight="duotone" aria-hidden="true" />}
      {children}
    </span>
  )
}

function Frescor({ criterio }: { criterio: Criterio | undefined }) {
  if (!criterio || criterio.veredito === 'semdado') return null
  const recente = criterio.veredito === 'favor'
  return (
    <div className={`ga-frescor ${recente ? 'ga-frescor--recente' : ''}`}>
      <span className="ga-frescor__ponto" aria-hidden="true" />
      <span>{criterio.resultado}</span>
    </div>
  )
}

function Hero({ carro, recencia }: { carro: Anuncio; recencia: Criterio | undefined }) {
  const foto = carro.imagens[0]
  const nome = carro.modelo_original ?? carro.titulo ?? GT.modeloAusente
  const local = [carro.cidade, carro.estado].filter(Boolean).join(', ')

  return (
    <section className="ga-hero ga-entra">
      <div className="ga-hero__foto">
        {foto ? (
          <img src={foto} alt={`${GT.fotoDe} ${nome}`} decoding="async" referrerPolicy="no-referrer" />
        ) : (
          <div className="ga-sem-foto">
            <ImageBroken size={32} weight="duotone" aria-hidden="true" />
            <span>{GT.semFoto}</span>
          </div>
        )}
        <div className="ga-hero__sombra" aria-hidden="true" />
        <div className="ga-hero__frescor">
          <Frescor criterio={recencia} />
        </div>
      </div>

      <div className="ga-hero__texto">
        <p className="ga-sobretitulo">{GT.analiseRevenda}</p>
        <h1>{nome}</h1>
        <p className="ga-preco">
          {carro.preco === null ? GT.precoAusente : <NumeroGrande valor={carro.preco} formato={reais} />}
        </p>
        <div className="ga-chips" aria-label={GT.resumoCarro}>
          <Chip icon={Tag}>{carro.ano ?? GT.anoAusente}</Chip>
          <Chip icon={Gauge}>
            {carro.km === null ? GT.kmAusente : `${carro.km.toLocaleString('pt-BR')} km`}
          </Chip>
          {local && <Chip icon={MapPin}>{local}</Chip>}
        </div>
      </div>
    </section>
  )
}

type EstadoVeredito = 'destaque' | 'neutro' | 'sembase' | 'carregando'

function estadoDoVeredito(analise: Analise | undefined): EstadoVeredito {
  if (!analise) return 'carregando'
  if (analise.nivel) return 'destaque'
  if (!analise.mercado || !analise.margem) return 'sembase'
  return 'neutro'
}

function RotuloVeredito({
  nivel, estado, preliminar, temFipe,
}: {
  nivel: Nivel | null
  estado: EstadoVeredito
  preliminar: boolean
  temFipe: boolean
}) {
  if (nivel === 'quente') return <>{T.quente}</>
  if (nivel === 'boa') return <>{preliminar ? GT.boaPreliminar : T.boa}</>
  if (estado === 'sembase') return <>{temFipe ? GT.fipeSemMercado : GT.faltaBase}</>
  if (estado === 'carregando') return <>{GT.preparandoLeitura}</>
  return <>{GT.leituraNeutra}</>
}

function ItemChecklist({ ok, children }: { ok: boolean; children: React.ReactNode }) {
  return (
    <li>
      <span className={ok ? 'is-ok' : ''}>
        {ok ? <Check size={13} aria-hidden="true" /> : <span aria-hidden="true">•</span>}
      </span>
      {children}
    </li>
  )
}

function Veredito({
  carro, analise, preco, onBuscarIguais,
}: {
  carro: Anuncio
  analise: Analise | undefined
  preco: Criterio | undefined
  onBuscarIguais: () => void
}) {
  const estado = estadoDoVeredito(analise)
  const iguais = totalDeIguais(preco, analise?.mercado)
  const baseCompleta = iguais !== null && iguais >= AMOSTRA_MINIMA

  return (
    <section className={`ga-veredito ga-veredito--${estado} ga-entra`}>
      <div className="ga-veredito__cabecalho">
        <IconeRedondo
          icon={estado === 'destaque' ? Sparkle : estado === 'neutro' ? CheckCircle : Question}
          tom={estado === 'destaque' ? 'agua' : 'cinza'}
        />
        <div>
          <p className="ga-sobretitulo">{GT.veredito}</p>
          <h2>
            <RotuloVeredito
              nivel={analise?.nivel ?? null}
              estado={estado}
              preliminar={analise?.preliminar ?? false}
              temFipe={carro.fipe?.confianca === 'alta'}
            />
          </h2>
        </div>
      </div>
      <p className="ga-veredito__motivo">
        {analise?.motivo ?? GT.leituraCarregando}
      </p>
      {(estado === 'sembase' || estado === 'carregando') && (
        <ul className="ga-checklist" aria-label={GT.baseDaLeitura}>
          <ItemChecklist ok={baseCompleta}>
            {GT.carrosIguais} {iguais === null ? GT.naoDisponivel : `${iguais} de ${AMOSTRA_MINIMA}`}
          </ItemChecklist>
          <ItemChecklist ok={carro.km !== null}>{GT.kmInformado} {carro.km !== null ? GT.sim : GT.nao}</ItemChecklist>
          <ItemChecklist ok={carro.ano !== null}>{GT.anoInformado} {carro.ano !== null ? GT.sim : GT.nao}</ItemChecklist>
          <ItemChecklist ok={carro.preco !== null}>{GT.precoInformado} {carro.preco !== null ? GT.sim : GT.nao}</ItemChecklist>
          <ItemChecklist ok={carro.fipe?.confianca === 'alta'}>{GT.fipeEncontrada} {carro.fipe?.confianca === 'alta' ? GT.sim : GT.nao}</ItemChecklist>
        </ul>
      )}
      {carro.modelo && carro.ano !== null && (
        <button type="button" className="ga-buscar-iguais" onClick={onBuscarIguais}>
          <MagnifyingGlass size={18} weight="bold" aria-hidden="true" />
          <span>
            <strong>{GT.buscarCarrosIguais}</strong>
            <small>{GT.buscarCarrosIguaisAjuda}</small>
          </span>
        </button>
      )}
      <p className="ga-veredito__nota">{T.comoLer}</p>
    </section>
  )
}

function CartaoSinal({ criterio }: { criterio: Criterio }) {
  const icones: Partial<Record<Criterio['id'], Icon>> = {
    recencia: Clock,
    preco: Tag,
    km: Gauge,
    margem: CurrencyCircleDollar,
  }
  const Icone = icones[criterio.id] ?? CheckCircle

  return (
    <article className="ga-sinal">
      <div className="ga-sinal__topo">
        <IconeRedondo icon={Icone} />
        <span>{criterio.titulo}</span>
      </div>
      <strong>{criterio.resultado}</strong>
      <div className="ga-sinal__pulso" aria-hidden="true"><span /></div>
      <p>{criterio.fato}</p>
    </article>
  )
}

function SinaisAFavor({ criterios }: { criterios: Criterio[] }) {
  const sinais = criterios.filter((criterio) =>
    criterio.veredito === 'favor' && !['vendedor', 'fotos'].includes(criterio.id))

  return (
    <section className="ga-secao ga-entra">
      <div className="ga-titulo-secao">
        <IconeRedondo icon={CheckCircle} />
        <div>
          <p className="ga-sobretitulo">{GT.sinaisReais}</p>
          <h2>{T.porQueVale}</h2>
        </div>
      </div>
      {sinais.length > 0 ? (
        <div className="ga-grade-sinais">
          {sinais.map((criterio) => <CartaoSinal key={criterio.id} criterio={criterio} />)}
        </div>
      ) : (
        <p className="ga-linha-calma"><Question size={18} weight="duotone" aria-hidden="true" /> {GT.semSinalReal}</p>
      )}
    </section>
  )
}

function ReguaKm({ carro, criterio }: { carro: Anuncio; criterio: Criterio | undefined }) {
  if (!criterio) return null
  const idade = carro.ano === null ? null : new Date().getFullYear() - carro.ano
  const porAno = carro.km !== null && idade !== null && idade >= IDADE_MINIMA_ANOS ? carro.km / idade : null
  const maximo = Math.max(18000, porAno ? porAno * 1.15 : 0)
  const posicao = (valor: number) => `${limitar(valor / maximo * 100, 3, 97)}%`

  return (
    <article className="ga-painel ga-painel--largo">
      <div className="ga-painel__topo">
        <div>
          <p className="ga-sobretitulo">{criterio.titulo}</p>
          <h3>{criterio.resultado}</h3>
        </div>
        <IconeRedondo icon={Gauge} tom={criterio.veredito === 'atencao' ? 'amarelo' : 'agua'} />
      </div>
      {porAno !== null ? (
        <div className="ga-regua-km" aria-label={GT.reguaKm}>
          <div className="ga-regua-km__trilho">
            <span className="ga-regua-km__faixa-boa" style={{ width: posicao(KM_POR_ANO_BAIXO) }} />
            <span className="ga-marca ga-marca--limite" style={{ left: posicao(KM_POR_ANO_BAIXO) }} />
            <span className="ga-marca ga-marca--media" style={{ left: posicao(12000) }} />
            <span className="ga-marca ga-marca--carro" style={{ left: posicao(porAno) }} />
          </div>
          <div className="ga-regua-km__legendas">
            <span style={{ left: posicao(KM_POR_ANO_BAIXO) }}>{GT.limiteSinal}<b>8 mil</b></span>
            <span style={{ left: posicao(12000) }}>{GT.mediaReferencia}<b>12 mil</b></span>
            <span className="is-carro" style={{ left: posicao(porAno) }}>{GT.esteCarro}<b>{(porAno / 1000).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} mil</b></span>
          </div>
        </div>
      ) : (
        <p className="ga-vazio">{GT.reguaSemBase}</p>
      )}
      <p className="ga-conta">{criterio.fato}</p>
    </article>
  )
}

function FaixaPreco({ carro, criterio, mercado }: { carro: Anuncio; criterio: Criterio | undefined; mercado: Mercado | null | undefined }) {
  if (!criterio) return null
  const iguais = totalDeIguais(criterio, mercado)
  const temFaixa = mercado && carro.preco !== null
  const amplitude = mercado ? mercado.maximo - mercado.minimo : 0
  const posicao = temFaixa && amplitude > 0
    ? limitar((carro.preco! - mercado.minimo) / amplitude * 100, 2, 98)
    : 50
  const progresso = limitar(((iguais ?? 0) / AMOSTRA_MINIMA) * 100, 0, 100)

  return (
    <article className="ga-painel">
      <div className="ga-painel__topo">
        <div>
          <p className="ga-sobretitulo">{criterio.titulo}</p>
          <h3>{criterio.resultado}</h3>
        </div>
        <IconeRedondo icon={Tag} tom={criterio.veredito === 'atencao' ? 'amarelo' : 'agua'} />
      </div>
      {temFaixa ? (
        <div className="ga-faixa-preco" aria-label={GT.faixaPreco}>
          <div className="ga-faixa-preco__valores">
            <span>{reais(mercado.minimo)}</span>
            <span>{reais(mercado.mediana)}</span>
            <span>{reais(mercado.maximo)}</span>
          </div>
          <div className="ga-faixa-preco__trilho">
            <span className="ga-faixa-preco__mediana" />
            <span className="ga-faixa-preco__carro" style={{ left: `${posicao}%` }} />
          </div>
          <div className="ga-faixa-preco__nomes">
            <span>{GT.minimo}</span><span>{GT.mediana}</span><span>{GT.maximo}</span>
          </div>
          <p className="ga-faixa-preco__destaque">
            {GT.precoDesteCarro} <b>{carro.preco === null ? GT.precoAusente : reais(carro.preco)}</b>
          </p>
        </div>
      ) : (
        <div className="ga-progresso">
          <div className="ga-progresso__texto">
            <span>{GT.baseDeComparacao}</span>
            <b>{iguais === null ? GT.semContagem : `${iguais} de ${AMOSTRA_MINIMA}`}</b>
          </div>
          <div className="ga-progresso__trilho"><span style={{ width: `${progresso}%` }} /></div>
          <p>{GT.dicaVerMais}</p>
        </div>
      )}
      <p className="ga-conta">{criterio.fato}</p>
    </article>
  )
}

function Margem({ criterio }: { criterio: Criterio | undefined }) {
  if (!criterio) return null
  const semBase = criterio.veredito === 'semdado'

  return (
    <article className={`ga-painel ${semBase ? 'ga-painel--apagado' : ''}`}>
      <div className="ga-painel__topo">
        <div>
          <p className="ga-sobretitulo">{criterio.titulo}</p>
          <h3>{criterio.resultado}</h3>
        </div>
        <IconeRedondo icon={CurrencyCircleDollar} tom={criterio.veredito === 'atencao' ? 'amarelo' : semBase ? 'cinza' : 'agua'} />
      </div>
      {semBase && <p className="ga-vazio">{GT.margemSemBase}</p>}
      <p className="ga-conta">{criterio.fato}</p>
    </article>
  )
}

function LinhaCuidado({ criterio }: { criterio: Criterio }) {
  return (
    <li>
      <IconeRedondo icon={Warning} tom="amarelo" />
      <div>
        <span>{criterio.titulo}</span>
        <strong>{criterio.resultado}</strong>
        <p>{criterio.fato}</p>
      </div>
    </li>
  )
}

function Cuidados({ criterios }: { criterios: Criterio[] }) {
  const alertas = criterios.filter((criterio) => criterio.veredito === 'atencao')
  return (
    <section className="ga-secao ga-entra">
      <div className="ga-titulo-secao">
        <IconeRedondo icon={alertas.length ? ShieldWarning : CheckCircle} tom={alertas.length ? 'amarelo' : 'agua'} />
        <div>
          <p className="ga-sobretitulo">{GT.horaDeConferir}</p>
          <h2>{T.porQueNao}</h2>
        </div>
      </div>
      {alertas.length ? (
        <ul className="ga-alertas">{alertas.map((criterio) => <LinhaCuidado key={criterio.id} criterio={criterio} />)}</ul>
      ) : (
        <p className="ga-linha-calma ga-linha-calma--ok"><CheckCircle size={18} weight="duotone" aria-hidden="true" /> {T.nadaContra}</p>
      )}
    </section>
  )
}

function PecaCompacta({ criterio, icon: Icone }: { criterio: Criterio | undefined; icon: Icon }) {
  if (!criterio) return null
  const alerta = criterio.veredito === 'atencao'
  return (
    <article className={`ga-peca ${alerta ? 'ga-peca--alerta' : ''}`}>
      <IconeRedondo icon={Icone} tom={alerta ? 'amarelo' : 'cinza'} />
      <div>
        <span>{criterio.titulo}</span>
        <strong>{criterio.resultado}</strong>
        <p>{criterio.fato}</p>
      </div>
    </article>
  )
}

function Apoios({ criterios, carro }: { criterios: Criterio[]; carro: Anuncio }) {
  const vendedor = criterioDe(criterios, 'vendedor')
  const iconeVendedor = carro.anunciante_profissional ? Storefront : User
  return (
    <section className="ga-secao ga-entra">
      <div className="ga-titulo-secao">
        <IconeRedondo icon={Camera} tom="cinza" />
        <div>
          <p className="ga-sobretitulo">{GT.semVirarNota}</p>
          <h2>{T.naoMedido}</h2>
        </div>
      </div>
      <div className="ga-grade-pecas">
        <PecaCompacta criterio={vendedor} icon={iconeVendedor} />
        <PecaCompacta criterio={criterioDe(criterios, 'fotos')} icon={Camera} />
        <PecaCompacta criterio={criterioDe(criterios, 'risco')} icon={ShieldWarning} />
      </div>
    </section>
  )
}

export function Garimpar({
  a, analise, onFechar, onFipe, onBuscarIguais,
}: {
  a: Anuncio
  analise: Analise | undefined
  onFechar: () => void
  onFipe: (anuncio: Anuncio) => void
  onBuscarIguais: (anuncio: Anuncio) => void
}) {
  const fechar = useRef<HTMLButtonElement>(null)
  const original = useRef(a)
  const [carro, setCarro] = useState(a)

  // A FIPE vem do quadro Referência de preço da página do anúncio, lida pela FichaAnuncio.
  const chegouDetalhe = useCallback((detalhe: DetalheAnuncio) => {
    const fipe = fipeDaOlx(original.current.preco, detalhe.referencia_preco?.fipe)
    if (!fipe) return
    const atualizado = { ...original.current, fipe }
    setCarro(atualizado)
    onFipe(atualizado)
  }, [onFipe])

  useEffect(() => {
    fechar.current?.focus()
    const antes = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const tecla = (evento: KeyboardEvent) => {
      if (evento.key === 'Escape') onFechar()
    }
    window.addEventListener('keydown', tecla)
    return () => {
      window.removeEventListener('keydown', tecla)
      document.body.style.overflow = antes
    }
  }, [onFechar])

  const criterios = analise?.criterios ?? []
  const preco = criterioDe(criterios, 'preco')
  const margem = criterioDe(criterios, 'margem')
  const km = criterioDe(criterios, 'km')
  const recencia = criterioDe(criterios, 'recencia')

  return (
    <div role="dialog" aria-modal="true" aria-labelledby="ga-titulo-tela" className="ga-tela">
      <header className="ga-cabecalho">
        <div className="ga-cabecalho__miolo">
          <button ref={fechar} type="button" onClick={onFechar} className="ga-botao-voltar">
            <ArrowLeft size={18} weight="bold" aria-hidden="true" />
            {T.voltar}
          </button>
          <p id="ga-titulo-tela"><Sparkle size={15} weight="duotone" aria-hidden="true" /> {GT.leituraOportunidade}</p>
          <a href={a.url} target="_blank" rel="noopener noreferrer" className="ga-link-anuncio ga-link-anuncio--topo">
            {T.verAnuncio}
            <ArrowSquareOut size={17} weight="bold" aria-hidden="true" />
          </a>
        </div>
      </header>

      <main className="ga-conteudo">
        <Hero carro={carro} recencia={recencia} />
        <Veredito
          carro={carro}
          analise={analise}
          preco={preco}
          onBuscarIguais={() => onBuscarIguais(carro)}
        />
        <SinaisAFavor criterios={criterios} />

        <section className="ga-secao ga-entra">
          <div className="ga-titulo-secao">
            <IconeRedondo icon={Gauge} />
            <div>
              <p className="ga-sobretitulo">{GT.contaAberta}</p>
              <h2>{T.numeros}</h2>
            </div>
          </div>
          <div className="ga-grade-medidas">
            <ReguaKm carro={carro} criterio={km} />
            <FaixaPreco carro={carro} criterio={preco} mercado={analise?.mercado} />
            <Margem criterio={margem} />
          </div>
        </section>

        <FichaAnuncio anuncio={original.current} onDetalhe={chegouDetalhe} />
        <Cuidados criterios={criterios} />
        <Apoios criterios={criterios} carro={carro} />
        <p className="ga-fora">{T.aindaNaoEntra}</p>
      </main>

      <div className="ga-acao-movel">
        <a href={a.url} target="_blank" rel="noopener noreferrer" className="ga-link-anuncio">
          {T.verAnuncio}
          <ArrowSquareOut size={18} weight="bold" aria-hidden="true" />
        </a>
      </div>
    </div>
  )
}
