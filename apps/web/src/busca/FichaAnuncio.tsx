import { useEffect, useRef, useState } from 'react'
import { ArrowClockwise, Article, Car, ChartBar, Info, ListChecks, MapPinLine, SealCheck } from '@phosphor-icons/react'
import type { Anuncio, DetalheAnuncio, FichaDetalhes, LocalAnuncio, ReferenciaPreco } from '../types'
import { ErroBusca, ErroDetalhe, buscarDetalhe } from '../api'
import { T } from './textos'
import { GARIMPAR_TEXTOS as GT, refBase } from './garimparTextos'
import { IconeRedondo } from './IconeRedondo'

type Estado =
  | { fase: 'carregando' }
  | { fase: 'pronto'; detalhe: DetalheAnuncio }
  | { fase: 'erro'; mensagem: string; podeTentar: boolean }

type Linha = [rotulo: string, valor: string | null]

const formatarCep = (cep: string) => (/^\d{8}$/.test(cep) ? `${cep.slice(0, 5)}-${cep.slice(5)}` : cep)

function linhasDetalhes(d: FichaDetalhes): Linha[] {
  return [
    [GT.rotuloCategoria, d.categoria],
    [GT.rotuloMarca, d.marca],
    [GT.rotuloModelo, d.modelo],
    [GT.rotuloTipo, d.tipo],
    [GT.rotuloAno, d.ano === null ? null : String(d.ano)],
    [GT.rotuloKm, d.km === null ? null : `${d.km.toLocaleString('pt-BR')} km`],
    [GT.rotuloPotencia, d.potencia],
    [GT.rotuloCombustivel, d.combustivel],
    [GT.rotuloCambio, d.cambio],
    [GT.rotuloDirecao, d.direcao],
    [GT.rotuloCor, d.cor],
    [GT.rotuloPortas, d.portas],
    [GT.rotuloFinalPlaca, d.final_placa],
    [GT.rotuloGnv, d.kit_gnv],
  ]
}

function linhasLocal(l: LocalAnuncio): Linha[] {
  return [
    [GT.rotuloBairro, l.bairro],
    [GT.rotuloCidade, l.cidade],
    [GT.rotuloEstado, l.estado],
    [GT.rotuloCep, l.cep === null ? null : formatarCep(l.cep)],
  ]
}

function Lista({ linhas, vazio }: { linhas: Linha[]; vazio: string }) {
  const presentes = linhas.filter((linha): linha is [string, string] => Boolean(linha[1]))
  if (!presentes.length) return <p className="ga-ficha__vazio">{vazio}</p>
  return (
    <dl className="ga-ficha__lista">
      {presentes.map(([rotulo, valor]) => (
        <div key={rotulo}>
          <dt>{rotulo}</dt>
          <dd>{valor}</dd>
        </div>
      ))}
    </dl>
  )
}

function Marcas({ itens, vazio, rotulo }: { itens: string[]; vazio: string; rotulo: string }) {
  if (!itens.length) return <p className="ga-ficha__vazio">{vazio}</p>
  return (
    <ul className="ga-chips ga-ficha__marcas" aria-label={rotulo}>
      {itens.map((item) => <li key={item} className="ga-chip">{item}</li>)}
    </ul>
  )
}

function Bloco({ titulo, icon, largo, children }: {
  titulo: string; icon: typeof Car; largo?: boolean; children: React.ReactNode
}) {
  return (
    <article className={`ga-ficha__bloco ${largo ? 'ga-ficha__bloco--largo' : ''}`}>
      <h3><IconeRedondo icon={icon} tom="cinza" /> {titulo}</h3>
      {children}
    </article>
  )
}

const reais = (valor: number) => `R$ ${Math.round(valor).toLocaleString('pt-BR')}`

function mesPorExtenso(mes: string | null): string | null {
  const partes = mes?.match(/^(\d{4})-(\d{2})$/)
  if (!partes) return null
  return new Date(Number(partes[1]), Number(partes[2]) - 1, 1).toLocaleDateString('pt-BR', { month: 'long', year: 'numeric' })
}

// Régua em 3 terços iguais, como a da OLX. O pino anda dentro do terço onde o preço cai.
function posicaoNaRegua(r: ReferenciaPreco): { terco: number; posicao: number } | null {
  const { preco_anuncio: preco, corte_baixo: baixo, corte_alto: alto } = r
  if (preco === null || baixo === null || alto === null || alto < baixo) return null
  const faixas: [number | null, number | null][] = [[r.menor, baixo], [baixo, alto], [alto, r.maior]]
  const terco = preco <= baixo ? 0 : preco <= alto ? 1 : 2
  const [inicio, fim] = faixas[terco]
  const dentro = inicio !== null && fim !== null && fim > inicio
    ? Math.min(1, Math.max(0, (preco - inicio) / (fim - inicio)))
    : 0.5
  return { terco, posicao: ((terco + dentro) / 3) * 100 }
}

