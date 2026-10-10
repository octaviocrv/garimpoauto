// A análise do Garimpar: olha um carro como quem vai revender e devolve critérios que dá pra conferir.
// Regras da casa, as mesmas dos sinais (sinais.ts):
// 1) só nasce de dado que o servidor devolveu, e dado faltando vira "sem dado", nunca chute nem zero
// 2) o preço só é comparado com a lista já carregada
// 3) cada critério diz de onde veio a conta (`fato`), pra pessoa conferir e discordar
// 4) a FIPE de exemplo nunca entra aqui. Quando a FIPE real chegar, ela vira outra referência de margem.
// Não existe nota. O nível (Quente ou Boa) sai de regras simples, escritas aqui embaixo.
import type { Anuncio } from '../types'
import {
  AMOSTRA_MINIMA, IDADE_MINIMA_ANOS, KM_MINIMO_CONFIAVEL, KM_POR_ANO_BAIXO, RECENTE_MINUTOS,
  chave, dataCurta, mediana, minutosDesde, prefixoData,
} from './sinais'

export type Veredito = 'favor' | 'atencao' | 'neutro' | 'semdado'
export type IdCriterio = 'preco' | 'margem' | 'km' | 'recencia' | 'vendedor' | 'fotos' | 'risco' | 'repetido'
export type Nivel = 'quente' | 'boa'

export interface Criterio {
  id: IdCriterio
  titulo: string // o nome do critério
  veredito: Veredito
  resultado: string // o que achamos, em poucas palavras
  fato: string // de onde veio a conta
}

export interface Mercado {
  n: number // carros iguais (marca, modelo e ano) já carregados
  mediana: number
  minimo: number
  maximo: number
  kmMediana: number | null
}

export interface Margem {
  bruta: number // mediana menos preço
  custo: number // estimativa nossa de reparo e transferência
  estimada: number // bruta menos custo
}

export interface Analise {
  nivel: Nivel | null
  resumo: string | null // a frase curta do card, só quando tem nível
  motivo: string // por que tem ou não tem nível
  criterios: Criterio[]
  mercado: Mercado | null
  margem: Margem | null
}

export const CUSTO_REVENDA = 0.05 // reparo e transferência, em % da mediana. Estimativa nossa, não é dado
export const MARGEM_BOA = { pct: 0.05, reais: 2000 }
export const MARGEM_QUENTE = { pct: 0.1, reais: 3000 }
export const FAVORES_PARA_QUENTE = 2 // pontos a favor além do preço e da margem
export const PRECO_BOM = 0.1 // a partir de 10% abaixo da mediana conta a favor
export const PRECO_SUSPEITO = 0.3 // 30% abaixo ou mais é golpe, leilão ou erro até prova em contrário
export const KM_ABAIXO_DOS_IGUAIS = 0.7
export const KM_ACIMA_DOS_IGUAIS = 1.3
export const NOTA_LOJA_BAIXA = 3.5
export const FOTOS_MINIMAS = 3
export const FOTOS_BOAS = 6

const reais = (v: number) => `R$ ${Math.round(v).toLocaleString('pt-BR')}`
const aprox = (v: number) => reais(Math.round(v / 100) * 100)
const pct = (v: number) => `${Math.round(v * 100)}%`
const mil = (v: number) => (v / 1000).toLocaleString('pt-BR', { maximumFractionDigits: 1 })
const num = (v: number) => v.toLocaleString('pt-BR')

const semAcento = (s: string) => s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
const NEGADO = /\b(sem|nao|nunca|livre de|zero)\s+(de\s+)?(leilao|sinistr\w*|batid\w*|colisao)\b/g
const RISCO = /\b(leilao|sinistr\w*|salvado|batido|batida|colisao|recuperad[oa]|sucata|repasse|a quitar|quitar|remarcad\w*|sem documento\w*|so entrada|apenas entrada|ipva atrasado)\b/

// Palavra de risco no texto que a gente tem (título e modelo). "Sem leilão" e "nunca bateu" não contam.
export function palavraDeRisco(texto: string): string | null {
  const limpo = semAcento(texto).replace(NEGADO, ' ')
  return limpo.match(RISCO)?.[0] ?? null
}

