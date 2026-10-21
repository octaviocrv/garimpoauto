// A análise do Garimpar: olha um carro como quem vai revender e devolve critérios que dá pra conferir.
// Regras da casa:
// 1) o preço só é comparado com a referência que a OLX mostra na página do anúncio (FIPE, preço
//    médio OLX e a régua dos carros parecidos). O Garimpo não monta comparação própria.
// 2) só nasce de dado que a OLX devolveu, e dado faltando vira "sem dado", nunca chute nem zero
// 3) cada critério diz de onde veio a conta (`fato`), pra pessoa conferir e discordar
// 4) antes de abrir o Garimpar só existem os critérios da lista. O nível só sai com a página lida.
// Não existe nota. O nível (Quente ou Boa) sai de regras simples, escritas aqui embaixo.
import type { Anuncio, DetalheAnuncio, ReferenciaPreco } from '../types'
import { IDADE_MINIMA_ANOS, KM_MINIMO_CONFIAVEL, KM_POR_ANO_BAIXO, RECENTE_MINUTOS, dataCurta, minutosDesde, prefixoData } from './sinais'

export type Veredito = 'favor' | 'atencao' | 'neutro' | 'semdado'
export type IdCriterio =
  | 'fipe' | 'media' | 'regua' | 'km' | 'recencia' | 'vendedor' | 'fotos' | 'risco'
  | 'garantias' | 'pendencias' | 'opcionais' | 'repetido'
export type Nivel = 'quente' | 'boa'

export interface Criterio {
  id: IdCriterio
  titulo: string // o nome do critério
  veredito: Veredito
  resultado: string // o que achamos, em poucas palavras
  fato: string // de onde veio a conta
}

export interface Analise {
  nivel: Nivel | null
  resumo: string | null // a frase curta do card, só quando tem nível
  motivo: string // por que tem ou não tem nível
  criterios: Criterio[]
  lido: boolean // a página do anúncio já foi lida (é dela que vem a referência da OLX)
  referencia: boolean // a OLX mostrou FIPE ou preço médio pra comparar
}

export const ABAIXO_BOM = 0.1 // a partir de 10% abaixo da FIPE ou da média OLX conta a favor
export const PRECO_SUSPEITO = 0.3 // 30% abaixo ou mais é golpe, leilão ou erro até prova em contrário
export const FOLGA_NEUTRA = 0.02 // até 2% pra cima ou pra baixo é "na linha"
export const NOTA_LOJA_BAIXA = 3.5
export const FOTOS_MINIMAS = 3
export const FOTOS_BOAS = 6

const reais = (v: number) => `R$ ${Math.round(v).toLocaleString('pt-BR')}`
const pct = (v: number) => `${Math.round(v * 100)}%`
const mil = (v: number) => (v / 1000).toLocaleString('pt-BR', { maximumFractionDigits: 1 })
const num = (v: number) => v.toLocaleString('pt-BR')

const semAcento = (s: string) => s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/-/g, ' ')
const NEGADO = /\b(sem|nao|nunca|livre de|zero)\s+(de\s+)?(leilao|sinistr\w*|batid\w*|colisao)\b/g
const RISCO = /\b(leilao|sinistr\w*|salvado|batido|batida|colisao|recuperad[oa]|sucata|repasse|a quitar|quitar|remarcad\w*|sem documento\w*|so entrada|apenas entrada|ipva atrasado)\b/

// Palavra de risco no texto do anúncio. "Sem leilão" e "nunca bateu" não contam.
export function palavraDeRisco(texto: string): string | null {
  const limpo = semAcento(texto).replace(NEGADO, ' ')
  return limpo.match(RISCO)?.[0] ?? null
}

const criterio = (id: IdCriterio, titulo: string, veredito: Veredito, resultado: string, fato: string): Criterio =>
  ({ id, titulo, veredito, resultado, fato })

// Quanto o preço está abaixo da referência. Positivo: abaixo. Negativo: acima.
function diferenca(preco: number | null, referencia: number | null | undefined): number | null {
  if (preco === null || preco <= 0 || !referencia || referencia <= 0) return null
  return 1 - preco / referencia
}