function ReferenciaDePreco({ r }: { r: ReferenciaPreco }) {
  const regua = posicaoNaRegua(r)
  const caixas: [string, number | null][] = [
    [GT.refPrecoAnuncio, r.preco_anuncio],
    [GT.refMediaOlx, r.media_olx],
    [GT.refFipe, r.fipe],
  ]
  return (
    <Bloco titulo={GT.refTitulo} icon={ChartBar} largo>
      {regua && (
        <div className="ga-ref__regua" role="img" aria-label={`${GT.refRegua}. ${GT.refPrecoAnuncio} ${reais(r.preco_anuncio ?? 0)}`}>
          <span className="ga-ref__pino" style={{ left: `${regua.posicao}%` }} aria-hidden="true" />
          <div className="ga-ref__trechos" aria-hidden="true">
            {[0, 1, 2].map((i) => (
              <span key={i} className={`ga-ref__trecho ga-ref__trecho--${i} ${i === regua.terco ? 'ga-ref__trecho--ativo' : ''}`} />
            ))}
          </div>
          {r.menor !== null && r.maior !== null && (
            <div className="ga-ref__pontas" aria-hidden="true">
              <span>{reais(r.menor)}</span>
              <span>{reais(r.maior)}</span>
            </div>
          )}
        </div>
      )}
      <dl className="ga-ref__caixas">
        {caixas.filter((c): c is [string, number] => c[1] !== null).map(([rotulo, valor]) => (
          <div key={rotulo}>
            <dt>{rotulo}</dt>
            <dd>{reais(valor)}</dd>
          </div>
        ))}
      </dl>
      {(r.carros !== null || r.media_olx !== null) && (
        <p className="ga-ficha__vazio">{refBase(r.carros, mesPorExtenso(r.mes_referencia))}</p>
      )}
      <p className="ga-ficha__vazio">{GT.refFonte}</p>
    </Bloco>
  )
}

function Carregando() {
  return (
    <div role="status" aria-busy="true" className="ga-ficha__carregando">
      <p><span className="ga-ficha__giro" aria-hidden="true" /> {GT.fichaCarregando}</p>
      <div className="ga-ficha__grade" aria-hidden="true">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className={`ga-ficha__bloco ga-ficha__esqueleto ${i === 0 ? 'ga-ficha__bloco--largo' : ''}`}>
            <span /><span /><span />
          </div>
        ))}
      </div>
    </div>
  )
}

// Lê a página do anúncio só aqui, quando a pessoa abre o Garimpar. Nada na lista chama isso.
// onDetalhe avisa o Garimpar quando a leitura chega, inclusive depois de Tentar de novo.
export function FichaAnuncio({ anuncio, onDetalhe }: {
  anuncio: Pick<Anuncio, 'source' | 'external_id' | 'url'>
  onDetalhe?: (detalhe: DetalheAnuncio) => void
}) {
  const { source, external_id, url } = anuncio
  const [estado, setEstado] = useState<Estado>({ fase: 'carregando' })
  const [tentativa, setTentativa] = useState(0)
  const avisar = useRef(onDetalhe)
  avisar.current = onDetalhe

  useEffect(() => {
    let ativo = true
    buscarDetalhe({ source, external_id, url })
      .then((detalhe) => {
        if (!ativo) return
        if (detalhe.source !== source || detalhe.external_id !== external_id) {
          setEstado({ fase: 'erro', mensagem: T.detalheFalhou, podeTentar: true })
          return
        }
        setEstado({ fase: 'pronto', detalhe })
        avisar.current?.(detalhe)
      })
      .catch((e: unknown) => {
        if (!ativo) return
        setEstado({
          fase: 'erro',
          mensagem: e instanceof ErroBusca ? e.message : T.detalheFalhou,
          podeTentar: e instanceof ErroDetalhe ? e.podeTentar : true,
        })
      })
    return () => { ativo = false }
  }, [source, external_id, url, tentativa])

  const tentarDeNovo = () => {
    setEstado({ fase: 'carregando' })
    setTentativa((n) => n + 1)
  }

  return (
    <section className="ga-secao ga-entra ga-ficha" aria-labelledby="ga-ficha-titulo">
      <div className="ga-titulo-secao">
        <IconeRedondo icon={Article} />
        <div>
          <p className="ga-sobretitulo">{GT.fichaSobretitulo}</p>
          <h2 id="ga-ficha-titulo">{GT.fichaTitulo}</h2>
        </div>
      </div>

      {estado.fase === 'carregando' && <Carregando />}

      {estado.fase === 'erro' && (
        <div role="status" className="ga-ficha__erro">
          <p><Info size={18} weight="duotone" aria-hidden="true" /> {estado.mensagem}</p>
          {estado.podeTentar && (
            <button type="button" className="ga-ficha__tentar" onClick={tentarDeNovo}>
              <ArrowClockwise size={17} weight="bold" aria-hidden="true" />
              {GT.fichaTentar}
            </button>
          )}
        </div>
      )}

      {estado.fase === 'pronto' && (
        <div className="ga-ficha__grade">
          {estado.detalhe.referencia_preco && <ReferenciaDePreco r={estado.detalhe.referencia_preco} />}
          <Bloco titulo={GT.fichaDetalhes} icon={Car} largo>
            <Lista linhas={linhasDetalhes(estado.detalhe.detalhes)} vazio={GT.fichaSemDetalhes} />
          </Bloco>
          <Bloco titulo={GT.fichaOpcionais} icon={ListChecks}>
            <Marcas itens={estado.detalhe.opcionais} vazio={GT.fichaSemOpcionais} rotulo={GT.fichaOpcionais} />
          </Bloco>
          <Bloco titulo={GT.fichaOutras} icon={SealCheck}>
            <Marcas itens={estado.detalhe.outras} vazio={GT.fichaSemOutras} rotulo={GT.fichaOutras} />
          </Bloco>
          <Bloco titulo={GT.fichaLocal} icon={MapPinLine} largo>
            <Lista linhas={linhasLocal(estado.detalhe.localizacao)} vazio={GT.fichaSemLocal} />
          </Bloco>
          <Bloco titulo={GT.fichaDescricao} icon={Article} largo>
            {estado.detalhe.descricao ? (
              <p className="ga-ficha__descricao">{estado.detalhe.descricao}</p>
            ) : (
              <p className="ga-ficha__vazio">{GT.fichaSemDescricao}</p>
            )}
          </Bloco>
        </div>
      )}
    </section>
  )
}
