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
  dicaFiltros: 'Trocou estado, região ou zona, a busca já atualiza. Os outros filtros valem quando você aperta Buscar.',
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
  naoMedido: 'Informações sem peso no veredito',
  numeros: 'Quanto o carro rodou',
  nadaAFavor: 'Nenhum ponto forte encontrado nos dados que a gente tem.',
  nadaContra: 'Nenhum alerta encontrado no anúncio.',
  aindaNaoEntra: 'Ainda não entram nessa análise o histórico de preço e o tempo que o carro fica no ar.',
  comoLer: 'O veredito usa a FIPE, o preço médio e a régua que a OLX mostra no anúncio, junto com km, o que o anunciante marcou e os riscos. Confira cada linha antes de decidir.',
  poucoKm: 'Pouco km pro ano',
  fipeNoValor: 'No valor da FIPE',
  fipePrecoEstranho: 'Preço muito abaixo da FIPE',
  detalheFalhou: 'Não consegui abrir esse anúncio na OLX agora, tenta de novo?',
} as const

export const naOlx = (total: number) => `${total.toLocaleString('pt-BR')} na OLX`
export const buscadoAs = (iso: string): string => {
  const d = new Date(iso)
  return `buscado às ${d.getHours()}h${String(d.getMinutes()).padStart(2, '0')}`
}

export const novosDesde = (n: number) => `${n.toLocaleString('pt-BR')} ${n === 1 ? 'novo' : 'novos'} desde a última busca`
export const seloFipeAbaixo = (n: number) => `${n}% abaixo da FIPE`
export const seloFipeAcima = (n: number) => `${n}% acima da FIPE`