function criterioReferencia(
  id: 'fipe' | 'media', titulo: string, nome: string, d: number | null, valor: number | null | undefined, base: string,
): Criterio {
  if (d === null || !valor) {
    return criterio(id, titulo, 'semdado', `A OLX não mostrou ${nome}`, 'Nem todo anúncio traz esse número na página.')
  }
  const fato = `A OLX mostra ${nome} de ${reais(valor)}. ${base}`
  if (d >= PRECO_SUSPEITO) {
    return criterio(id, titulo, 'atencao', `${pct(d)} abaixo, baixo demais`, `${fato} Tão abaixo costuma ser golpe, leilão ou erro de digitação. Confere antes de falar com o vendedor.`)
  }
  if (d >= ABAIXO_BOM) return criterio(id, titulo, 'favor', `${pct(d)} abaixo ${nome === 'a FIPE' ? 'da FIPE' : 'da média OLX'}`, `${fato} Comprar bem abaixo deixa espaço pra negociar e revender.`)
  if (d > FOLGA_NEUTRA) return criterio(id, titulo, 'neutro', `${pct(d)} abaixo ${nome === 'a FIPE' ? 'da FIPE' : 'da média OLX'}`, `${fato} Pouca folga pra revenda.`)
  if (d >= -FOLGA_NEUTRA) return criterio(id, titulo, 'neutro', nome === 'a FIPE' ? 'Na linha da FIPE' : 'Na linha da média OLX', `${fato} Sem folga, só vale se negociar.`)
  return criterio(id, titulo, 'atencao', `${pct(-d)} acima ${nome === 'a FIPE' ? 'da FIPE' : 'da média OLX'}`, `${fato} Comprando acima fica difícil revender com lucro.`)
}

// Em que terço da régua da OLX o preço cai. 0 é o dos mais baratos.
function tercoDaRegua(r: ReferenciaPreco | null, preco: number | null): number | null {
  const p = r?.preco_anuncio ?? preco
  if (!r || p === null || r.corte_baixo === null || r.corte_alto === null || r.corte_alto < r.corte_baixo) return null
  return p <= r.corte_baixo ? 0 : p <= r.corte_alto ? 1 : 2
}

function criterioRegua(r: ReferenciaPreco | null, terco: number | null): Criterio {
  const t = 'Onde o preço fica na régua da OLX'
  if (!r || terco === null) return criterio('regua', t, 'semdado', 'A OLX não mostrou a régua', 'Nem todo anúncio traz a régua de preço na página.')
  const quantos = r.carros !== null ? `${num(r.carros)} carros parecidos` : 'os carros parecidos'
  const fato = `A OLX compara com ${quantos}. O primeiro terço vai até ${reais(r.corte_baixo as number)} e o último começa em ${reais(r.corte_alto as number)}.`
  if (terco === 0) return criterio('regua', t, 'favor', 'Entre os mais baratos', `${fato} Comprar no começo da régua facilita a revenda.`)
  if (terco === 1) return criterio('regua', t, 'neutro', 'No meio da régua', fato)
  return criterio('regua', t, 'atencao', 'Entre os mais caros', `${fato} No fim da régua sobra pouco pra revender.`)
}

function criterioKm(km: number | null, ano: number | null, agora: number): Criterio {
  const t = 'Quilometragem'
  if (km === null || ano === null) return criterio('km', t, 'semdado', 'Km ou ano não informado', 'Sem os dois não dá pra medir o uso do carro.')
  const idade = new Date(agora).getFullYear() - ano
  const texto = `${num(km)} km`
  if (idade >= IDADE_MINIMA_ANOS && km < KM_MINIMO_CONFIAVEL) {
    return criterio('km', t, 'atencao', 'Km parece errado', `${texto} num carro de ${idade} anos costuma ser campo mal preenchido. Pergunta o km real.`)
  }
  if (idade < IDADE_MINIMA_ANOS) {
    const porAnoNovo = km / Math.max(1, idade)
    return criterio('km', t, 'neutro', `${mil(porAnoNovo)} mil km por ano`, `${texto} num carro ${ano}, contado como 1 ano de uso. Em carro de menos de ${IDADE_MINIMA_ANOS} anos o km por ano pesa menos, por isso não conta a favor nem contra.`)
  }
  const porAno = km / idade
  const fato = `${texto} em ${idade} anos dá ${mil(porAno)} mil km por ano, e a média fica perto de 12 mil.`
  if (porAno <= KM_POR_ANO_BAIXO) return criterio('km', t, 'favor', 'Pouco km pro ano', `${fato} Carro pouco rodado revende melhor.`)
  return criterio('km', t, 'neutro', `${mil(porAno)} mil km por ano`, fato)
}

