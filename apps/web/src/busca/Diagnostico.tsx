import type { Anuncio, RespostaPagina } from '../types'

const CAMPOS_VERIFICADOS = ['preco', 'ano', 'km', 'marca', 'modelo_original', 'cidade'] as const

// Quantos anúncios têm cada campo vazio (os que os filtros usam).
function contarVazios(anuncios: Anuncio[]): { porCampo: Record<string, number>; algum: number } {
  const porCampo = Object.fromEntries(CAMPOS_VERIFICADOS.map((c) => [c, 0]))
  let algum = 0
  for (const a of anuncios) {
    let tem = false
    for (const c of CAMPOS_VERIFICADOS) {
      if (a[c] === null || a[c] === '') { porCampo[c] += 1; tem = true }
    }
    if (tem) algum += 1
  }
  return { porCampo, algum }
}

// Só aparece com ?dev=1. Mostra o que o servidor contou e onde cada filtro foi aplicado.
export function Diagnostico({ resposta, anuncios }: { resposta: RespostaPagina; anuncios: Anuncio[] }) {
  const vazios = contarVazios(anuncios)
  const linha = (nome: string, valor: unknown) => (
    <div className="flex justify-between gap-4"><dt className="text-gray-500">{nome}</dt><dd>{String(valor)}</dd></div>
  )
  return (
    <details className="mb-4 rounded-lg border border-white/10 bg-[#0a0a0a] p-3 font-mono text-xs text-gray-300">
      <summary className="cursor-pointer text-teal-400">Diagnóstico (dev)</summary>
      <dl className="mt-3 space-y-1">
        {linha('página', resposta.pagina)}
        {linha('total na fonte', resposta.total_na_fonte)}
        {linha('coletados até aqui', resposta.coletados)}
        {linha('entregues até aqui', resposta.entregues)}
        {linha('cortados nesta página', JSON.stringify(resposta.cortados_por_filtro))}
        {linha('filtros na origem', resposta.filtros_na_origem.join(', ') || 'nenhum')}
        {linha('filtros só aqui', resposta.filtros_locais.join(', ') || 'nenhum')}
        {linha('motivo_parada', resposta.motivo_parada)}
        {linha('veio do cache', resposta.do_cache)}
        {linha('estado aplicado', resposta.estado_aplicado)}
        <div className="my-2 border-t border-white/10" />
        {linha('carros na lista', anuncios.length)}
        {linha('com algum campo vazio', vazios.algum)}
        {linha('vazios por campo', JSON.stringify(vazios.porCampo))}
        {linha('em destaque', anuncios.filter((a) => a.em_destaque).length)}
        {linha('marcados como repetido', anuncios.filter((a) => a.repetido_de).length)}
      </dl>
      {resposta.avisos.map((a) => (
        <p key={a.codigo} className="mt-3 break-words text-gray-400">
          <span className="text-teal-400">{a.codigo}</span> {a.detalhe_tecnico ?? ''}
        </p>
      ))}
    </details>
  )
}
