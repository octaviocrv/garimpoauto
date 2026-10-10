// Leitor de SSE (text/event-stream) em pedaços, porque os dados chegam picados pela rede.
// Comentário (linha começando com ":") é só sinal de vida e é ignorado.
export interface EventoSse {
  nome: string
  dados: unknown
}

export function criarLeitorSse(aoEvento: (e: EventoSse) => void) {
  let sobra = ''
  const bloco = (texto: string) => {
    let nome = 'message'
    const dados: string[] = []
    for (const linha of texto.split('\n')) {
      if (linha.startsWith('event:')) nome = linha.slice(6).trim()
      else if (linha.startsWith('data:')) dados.push(linha.slice(5).replace(/^ /, ''))
    }
    if (!dados.length) return
    try {
      aoEvento({ nome, dados: JSON.parse(dados.join('\n')) })
    } catch {
      // evento quebrado não derruba a busca, os outros seguem
    }
  }
  return {
    empurrar(pedaco: string) {
      sobra += pedaco.replace(/\r\n/g, '\n')
      let fim: number
      while ((fim = sobra.indexOf('\n\n')) !== -1) {
        bloco(sobra.slice(0, fim))
        sobra = sobra.slice(fim + 2)
      }
    },
  }
}