function mercadoDe(a: Anuncio, grupos: Map<string, Anuncio[]>): { mercado: Mercado | null; iguais: number } {
  const k = chave(a)
  const iguais = k ? (grupos.get(k) ?? []).filter((x) => x.preco !== null && x.preco > 0) : []
  if (iguais.length < AMOSTRA_MINIMA) return { mercado: null, iguais: iguais.length }
  const precos = iguais.map((x) => x.preco as number)
  const kms = iguais.map((x) => x.km).filter((v): v is number => v !== null && v >= KM_MINIMO_CONFIAVEL)
  return {
    iguais: iguais.length,
    mercado: {
      n: iguais.length, mediana: mediana(precos), minimo: Math.min(...precos), maximo: Math.max(...precos),
      kmMediana: kms.length >= AMOSTRA_MINIMA ? mediana(kms) : null,
    },
  }
}

const criterio = (id: IdCriterio, titulo: string, veredito: Veredito, resultado: string, fato: string): Criterio =>
  ({ id, titulo, veredito, resultado, fato })

function criterioPreco(a: Anuncio, m: Mercado | null, iguais: number): Criterio {
  const t = 'Preço contra o mercado'
  if (a.preco === null || a.preco <= 0) return criterio('preco', t, 'semdado', 'Preço não informado', 'Sem preço não tem como comparar.')
  if (!m) {
    const fato = chave(a)
      ? `Só ${iguais} ${a.modelo} ${a.ano} carregados e preciso de ${AMOSTRA_MINIMA} pra comparar. Carrega mais carros com Ver mais.`
      : 'O anúncio veio sem modelo ou sem ano, então não dá pra achar carros iguais.'
    return criterio('preco', t, 'semdado', 'Poucos carros iguais pra comparar', fato)
  }
  const d = 1 - a.preco / m.mediana
  const fato = `A mediana de ${m.n} ${a.modelo} ${a.ano} carregados é ${reais(m.mediana)}, indo de ${reais(m.minimo)} a ${reais(m.maximo)}.`
  if (d >= PRECO_SUSPEITO) {
    return criterio('preco', t, 'atencao', `Preço ${pct(d)} abaixo, baixo demais`, `${fato} Tão abaixo do mercado costuma ser golpe, leilão ou erro de digitação. Confere antes de falar com o vendedor.`)
  }
  if (d >= PRECO_BOM) return criterio('preco', t, 'favor', `Preço ${pct(d)} abaixo do mercado`, fato)
  if (d > 0.02) return criterio('preco', t, 'neutro', `${pct(d)} abaixo do mercado`, fato)
  if (d >= -0.02) return criterio('preco', t, 'neutro', 'No preço do mercado', fato)
  return criterio('preco', t, 'atencao', `Preço ${pct(-d)} acima do mercado`, fato)
}

function calcularMargem(a: Anuncio, m: Mercado | null): Margem | null {
  if (!m || a.preco === null || a.preco <= 0) return null
  const custo = m.mediana * CUSTO_REVENDA
  return { bruta: m.mediana - a.preco, custo, estimada: m.mediana - a.preco - custo }
}

const margemAtinge = (g: Margem, m: Mercado, minimo: { pct: number; reais: number }) =>
  g.estimada >= minimo.reais && g.estimada / m.mediana >= minimo.pct

