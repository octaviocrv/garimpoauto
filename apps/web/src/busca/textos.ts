// Textos da tela de busca. Português informal, frases curtas, sem travessão, dois pontos nem ponto e vírgula.
export const T = {
  inicial: 'Digita o carro que você quer e aperta Enter. O resto é com a gente.',
  garimpando: 'Garimpando...',
  garimpandoSub: 'Já já os carros aparecem aqui.',
  demorando: 'Tá demorando um pouco mais que o normal, segura aí.',
  parada: 'Parei a busca.',
  semCarro: 'Não achei esse carro agora, tenta de novo?',
  pedidoRuim: 'Esse pedido de busca não está certo, confere os filtros?',
  maisFalhou: 'Não consegui buscar mais agora, tenta de novo daqui a pouco?',
  nenhumComFiltro: 'Não achei nenhum carro com esses filtros. Que tal afrouxar algum?',
  buscar: 'Buscar',
  filtros: 'Filtros',
  parar: 'Parar',
  verMais: 'Ver mais',
  buscandoMais: 'Buscando mais...',
  tentarDeNovo: 'Tentar de novo',
  buscarDeNovo: 'Buscar de novo',
  limparFiltros: 'Limpar filtros',
  dicaFiltros: 'Os filtros valem na próxima busca. Aperta Buscar pra aplicar.',
  destaque: 'Destaque',
  placeholder: 'Qual carro você quer? Tipo gol 2012',
} as const

export const naOlx = (total: number) => `${total.toLocaleString('pt-BR')} na OLX`
export const buscadoAs = (iso: string): string => {
  const d = new Date(iso)
  return `buscado às ${d.getHours()}h${String(d.getMinutes()).padStart(2, '0')}`
}
