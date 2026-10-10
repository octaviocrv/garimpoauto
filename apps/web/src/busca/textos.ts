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
  listaFalhou: 'Não consegui carregar essa lista agora. A busca funciona do mesmo jeito.',
  regiao: 'Região',
  qualquerRegiao: 'Qualquer região',
  zona: 'Zona',
  qualquerZona: 'Qualquer zona',
  carregando: 'Carregando...',
  novo: 'Novo',
  legendaSinais: 'Os sinais vêm do que o anúncio mostra. O preço só compara com os carros já carregados aqui. Borda verde quer dizer 2 ou mais sinais. Quente e Boa vêm da análise de revenda, toca em Garimpar pra ver a conta.',
  garimpar: 'Garimpar',
  verAnuncio: 'Ver anúncio original',
  quente: 'Quente',
  boa: 'Boa',
  voltar: 'Voltar pra lista',
  analiseTitulo: 'Vale pra revenda?',
  porQueVale: 'Por que vale pra revenda',
  porQueNao: 'Por que cuidado ou não vale',
  naoMedido: 'O que não deu pra medir',
  numeros: 'Os números',
  nadaAFavor: 'Nenhum ponto forte encontrado nos dados que a gente tem.',
  nadaContra: 'Nenhum alerta encontrado nos dados que a gente tem.',
  aindaNaoEntra: 'Ainda não entram nessa análise a tabela FIPE, o histórico de preço, o tempo que o carro fica no ar e a descrição do anúncio. Quando entrarem, a conta aparece aqui.',
  comoLer: 'Nada aqui é nota. Cada linha mostra a conta e de onde ela veio, pra você conferir e discordar.',
  poucoKm: 'Pouco km pro ano',
  exemplo: 'Exemplo, não é valor real',
  demoLigado: 'Modo exemplo ligado. A FIPE que aparece aqui é inventada, só pra ver como o card ficaria.',
  demoEsconder: 'Esconder FIPE de exemplo',
  demoMostrar: 'Mostrar FIPE de exemplo',
} as const

export const naOlx = (total: number) => `${total.toLocaleString('pt-BR')} na OLX`
export const buscadoAs = (iso: string): string => {
  const d = new Date(iso)
  return `buscado às ${d.getHours()}h${String(d.getMinutes()).padStart(2, '0')}`
}

export const novosDesde = (n: number) => `${n.toLocaleString('pt-BR')} ${n === 1 ? 'novo' : 'novos'} desde a última busca`