function criterioMargem(a: Anuncio, m: Mercado | null, g: Margem | null): Criterio {
  const t = 'Margem estimada de revenda'
  if (!m || !g || a.preco === null) return criterio('margem', t, 'semdado', 'Sem margem calculada', 'A margem precisa da comparação de preço, que ainda não tem dado suficiente.')
  const conta = `${reais(m.mediana)} de mercado, menos ${reais(a.preco)} de preço, menos ${reais(g.custo)} de custo (${pct(CUSTO_REVENDA)} pra reparo e transferência, estimativa nossa).`
  if (a.preco / m.mediana <= 1 - PRECO_SUSPEITO) {
    return criterio('margem', t, 'atencao', `Margem de ${aprox(g.estimada)} não é confiável`, `${conta} O preço está baixo demais pra acreditar nessa margem.`)
  }
  if (margemAtinge(g, m, MARGEM_BOA)) return criterio('margem', t, 'favor', `Sobram cerca de ${aprox(g.estimada)}`, conta)
  if (g.estimada > 0) return criterio('margem', t, 'atencao', `Margem apertada, cerca de ${aprox(g.estimada)}`, conta)
  return criterio('margem', t, 'atencao', 'Não sobra margem', conta)
}

function criterioKm(a: Anuncio, m: Mercado | null, agora: number): Criterio {
  const t = 'Quilometragem'
  if (a.km === null || a.ano === null) return criterio('km', t, 'semdado', 'Km ou ano não informado', 'Sem os dois não dá pra medir o uso do carro.')
  const idade = new Date(agora).getFullYear() - a.ano
  const km = `${num(a.km)} km`
  if (idade >= IDADE_MINIMA_ANOS && a.km < KM_MINIMO_CONFIAVEL) {
    return criterio('km', t, 'atencao', 'Km parece errado', `${km} num carro de ${idade} anos costuma ser campo mal preenchido. Pergunta o km real.`)
  }
  const partes: string[] = []
  let porAno: number | null = null
  if (idade >= IDADE_MINIMA_ANOS) {
    porAno = a.km / idade
    partes.push(`${km} em ${idade} anos dá ${mil(porAno)} mil km por ano, e a média fica perto de 12 mil.`)
  } else {
    partes.push(`${km}. Em carro de menos de ${IDADE_MINIMA_ANOS} anos o km por ano não diz nada.`)
  }
  let contraIguais: 'menos' | 'mais' | null = null
  if (m?.kmMediana) {
    partes.push(`A mediana de km dos iguais é ${num(Math.round(m.kmMediana))}.`)
    if (a.km <= m.kmMediana * KM_ABAIXO_DOS_IGUAIS) contraIguais = 'menos'
    else if (a.km >= m.kmMediana * KM_ACIMA_DOS_IGUAIS) contraIguais = 'mais'
  }
  const fato = partes.join(' ')
  if (porAno !== null && porAno <= KM_POR_ANO_BAIXO) return criterio('km', t, 'favor', 'Pouco km pro ano', fato)
  if (contraIguais === 'menos') return criterio('km', t, 'favor', 'Menos km que os iguais', fato)
  if (contraIguais === 'mais') return criterio('km', t, 'atencao', 'Rodou mais que a maioria dos iguais', fato)
  return criterio('km', t, 'neutro', porAno !== null ? `${mil(porAno)} mil km por ano` : km, fato)
}

function criterioRecencia(a: Anuncio, agora: number): Criterio {
  const t = 'Frescor do anúncio'
  const min = minutosDesde(a.anunciado_em, agora)
  if (min === null) return criterio('recencia', t, 'semdado', 'Sem data do anúncio', 'A fonte não mandou a data.')
  const quando = `${prefixoData(a)} ${dataCurta(a.anunciado_em, agora)}`
  if (min < RECENTE_MINUTOS) return criterio('recencia', t, 'favor', quando, 'Anúncio de poucas horas. Quem chega primeiro costuma negociar melhor.')
  return criterio('recencia', t, 'neutro', quando, `Só conta a favor nas primeiras ${RECENTE_MINUTOS / 60} horas.`)
}

