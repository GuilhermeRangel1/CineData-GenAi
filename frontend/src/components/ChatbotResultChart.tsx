import { useRef, useState } from 'react'
import type { MetadadosGenAi } from '../types/api'
import { baixarGraficoPng } from './chatbotExport'
import { formatarCelula, rotuloColuna } from './chatbotPresentation'

type TipoGrafico = 'barras' | 'linha' | 'rosca' | 'dispersao'
type TemaGrafico = 'financeiro' | 'notas' | 'popularidade' | 'divergencia' | 'catalogo' | 'pessoas'

type EspecificacaoGrafico = {
  tipo: TipoGrafico
  colunaRotulo: string
  colunaValor: string
  titulo: string
  tema: TemaGrafico
  colunaX?: string
  colunaY?: string
}

const ESPECIFICACOES: Record<string, EspecificacaoGrafico> = {
  Q01: { tipo: 'barras', colunaRotulo: 'titulo', colunaValor: 'receita_brl', titulo: 'Receita por filme', tema: 'financeiro' },
  Q02: { tipo: 'barras', colunaRotulo: 'nome_genero', colunaValor: 'lucro_medio_brl', titulo: 'Lucro médio por gênero', tema: 'financeiro' },
  Q03: { tipo: 'barras', colunaRotulo: 'titulo', colunaValor: 'margem', titulo: 'Margem de lucro por filme', tema: 'financeiro' },
  Q04: { tipo: 'barras', colunaRotulo: 'titulo', colunaValor: 'popularidade', titulo: 'Popularidade por filme', tema: 'popularidade' },
  Q05: { tipo: 'barras', colunaRotulo: 'titulo', colunaValor: 'divergencia', titulo: 'Divergência entre IMDb e TMDB', tema: 'divergencia' },
  Q06: { tipo: 'linha', colunaRotulo: 'ano_lancamento', colunaValor: 'nota_imdb_media', titulo: 'Média IMDb por ano', tema: 'notas' },
  Q07: { tipo: 'barras', colunaRotulo: 'nome_pessoa', colunaValor: 'total_filmes', titulo: 'Filmes por ator', tema: 'pessoas' },
  Q08: { tipo: 'barras', colunaRotulo: 'nome_pessoa', colunaValor: 'nota_media', titulo: 'Média IMDb por diretor', tema: 'notas' },
  Q10: { tipo: 'rosca', colunaRotulo: 'nome_genero', colunaValor: 'total_filmes', titulo: 'Filmes por gênero', tema: 'catalogo' },
  Q11: { tipo: 'barras', colunaRotulo: 'nome_produtora', colunaValor: 'lucro_total_brl', titulo: 'Lucro total por produtora', tema: 'financeiro' },
  Q12: { tipo: 'barras', colunaRotulo: 'nome_genero', colunaValor: 'margem_media', titulo: 'Margem média por gênero', tema: 'financeiro' },
  Q13: { tipo: 'barras', colunaRotulo: 'titulo', colunaValor: 'qtd_avaliacoes_usuarios', titulo: 'Avaliações por filme', tema: 'catalogo' },
  Q14: { tipo: 'barras', colunaRotulo: 'titulo', colunaValor: 'divergencia', titulo: 'Divergência entre público e IMDb', tema: 'divergencia' },
}

type PontoGrafico = { rotulo: string; valor: number }

function numero(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && value.trim() && Number.isFinite(Number(value))) return Number(value)
  return null
}

function temaParaColuna(column: string): TemaGrafico {
  if (/(?:receita|orcamento|lucro|margem)/.test(column)) return 'financeiro'
  if (/(?:nota|media)/.test(column)) return 'notas'
  if (/(?:popularidade|relevancia)/.test(column)) return 'popularidade'
  if (/(?:ator|diretor|pessoa)/.test(column)) return 'pessoas'
  return 'catalogo'
}

