import type { MetadadosGenAi } from '../types/api'
import { formatarCelula, rotuloColuna } from './chatbotPresentation'

type TipoGrafico = 'barras' | 'linha'

type EspecificacaoGrafico = {
  tipo: TipoGrafico
  colunaRotulo: string
  colunaValor: string
  titulo: string
}

const ESPECIFICACOES: Record<string, EspecificacaoGrafico> = {
  Q01: { tipo: 'barras', colunaRotulo: 'titulo', colunaValor: 'receita_brl', titulo: 'Receita por filme' },
  Q02: { tipo: 'barras', colunaRotulo: 'nome_genero', colunaValor: 'lucro_medio_brl', titulo: 'Lucro médio por gênero' },
  Q03: { tipo: 'barras', colunaRotulo: 'titulo', colunaValor: 'margem', titulo: 'Margem de lucro por filme' },
  Q04: { tipo: 'barras', colunaRotulo: 'titulo', colunaValor: 'popularidade', titulo: 'Popularidade por filme' },
  Q05: { tipo: 'barras', colunaRotulo: 'titulo', colunaValor: 'divergencia', titulo: 'Diferença entre IMDb e TMDB' },
  Q06: { tipo: 'linha', colunaRotulo: 'ano_lancamento', colunaValor: 'nota_imdb_media', titulo: 'Média IMDb por ano' },
  Q07: { tipo: 'barras', colunaRotulo: 'nome_pessoa', colunaValor: 'total_filmes', titulo: 'Filmes por ator' },
  Q08: { tipo: 'barras', colunaRotulo: 'nome_pessoa', colunaValor: 'nota_media', titulo: 'Média IMDb por diretor' },
  Q10: { tipo: 'barras', colunaRotulo: 'nome_genero', colunaValor: 'total_filmes', titulo: 'Filmes por gênero' },
  Q11: { tipo: 'barras', colunaRotulo: 'nome_produtora', colunaValor: 'lucro_total_brl', titulo: 'Lucro total por produtora' },
  Q12: { tipo: 'barras', colunaRotulo: 'nome_genero', colunaValor: 'margem_media', titulo: 'Margem média por gênero' },
  Q13: { tipo: 'barras', colunaRotulo: 'titulo', colunaValor: 'qtd_avaliacoes_usuarios', titulo: 'Avaliações por filme' },
  Q14: { tipo: 'barras', colunaRotulo: 'titulo', colunaValor: 'divergencia', titulo: 'Diferença entre público e IMDb' },
}

type PontoGrafico = { rotulo: string; valor: number }

function numero(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && value.trim() && Number.isFinite(Number(value))) return Number(value)
  return null
}

function especificacao(metadata: MetadadosGenAi): EspecificacaoGrafico | null {
  if (metadata.query_id && ESPECIFICACOES[metadata.query_id]) return ESPECIFICACOES[metadata.query_id]
  if (metadata.metric === 'quantidade de filmes por ator') {
    return { tipo: 'barras', colunaRotulo: 'nome_pessoa', colunaValor: 'total_filmes', titulo: 'Filmes por ator' }
  }
  if (metadata.metric === 'quantidade de filmes por produtora') {
    return { tipo: 'barras', colunaRotulo: 'nome_produtora', colunaValor: 'total_filmes', titulo: 'Filmes por produtora' }
  }
  return null
}

function rotuloCurto(value: string) {
  return value.length > 25 ? `${value.slice(0, 24)}…` : value
}

function GraficoDeBarras({ pontos, spec }: { pontos: PontoGrafico[]; spec: EspecificacaoGrafico }) {
  const largura = 720
  const margemEsquerda = 168
  const margemDireita = 84
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

  return (
    <svg className="chatbot-chart chatbot-chart--line" viewBox={`0 0 ${largura} ${altura}`} role="img" aria-label={`${spec.titulo}. A tabela abaixo contém todos os valores.`}>
      {[0, 0.5, 1].map((marcador) => <line className="chatbot-chart-grid" key={marcador} x1={margem.esquerda} x2={largura - margem.direita} y1={margem.superior + marcador * (altura - margem.superior - margem.inferior)} y2={margem.superior + marcador * (altura - margem.superior - margem.inferior)} />)}
      <polyline className="chatbot-chart-line" points={linha} />
      {pontos.map((ponto, indice) => <g key={ponto.rotulo}>
        <circle className="chatbot-chart-point" cx={x(indice)} cy={y(ponto.valor)} r="4" />
        <text className="chatbot-chart-x-label" x={x(indice)} y={altura - 18} textAnchor="middle">{rotuloCurto(ponto.rotulo)}</text>
      </g>)}
    </svg>
  )
}

export function ChatbotResultChart({ metadata, rows }: { metadata: MetadadosGenAi; rows: Array<Record<string, unknown>> }) {
  const spec = especificacao(metadata)
  if (!spec) return null
  const pontos = rows.flatMap((row) => {
    const valor = numero(row[spec.colunaValor])
    if (valor === null || row[spec.colunaRotulo] === undefined || row[spec.colunaRotulo] === null) return []
    return [{ rotulo: formatarCelula(spec.colunaRotulo, row[spec.colunaRotulo]), valor }]
  }).slice(0, 8)
  if (pontos.length < 2) return null

  return <figure className="chatbot-chart-card">
    <figcaption>
      <span>Visualização</span>
      <strong>{spec.titulo}</strong>
      <small>{rotuloColuna(spec.colunaValor, metadata)}</small>
    </figcaption>
    {spec.tipo === 'linha' ? <GraficoDeLinha pontos={pontos} spec={spec} /> : <GraficoDeBarras pontos={pontos} spec={spec} />}
    {rows.length > pontos.length && <p>O gráfico mostra os primeiros {pontos.length} resultados; a tabela contém a lista completa.</p>}
  </figure>
}

export function temGraficoDeResultado(metadata: MetadadosGenAi, rows: Array<Record<string, unknown>>) {
  const spec = especificacao(metadata)
  if (!spec) return false
  return rows.filter((row) => numero(row[spec.colunaValor]) !== null && row[spec.colunaRotulo] != null).length > 1
}