function criterioRecencia(a: Anuncio, agora: number): Criterio {
  const t = 'Frescor do anúncio'
  const min = minutosDesde(a.anunciado_em, agora)
  if (min === null) return criterio('recencia', t, 'semdado', 'Sem data do anúncio', 'A OLX não mandou a data.')
  const quando = `${prefixoData(a)} ${dataCurta(a.anunciado_em, agora)}`
  if (min < RECENTE_MINUTOS) return criterio('recencia', t, 'favor', quando, 'Anúncio de poucas horas. Quem chega primeiro costuma negociar melhor.')
  return criterio('recencia', t, 'neutro', quando, `Só conta a favor nas primeiras ${RECENTE_MINUTOS / 60} horas.`)
}

function criterioVendedor(a: Anuncio): Criterio {
  const t = 'Vendedor'
  if (a.anunciante_profissional === null) return criterio('vendedor', t, 'semdado', 'Tipo de vendedor não informado', 'A OLX não disse se é loja ou particular.')
  if (!a.anunciante_profissional) return criterio('vendedor', t, 'favor', 'Particular', 'Sem margem de loja embutida no preço, e o dono costuma negociar mais.')
  const nota = a.nota_anunciante
  if (nota !== null && nota < NOTA_LOJA_BAIXA) {
    return criterio('vendedor', t, 'atencao', `Loja com nota ${nota.toLocaleString('pt-BR')}`, `Nota do Google abaixo de ${NOTA_LOJA_BAIXA.toLocaleString('pt-BR')}.`)
  }
  return criterio('vendedor', t, 'neutro', 'Loja', nota !== null ? `Nota ${nota.toLocaleString('pt-BR')} no Google.` : 'Loja sem nota no Google.')
}

function criterioFotos(a: Anuncio): Criterio {
  const t = 'Fotos'
  const n = a.imagens.length
  if (n === 0) return criterio('fotos', t, 'atencao', 'Anúncio sem foto', 'Sem foto não dá pra avaliar o estado do carro.')
  if (n < FOTOS_MINIMAS) return criterio('fotos', t, 'atencao', `Só ${n} ${n === 1 ? 'foto' : 'fotos'}`, 'Pouca foto costuma esconder o estado do carro.')
  if (n >= FOTOS_BOAS) return criterio('fotos', t, 'favor', `${n} fotos`, 'Dá pra avaliar o estado do carro antes de ir ver.')
  return criterio('fotos', t, 'neutro', `${n} fotos`, 'Quantidade normal.')
}

function criterioRisco(a: Anuncio, d: DetalheAnuncio | null): Criterio {
  const t = 'Palavras de risco'
  const noTitulo = palavraDeRisco(`${a.titulo ?? ''} ${a.modelo_original ?? ''}`)
  const naDescricao = d?.descricao ? palavraDeRisco(d.descricao) : null
  const aviso = 'Leilão, sinistro, repasse e parecidos pedem cuidado redobrado na revenda.'
  if (noTitulo) return criterio('risco', t, 'atencao', `O título fala em ${noTitulo}`, aviso)
  if (naDescricao) return criterio('risco', t, 'atencao', `A descrição fala em ${naDescricao}`, aviso)
  if (!d) return criterio('risco', t, 'neutro', 'Título sem palavra de risco', 'A descrição entra quando a página do anúncio abre.')
  return criterio('risco', t, 'neutro', 'Nenhuma palavra de risco', d.descricao ? 'Lemos o título e a descrição do anúncio.' : 'Lemos o título. O anúncio veio sem descrição.')
}