function especificacao(metadata: MetadadosGenAi, rows: Array<Record<string, unknown>>): EspecificacaoGrafico | null {
  if (metadata.query_id && ESPECIFICACOES[metadata.query_id]) return ESPECIFICACOES[metadata.query_id]
  if (metadata.columns.includes('titulo') && metadata.columns.includes('receita_brl')) {
    return { tipo: 'barras', colunaRotulo: 'titulo', colunaValor: 'receita_brl', titulo: 'Receita por filme', tema: 'financeiro' }
  }
  if (metadata.columns.includes('titulo') && metadata.columns.includes('orcamento_brl')) {
    return { tipo: 'barras', colunaRotulo: 'titulo', colunaValor: 'orcamento_brl', titulo: 'Orçamento por filme', tema: 'financeiro' }
  }
  if (metadata.columns.includes('titulo') && metadata.columns.includes('orcamento_usd')) {
    return { tipo: 'barras', colunaRotulo: 'titulo', colunaValor: 'orcamento_usd', titulo: 'Orçamento por filme', tema: 'financeiro' }
  }
  if (metadata.columns.includes('titulo') && metadata.columns.includes('lucro_brl')) {
    return { tipo: 'barras', colunaRotulo: 'titulo', colunaValor: 'lucro_brl', titulo: 'Lucro por filme', tema: 'financeiro' }
  }
  if (metadata.columns.includes('titulo') && metadata.columns.includes('margem')) {
    return { tipo: 'barras', colunaRotulo: 'titulo', colunaValor: 'margem', titulo: 'Margem de lucro por filme', tema: 'financeiro' }
  }
  if (metadata.columns.includes('titulo') && metadata.columns.includes('popularidade')) {
    return { tipo: 'barras', colunaRotulo: 'titulo', colunaValor: 'popularidade', titulo: 'Popularidade por filme', tema: 'popularidade' }
  }
  if (metadata.metric === 'quantidade de filmes por ator') {
    return { tipo: 'barras', colunaRotulo: 'nome_pessoa', colunaValor: 'total_filmes', titulo: 'Filmes por ator', tema: 'pessoas' }
  }
  if (metadata.metric === 'quantidade de filmes por produtora') {
    return { tipo: 'barras', colunaRotulo: 'nome_produtora', colunaValor: 'total_filmes', titulo: 'Filmes por produtora', tema: 'catalogo' }
  }
  const numericColumns = metadata.columns.filter((column) =>
    !/^(?:id|id_.*|.*_id|ano_lancamento)$/i.test(column)
    && rows.some((row) => numero(row[column]) !== null),
  )
  const valueColumn = numericColumns.find((column) =>
    /(?:receita|orcamento|lucro|margem|nota|media|popularidade|relevancia|qtd|total|divergencia|duracao)/i.test(column),
  ) ?? numericColumns[0]
  if (!valueColumn) return null

  const labelColumn = metadata.columns.find((column) =>
    /^(?:titulo|nome_.+|ator|diretor|ano_lancamento|nome_genero|nome_produtora)$/i.test(column)
    && rows.some((row) => row[column] !== null && row[column] !== undefined),
  ) ?? metadata.columns.find((column) =>
    column !== valueColumn
    && !/^(?:id|id_.*|.*_id|sinopse)$/i.test(column)
    && rows.some((row) => typeof row[column] === 'string' && row[column].trim()),
  )
  if (!labelColumn) return null

  return {
    tipo: 'barras',
    colunaRotulo: labelColumn,
    colunaValor: valueColumn,
    titulo: `${rotuloColuna(valueColumn, metadata)} por ${rotuloColuna(labelColumn, metadata)}`,
    tema: temaParaColuna(valueColumn),
  }
}

function rotuloCurto(value: string) {
  return value.length > 25 ? `${value.slice(0, 24)}…` : value
}