function criterioVendedor(a: Anuncio): Criterio {
  const t = 'Vendedor'
  if (a.anunciante_profissional === null) return criterio('vendedor', t, 'semdado', 'Tipo de vendedor não informado', 'A fonte não disse se é loja ou particular.')
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

function criterioRisco(a: Anuncio): Criterio {
  const t = 'Palavras de risco'
  const achada = palavraDeRisco(`${a.titulo ?? ''} ${a.modelo_original ?? ''}`)
  if (achada) return criterio('risco', t, 'atencao', `O título fala em ${achada}`, 'Leilão, sinistro, repasse e parecidos pedem cuidado redobrado na revenda.')
  return criterio('risco', t, 'neutro', 'Título sem palavra de risco', 'Só o título é lido. A descrição do anúncio ainda não entra na análise.')
}

const NOMES_FAVOR: Partial<Record<IdCriterio, string>> = { km: 'km', recencia: 'anúncio novo', vendedor: 'particular', fotos: 'fotos' }

export function analisar(a: Anuncio, grupos: Map<string, Anuncio[]>, agora: number): Analise {
  const { mercado, iguais } = mercadoDe(a, grupos)
  const margem = calcularMargem(a, mercado)
  const criterios = [
    criterioPreco(a, mercado, iguais), criterioMargem(a, mercado, margem), criterioKm(a, mercado, agora),
    criterioRecencia(a, agora), criterioVendedor(a), criterioFotos(a), criterioRisco(a),
  ]
  if (a.repetido_de) {
    criterios.push(criterio('repetido', 'Anúncio repetido', 'atencao', 'Já aparece em outro anúncio', 'Mesmo carro, preço, km e cidade de outro anúncio da lista.'))
  }
  const por = (id: IdCriterio) => criterios.find((c) => c.id === id)
  const grave = (['risco', 'repetido'] as const).some((id) => por(id)?.veredito === 'atencao')
    || (mercado !== null && a.preco !== null && a.preco / mercado.mediana <= 1 - PRECO_SUSPEITO)
  const semAlerta = criterios.every((c) => c.veredito !== 'atencao')
  const favores = criterios.filter((c) => c.veredito === 'favor' && NOMES_FAVOR[c.id])

  let nivel: Nivel | null = null
  let motivo: string
  const est = margem ? aprox(margem.estimada) : ''
  if (grave) {
    motivo = 'Tem um alerta forte (risco, anúncio repetido ou preço baixo demais), então o Garimpo não destaca.'
  } else if (!mercado || !margem) {
    motivo = 'Ainda não dá pra calcular a margem. Faltam carros iguais na lista ou dado no anúncio.'
  } else if (margemAtinge(margem, mercado, MARGEM_QUENTE) && semAlerta && favores.length >= FAVORES_PARA_QUENTE) {
    nivel = 'quente'
    motivo = `Margem estimada de ${est}, sem nenhum alerta e ${favores.length} pontos a favor (${favores.map((c) => NOMES_FAVOR[c.id]).join(', ')}).`
  } else if (margemAtinge(margem, mercado, MARGEM_BOA)) {
    nivel = 'boa'
    motivo = `Margem estimada de ${est} e nenhum alerta forte. Pra ser Quente precisa de ${reais(MARGEM_QUENTE.reais)} de margem, nenhum alerta e ${FAVORES_PARA_QUENTE} pontos a favor.`
  } else {
    motivo = `Margem estimada de ${est}, abaixo do mínimo de ${reais(MARGEM_BOA.reais)} (e ${pct(MARGEM_BOA.pct)} da mediana) pra valer a revenda.`
  }
  return { nivel, resumo: nivel ? `Margem estimada ${aprox(margem?.estimada ?? 0)}` : null, motivo, criterios, mercado, margem }
}

export function agrupar(lista: Anuncio[]): Map<string, Anuncio[]> {
  const grupos = new Map<string, Anuncio[]>()
  for (const a of lista) {
    const k = chave(a)
    if (!k) continue
    const g = grupos.get(k)
    if (g) g.push(a)
    else grupos.set(k, [a])
  }
  return grupos
}

// Como `sinaisDaPagina`: calcula pros carros que acabaram de chegar, comparando com tudo que já está
// carregado. Quem chama guarda o resultado e não recalcula, pra o nível não mudar sozinho.
export function analisesDaPagina(novos: Anuncio[], lista: Anuncio[], agora: number): Record<string, Analise> {
  const grupos = agrupar(lista)
  const saida: Record<string, Analise> = {}
  for (const a of novos) saida[a.external_id] = analisar(a, grupos, agora)
  return saida
}