// O que o anunciante marcou em Outras características na OLX.
const BOAS = ['ipva pago', 'unico dono', 'quitado', 'revis', 'garantia', 'manual', 'chave reserva']
const RUINS = ['leilao', 'multa', 'financiado']
const negada = (s: string) => /^(sem|nao|nunca)\b/.test(s)

function marcadas(outras: string[], chaves: string[]): string[] {
  return outras.filter((o) => {
    const s = semAcento(o)
    return !negada(s) && chaves.some((k) => s.includes(k))
  })
}

// "Único dono" vira "único dono" no meio da frase, mas "IPVA pago" fica como está.
const minuscula = (s: string) => (/^\p{Lu}\p{Ll}/u.test(s) ? s[0].toLowerCase() + s.slice(1) : s)

const juntar = (itens: string[]) => {
  const lista = itens.map((i, n) => (n === 0 ? i : minuscula(i)))
  return lista.length > 1 ? `${lista.slice(0, -1).join(', ')} e ${lista[lista.length - 1]}` : lista[0]
}

function criterioGarantias(outras: string[]): Criterio | null {
  const boas = marcadas(outras, BOAS)
  if (!boas.length) return null
  return criterio('garantias', 'O que o anúncio garante', 'favor', juntar(boas), 'Marcado pelo anunciante na OLX. Papel em dia e histórico conhecido fazem o carro sair mais rápido na revenda.')
}

function criterioPendencias(outras: string[]): Criterio | null {
  const ruins = marcadas(outras, RUINS)
  if (!ruins.length) return null
  return criterio('pendencias', 'Pendências do anúncio', 'atencao', juntar(ruins), 'Marcado pelo anunciante na OLX. Leilão derruba o preço de revenda, e multa ou financiamento precisam ser resolvidos antes da transferência.')
}

// Ar, direção, vidro e trava elétrica. É o "completo" que o comprador da revenda procura.
function criterioOpcionais(d: DetalheAnuncio): Criterio | null {
  const ops = d.opcionais.map(semAcento)
  const tem = (k: string) => ops.some((o) => o.includes(k))
  const direcao = d.detalhes.direcao ? semAcento(d.detalhes.direcao) : ''
  const direcaoBoa = tem('direcao') || (direcao !== '' && !direcao.includes('mecanic'))
  if (!(tem('ar condicionado') && tem('vidro') && tem('trava') && direcaoBoa)) return null
  return criterio('opcionais', 'Opcionais', 'favor', 'Carro completo', 'Ar condicionado, direção, vidro e trava elétrica marcados no anúncio. Carro completo vende mais fácil.')
}