function GraficoDeBarras({ pontos, spec }: { pontos: PontoGrafico[]; spec: EspecificacaoGrafico }) {
  const largura = 720
  const margemEsquerda = 168
  // A margem acomoda números longos, como valores em BRL, também no PNG.
  const margemDireita = 176
  const alturaLinha = 34
  const altura = pontos.length * alturaLinha + 38
  const minimo = Math.min(0, ...pontos.map((ponto) => ponto.valor))
  const maximo = Math.max(0, ...pontos.map((ponto) => ponto.valor))
  const intervalo = Math.max(1, maximo - minimo)
  const escala = (valor: number) => margemEsquerda + ((valor - minimo) / intervalo) * (largura - margemEsquerda - margemDireita)
  const base = escala(0)

  return (
    <svg className="chatbot-chart" viewBox={`0 0 ${largura} ${altura}`} role="img" aria-label={`${spec.titulo}. A tabela abaixo contém todos os valores.`}>
      <line className="chatbot-chart-axis" x1={base} x2={base} y1="10" y2={altura - 12} />
      {pontos.map((ponto, indice) => {
        const y = 12 + indice * alturaLinha
        const valorX = escala(ponto.valor)
        const inicio = Math.min(base, valorX)
        const larguraBarra = Math.max(2, Math.abs(valorX - base))
        return <g key={ponto.rotulo}>
          <text className="chatbot-chart-label" x={margemEsquerda - 10} y={y + 16} textAnchor="end">{rotuloCurto(ponto.rotulo)}</text>
          <rect className={`chatbot-chart-bar ${ponto.valor < 0 ? 'is-negative' : ''}`} x={inicio} y={y} width={larguraBarra} height="22" rx="6" />
          <text className="chatbot-chart-value" x={ponto.valor < 0 ? inicio - 8 : inicio + larguraBarra + 8} y={y + 16} textAnchor={ponto.valor < 0 ? 'end' : 'start'}>{formatarCelula(spec.colunaValor, ponto.valor)}</text>
        </g>
      })}
    </svg>
  )
}

function GraficoDeLinha({ pontos, spec }: { pontos: PontoGrafico[]; spec: EspecificacaoGrafico }) {
  const largura = 720
  const altura = 238
  const margem = { esquerda: 52, direita: 20, superior: 18, inferior: 48 }
  const minimo = Math.min(...pontos.map((ponto) => ponto.valor))
  const maximo = Math.max(...pontos.map((ponto) => ponto.valor))
  const intervalo = Math.max(0.1, maximo - minimo)
  const x = (indice: number) => margem.esquerda + (indice / Math.max(1, pontos.length - 1)) * (largura - margem.esquerda - margem.direita)
  const y = (valor: number) => margem.superior + ((maximo - valor) / intervalo) * (altura - margem.superior - margem.inferior)
  const linha = pontos.map((ponto, indice) => `${x(indice)},${y(ponto.valor)}`).join(' ')
  const area = `${x(0)},${altura - margem.inferior} ${linha} ${x(pontos.length - 1)},${altura - margem.inferior}`

  return (
    <svg className="chatbot-chart chatbot-chart--line" viewBox={`0 0 ${largura} ${altura}`} role="img" aria-label={`${spec.titulo}. A tabela abaixo contém todos os valores.`}>
      <defs><linearGradient id="chart-area" x1="0" x2="0" y1="0" y2="1"><stop stopColor="#79b9ff" /><stop offset="1" stopColor="#79b9ff" stopOpacity="0" /></linearGradient></defs>
      {[0, 0.5, 1].map((marcador) => <line className="chatbot-chart-grid" key={marcador} x1={margem.esquerda} x2={largura - margem.direita} y1={margem.superior + marcador * (altura - margem.superior - margem.inferior)} y2={margem.superior + marcador * (altura - margem.superior - margem.inferior)} />)}
      <polygon className="chatbot-chart-area" points={area} />
      <polyline className="chatbot-chart-line" points={linha} />
      {pontos.map((ponto, indice) => <g key={ponto.rotulo}>
        <circle className="chatbot-chart-point" cx={x(indice)} cy={y(ponto.valor)} r="4" />
        <text className="chatbot-chart-x-label" x={x(indice)} y={altura - 18} textAnchor="middle">{rotuloCurto(ponto.rotulo)}</text>
      </g>)}
    </svg>
  )
}

