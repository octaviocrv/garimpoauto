import type { Anuncio, ResultadoBusca } from '../types'
import { contarVazios } from './filtros'

// Só aparece com ?dev=1. Explica por que a lista tem o tamanho que tem.
export function Diagnostico({
  resultado, depoisDosFiltros, cortadosTela,
}: {
  resultado: ResultadoBusca
  depoisDosFiltros: Anuncio[]
  cortadosTela: Record<string, number>
}) {
  const f = resultado.funil
  const vazios = contarVazios(resultado.anuncios)
  const linha = (nome: string, valor: unknown) => (
    <div className="flex justify-between gap-4"><dt className="text-gray-500">{nome}</dt><dd>{String(valor)}</dd></div>
  )
  return (
    <details className="mb-4 rounded-lg border border-white/10 bg-[#0a0a0a] p-3 font-mono text-xs text-gray-300">
      <summary className="cursor-pointer text-teal-400">Diagnóstico (dev)</summary>
      <dl className="mt-3 space-y-1">
        {linha('total na fonte', f.total_na_fonte)}
        {linha('coletados', f.coletados)}
        {linha('cortados no coletor', JSON.stringify(f.cortados_por_filtro))}
        {linha('finais do coletor', f.finais)}
        {linha('motivo_parada', resultado.motivo_parada)}
        {linha('páginas lidas', resultado.paginas_lidas)}
        {linha('tempo', `${resultado.tempo_segundos.toFixed(1)}s`)}
        <div className="my-2 border-t border-white/10" />
        {linha('carros depois dos filtros da tela', depoisDosFiltros.length)}
        {linha('cortados pelos filtros da tela', JSON.stringify(cortadosTela))}
        {linha('com algum campo vazio (da lista toda)', vazios.algum)}
        {linha('vazios por campo', JSON.stringify(vazios.porCampo))}
        {linha('com algum campo vazio (depois dos filtros)', contarVazios(depoisDosFiltros).algum)}
      </dl>
      {resultado.avisos.map((a) => (
        <p key={a.codigo} className="mt-3 break-words text-gray-400">
          <span className="text-teal-400">{a.codigo}</span> {a.detalhe_tecnico}
        </p>
      ))}
    </details>
  )
}