export function analisar(a: Anuncio, detalhe: DetalheAnuncio | null, agora: number): Analise {
  const r = detalhe?.referencia_preco ?? null
  const preco = a.preco ?? r?.preco_anuncio ?? null
  const dFipe = diferenca(preco, r?.fipe)
  const dMedia = diferenca(preco, r?.media_olx)
  const terco = tercoDaRegua(r, preco)
  const lido = detalhe !== null
  const criterios: Criterio[] = []
  if (lido) {
    criterios.push(
      criterioReferencia('fipe', 'Preço comparado à FIPE', 'a FIPE', dFipe, r?.fipe, 'A FIPE é uma referência nacional e o preço real de revenda pode ser outro.'),
      criterioReferencia('media', 'Preço comparado à média da OLX', 'o preço médio', dMedia, r?.media_olx, 'É a média dos carros parecidos anunciados na OLX.'),
      criterioRegua(r, terco),
    )
  }
  criterios.push(
    criterioKm(a.km ?? detalhe?.detalhes.km ?? null, a.ano ?? detalhe?.detalhes.ano ?? null, agora),
    criterioRecencia(a, agora), criterioVendedor(a), criterioFotos(a), criterioRisco(a, detalhe),
  )
  if (detalhe) {
    for (const c of [criterioGarantias(detalhe.outras), criterioOpcionais(detalhe), criterioPendencias(detalhe.outras)]) {
      if (c) criterios.push(c)
    }
  }
  if (a.repetido_de) {
    criterios.push(criterio('repetido', 'Anúncio repetido', 'atencao', 'Já aparece em outro anúncio', 'Mesmo carro, preço, km e cidade de outro anúncio da lista.'))
  }

  const refs = [
    { nome: 'da FIPE', d: dFipe },
    { nome: 'da média OLX', d: dMedia },
  ].filter((x): x is { nome: string; d: number } => x.d !== null)
  const referencia = refs.length > 0
  const por = (id: IdCriterio) => criterios.find((c) => c.id === id)
  const suspeito = refs.some((x) => x.d >= PRECO_SUSPEITO)
  const leilao = detalhe ? marcadas(detalhe.outras, ['leilao']).length > 0 : false
  const grave = suspeito || leilao || (['risco', 'repetido'] as const).some((id) => por(id)?.veredito === 'atencao')
  const semAlerta = criterios.every((c) => c.veredito !== 'atencao')
  const abaixo = refs.filter((x) => x.d > FOLGA_NEUTRA)
  const acima = refs.filter((x) => x.d < -FOLGA_NEUTRA)
  const textoAbaixo = juntar(abaixo.map((x) => `${pct(x.d)} abaixo ${x.nome}`))

  let nivel: Nivel | null = null
  let motivo: string
  if (!lido) {
    motivo = 'O veredito sai da referência de preço da OLX. Assim que a página do anúncio abrir, ele aparece aqui.'
  } else if (preco === null) {
    motivo = 'O anúncio não informou o preço, então não tem como comparar com a referência da OLX.'
  } else if (!referencia) {
    motivo = 'A OLX não mostrou FIPE nem preço médio pra este anúncio, então o Garimpo não arrisca um veredito.'
  } else if (suspeito) {
    motivo = 'Preço muito abaixo da referência da OLX. Confere bem antes, pode ser leilão, problema de documento ou golpe.'
  } else if (grave) {
    motivo = 'Tem um alerta forte (palavra de risco, leilão ou anúncio repetido), então o Garimpo não destaca.'
  } else if (abaixo.length === refs.length) {
    const forte = abaixo.some((x) => x.d >= ABAIXO_BOM)
    if (forte && terco === 0 && semAlerta) {
      nivel = 'quente'
      motivo = `${textoAbaixo}, entre os mais baratos da régua da OLX e sem nenhum alerta. Sobra espaço pra negociar e revender.`
    } else {
      nivel = 'boa'
      motivo = `${textoAbaixo} e nenhum alerta forte. Pra ser Quente precisa ficar ${pct(ABAIXO_BOM)} abaixo, no começo da régua da OLX e sem nenhum alerta.`
    }
  } else if (abaixo.length > 0) {
    motivo = `${textoAbaixo}, mas a outra referência da OLX não confirma. Fica de olho e negocia.`
  } else if (acima.length > 0) {
    motivo = 'Preço acima da referência da OLX. Sem folga pra revender, só vale se o vendedor baixar.'
  } else {
    motivo = 'Preço na linha da referência da OLX. Pouca folga pra revenda, só vale se negociar.'
  }
  const melhor = abaixo.reduce<{ nome: string; d: number } | null>((m, x) => (!m || x.d > m.d ? x : m), null)
  const resumo = nivel && melhor ? `${pct(melhor.d)} abaixo ${melhor.nome}` : null
  return { nivel, resumo, motivo, criterios, lido, referencia }
}

// Calcula pros carros que acabaram de chegar, só com o que a lista traz. O nível vem depois,
// quando a pessoa abre o Garimpar e a página do anúncio é lida.
export function analisesDaPagina(novos: Anuncio[], agora: number): Record<string, Analise> {
  const saida: Record<string, Analise> = {}
  for (const a of novos) saida[a.external_id] = analisar(a, null, agora)
  return saida
}