const CORES_ROSCA = ['#76d7c7', '#6da8f2', '#a88ded', '#f2b66d', '#e67d9d', '#77cfa2', '#5dc5d7', '#d994e7']

function GraficoDeRosca({ pontos, spec }: { pontos: PontoGrafico[]; spec: EspecificacaoGrafico }) {
  const dados = pontos.filter((ponto) => ponto.valor >= 0).slice(0, 7)
  const total = dados.reduce((soma, ponto) => soma + ponto.valor, 0)
  if (!total) return <GraficoDeBarras pontos={pontos} spec={spec} />
  let acumulado = 0
  const circunferencia = 2 * Math.PI * 54
  return (
    <svg className="chatbot-chart chatbot-chart--donut" viewBox="0 0 720 260" role="img" aria-label={`${spec.titulo}. A tabela abaixo contém todos os valores.`}>
      <circle className="chatbot-donut-track" cx="158" cy="130" r="54" />
      {dados.map((ponto, indice) => {
        const tamanho = (ponto.valor / total) * circunferencia
        const deslocamento = -acumulado
        acumulado += tamanho
        return <circle key={ponto.rotulo} className="chatbot-donut-segment" cx="158" cy="130" r="54" transform="rotate(-90 158 130)" stroke={CORES_ROSCA[indice]} strokeDasharray={`${tamanho} ${circunferencia - tamanho}`} strokeDashoffset={deslocamento} />
      })}
      <text className="chatbot-donut-total" x="158" y="125" textAnchor="middle">{formatarCelula(spec.colunaValor, total)}</text>
      <text className="chatbot-donut-caption" x="158" y="143" textAnchor="middle">no recorte</text>
      {dados.map((ponto, indice) => {
        const y = 44 + indice * 28
        return <g key={`legenda-${ponto.rotulo}`}>
          <circle cx="302" cy={y - 4} r="4" fill={CORES_ROSCA[indice]} />
          <text className="chatbot-donut-legend-label" x="316" y={y}>{rotuloCurto(ponto.rotulo)}</text>
          <text className="chatbot-donut-legend-value" x="682" y={y} textAnchor="end">{Math.round((ponto.valor / total) * 100)}%</text>
        </g>
      })}
    </svg>
  )
}

function GraficoDeDispersao({ rows, spec, metadata }: { rows: Array<Record<string, unknown>>; spec: EspecificacaoGrafico; metadata: MetadadosGenAi }) {
  const pontos = rows.flatMap((row) => {
    const x = numero(row[spec.colunaX ?? ''])
    const y = numero(row[spec.colunaY ?? ''])
    if (x === null || y === null || row[spec.colunaRotulo] == null) return []
    return [{ rotulo: formatarCelula(spec.colunaRotulo, row[spec.colunaRotulo]), x, y }]
  }).slice(0, 20)
  if (pontos.length < 2) return null
  const largura = 720; const altura = 260; const margem = { esquerda: 50, direita: 25, superior: 20, inferior: 44 }
  const escalaX = (valor: number) => margem.esquerda + (valor / 10) * (largura - margem.esquerda - margem.direita)
  const escalaY = (valor: number) => altura - margem.inferior - (valor / 10) * (altura - margem.superior - margem.inferior)
  return <svg className="chatbot-chart chatbot-chart--scatter" viewBox={`0 0 ${largura} ${altura}`} role="img" aria-label={`${spec.titulo}. Cada ponto representa um filme; a tabela abaixo contém todos os valores.`}>
    {[0, 5, 10].map((marca) => <g key={marca}><line className="chatbot-chart-grid" x1={escalaX(marca)} x2={escalaX(marca)} y1={margem.superior} y2={altura - margem.inferior} /><line className="chatbot-chart-grid" x1={margem.esquerda} x2={largura - margem.direita} y1={escalaY(marca)} y2={escalaY(marca)} /><text className="chatbot-chart-x-label" x={escalaX(marca)} y={altura - 18} textAnchor="middle">{marca}</text></g>)}
    <line className="chatbot-scatter-reference" x1={escalaX(0)} y1={escalaY(0)} x2={escalaX(10)} y2={escalaY(10)} />
    {pontos.map((ponto) => <circle key={ponto.rotulo} className="chatbot-scatter-point" cx={escalaX(ponto.x)} cy={escalaY(ponto.y)} r="6"><title>{`${ponto.rotulo}: ${spec.colunaX} ${ponto.x}, ${spec.colunaY} ${ponto.y}`}</title></circle>)}
    <text className="chatbot-scatter-axis" x={largura / 2} y={altura - 2} textAnchor="middle">{rotuloColuna(spec.colunaX ?? '', metadata)}</text>
    <text className="chatbot-scatter-axis" x="15" y={altura / 2} textAnchor="middle" transform={`rotate(-90 15 ${altura / 2})`}>{rotuloColuna(spec.colunaY ?? '', metadata)}</text>
  </svg>
}

