// Copia as buscas salvas de ../../dados para public/dados, sem o campo "crus" (item cru da fonte,
// que a tela não usa), e gera public/dados/index.json com a lista de buscas para o seletor.
// Só entram arquivos no formato novo do coletor (com "resultado"). Quando existir endpoint, isto some.
import { mkdirSync, readdirSync, readFileSync, writeFileSync, existsSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const aqui = dirname(fileURLToPath(import.meta.url))
const origem = join(aqui, '..', '..', '..', 'dados')
const destino = join(aqui, '..', 'public', 'dados')

if (!existsSync(origem)) {
  console.warn(`Pasta ${origem} não existe, nada copiado.`)
  process.exit(0)
}
mkdirSync(destino, { recursive: true })

const indice = []
for (const arquivo of readdirSync(origem).filter((f) => f.endsWith('.json')).sort()) {
  const dados = JSON.parse(readFileSync(join(origem, arquivo), 'utf8'))
  if (!dados.resultado || !Array.isArray(dados.anuncios)) {
    console.log(`pulei ${arquivo} (formato antigo, sem "resultado")`)
    continue
  }
  const { crus: _crus, ...leve } = dados
  writeFileSync(join(destino, arquivo), JSON.stringify(leve))
  indice.push({ arquivo, busca: dados.busca, anuncios: dados.anuncios.length })
  console.log(`copiei ${arquivo} (${dados.anuncios.length} anúncios, busca "${dados.busca.texto}")`)
}
writeFileSync(join(destino, 'index.json'), JSON.stringify(indice))
console.log(`${indice.length} buscas em ${destino}`)