export function ChatbotResultChart({ metadata, rows }: { metadata: MetadadosGenAi; rows: Array<Record<string, unknown>> }) {
  const spec = especificacao(metadata, rows)
  const chart = useRef<HTMLElement>(null)
  const [exportando, setExportando] = useState(false)
  const [erroExportacao, setErroExportacao] = useState('')
  if (!spec) return null
  const specForExport = spec
  const pontos = rows.flatMap((row) => {
    const valor = numero(row[spec.colunaValor])
    if (valor === null || row[spec.colunaRotulo] === undefined || row[spec.colunaRotulo] === null) return []
    return [{ rotulo: formatarCelula(spec.colunaRotulo, row[spec.colunaRotulo]), valor }]
  }).slice(0, 8)
  if (pontos.length < 2) return null

  async function exportarPng() {
    if (!chart.current) return
    setExportando(true)
    setErroExportacao('')
    try {
      await baixarGraficoPng({ elemento: chart.current, titulo: specForExport.titulo, metadata })
    } catch (error) {
      setErroExportacao(error instanceof Error ? error.message : 'Não foi possível baixar o gráfico.')
    } finally {
      setExportando(false)
    }
  }

  return <figure ref={chart} className={`chatbot-chart-card chatbot-chart-card--${spec.tema}`}>
    <figcaption>
      <span>Visualização</span>
      <div><strong>{spec.titulo}</strong><button className="chatbot-export-png" type="button" onClick={() => void exportarPng()} disabled={exportando}><svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="M10 2.5v9m0 0 3.5-3.5M10 11.5 6.5 8M3.5 13v2.5c0 .55.45 1 1 1h11c.55 0 1-.45 1-1V13" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" /></svg>{exportando ? 'Gerando…' : 'Baixar PNG'}</button></div>
      <small>{rotuloColuna(spec.colunaValor, metadata)}</small>
    </figcaption>
    {spec.tipo === 'linha' && <GraficoDeLinha pontos={pontos} spec={spec} />}
    {spec.tipo === 'barras' && <GraficoDeBarras pontos={pontos} spec={spec} />}
    {spec.tipo === 'rosca' && <GraficoDeRosca pontos={pontos} spec={spec} />}
    {spec.tipo === 'dispersao' && <GraficoDeDispersao rows={rows} spec={spec} metadata={metadata} />}
    {rows.length > pontos.length && <p>O gráfico mostra os primeiros {pontos.length} resultados; a tabela contém a lista completa.</p>}
    {erroExportacao && <p className="chatbot-chart-export-error" role="alert">{erroExportacao}</p>}
  </figure>
}

export function temGraficoDeResultado(metadata: MetadadosGenAi, rows: Array<Record<string, unknown>>) {
  const spec = especificacao(metadata, rows)
  if (!spec) return false
  return rows.filter((row) => numero(row[spec.colunaValor]) !== null && row[spec.colunaRotulo] != null).length > 1
}
