import type { MetadadosGenAi } from '../types/api'

const TITULOS: Record<string, string> = {
  Q01: 'Filmes com maior receita',
  Q02: 'Lucro médio por gênero',
  Q03: 'Filmes com maiores margens',
  Q04: 'Filmes mais populares',
  Q05: 'Diferenças entre IMDb e TMDB',
  Q06: 'Nota IMDb média por ano',
  Q07: 'Ator com mais filmes recentes',
  Q08: 'Diretores com maior média no IMDb',
  Q09: 'Dupla ator e diretor com mais filmes',
  Q10: 'Filmes por gênero',
  Q11: 'Produtora com maior lucro total',
  Q12: 'Gênero com maior margem média',
  Q13: 'Filmes mais avaliados pelo público',
  Q14: 'Diferenças entre público e IMDb',
}

const OBSERVACOES: Record<string, string> = {
  Q02: 'Um filme pode contar em mais de um gênero. Entram no cálculo apenas filmes com receita e orçamento informados.',
  Q03: 'A margem considera apenas filmes com receita e orçamento informados.',
  Q04: 'Popularidade é uma pontuação do catálogo, não uma contagem de visualizações.',
  Q05: 'A comparação considera filmes com notas e votos nas duas plataformas.',
  Q06: 'Média simples dos filmes que receberam votos no IMDb.',
  Q07: 'Considera os filmes lançados nos últimos cinco anos.',
  Q08: 'Considera diretores com pelo menos cinco filmes avaliados.',
  Q09: 'Filmes em comum não indicam quem teve o crédito principal.',
  Q10: 'Filmes com vários gêneros aparecem em cada gênero correspondente.',
  Q11: 'O lucro de um filme é atribuído a cada produtora associada a ele.',
  Q12: 'A margem usa filmes com receita e orçamento informados.',
  Q14: 'A comparação usa filmes avaliados pelo público e no IMDb.',
}

const ROTULOS: Record<string, string> = {
  ator: 'Ator',
  diretor: 'Diretor',
  titulo: 'Filme',
  nome_genero: 'Gênero',
  nome_produtora: 'Produtora',
  nome_pessoa: 'Pessoa',
  ano_lancamento: 'Ano',
  total_filmes: 'Filmes',
  filmes_validos: 'Filmes avaliados',
  filmes_elegiveis: 'Filmes considerados',
  filmes_em_comum: 'Filmes juntos',
  receita_brl: 'Receita',
  orcamento_brl: 'Orçamento',
  lucro_brl: 'Lucro',
  lucro_medio_brl: 'Lucro médio',
  lucro_total_brl: 'Lucro total',
  margem: 'Margem',
  margem_media: 'Margem média',
  popularidade: 'Popularidade',
  nota_imdb: 'Nota IMDb',
  nota_tmdb: 'Nota TMDB',
  nota_media: 'Nota média',
  nota_imdb_media: 'Média IMDb',
  nota_media_usuarios: 'Nota do público',
  qtd_imdb: 'Votos no IMDb',
  qtd_tmdb: 'Votos no TMDB',
  qtd_avaliacoes_usuarios: 'Avaliações do público',
  divergencia: 'Diferença de notas',
  sinopse: 'Sinopse',
  relevancia: 'Relevância',
}

const INDICADORES: Record<string, string> = {
  Q01: 'Receita por filme',
  Q02: 'Lucro médio por gênero',
  Q03: 'Margem de lucro por filme',
  Q04: 'Popularidade por filme',
  Q05: 'Diferença entre notas do IMDb e TMDB',
  Q06: 'Média das notas IMDb por ano',
  Q07: 'Participação de atores em filmes recentes',
  Q08: 'Média das notas IMDb por diretor',
  Q09: 'Parcerias entre atores e diretores',
  Q10: 'Filmes por gênero',
  Q11: 'Lucro acumulado por produtora',
  Q12: 'Margem média de lucro por gênero',
  Q13: 'Avaliações do público por filme',
  Q14: 'Diferença entre notas do público e IMDb',
}

const ABRANGENCIAS: Record<string, string> = {
  Q01: 'Filmes com receita registrada',
  Q02: 'Filmes com receita e orçamento registrados',
  Q03: 'Filmes com receita e orçamento registrados',
  Q04: 'Filmes com índice de popularidade disponível',
  Q05: 'Filmes avaliados no IMDb e no TMDB',
  Q06: 'Filmes com avaliações no IMDb',
  Q07: 'Filmes lançados nos últimos cinco anos',
  Q08: 'Diretores com pelo menos cinco filmes avaliados',
  Q09: 'Filmes com participação de ator e direção',
  Q10: 'Filmes vinculados a gêneros',
  Q11: 'Filmes com receita e orçamento registrados',
  Q12: 'Filmes com receita e orçamento registrados',
  Q13: 'Filmes com avaliações do público',
  Q14: 'Filmes avaliados pelo público e no IMDb',
}

const UNIDADES: Record<string, string> = {
  BRL: 'Reais (R$)',
  'BRL por filme': 'Reais por filme',
  'filmes distintos': 'Filmes',
  avaliações: 'Avaliações',
  'pontuação de popularidade': 'Índice de popularidade',
  'pontuação em escala de 0 a 10': 'Notas de 0 a 10',
  'fração, com exibição possível em percentual': 'Percentual',
}

const GENEROS: Record<string, string> = {
  action: 'Ação',
  adventure: 'Aventura',
  animation: 'Animação',
  comedy: 'Comédia',
  crime: 'Crime',
  documentary: 'Documentário',
  drama: 'Drama',
  family: 'Família',
  fantasy: 'Fantasia',
  history: 'História',
  horror: 'Terror',
  music: 'Música',
  mystery: 'Mistério',
  romance: 'Romance',
  'science fiction': 'Ficção científica',
  'tv movie': 'Filme para TV',
  thriller: 'Suspense',
  war: 'Guerra',
  western: 'Faroeste',
}

const numero = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 2 })
const moedaBrl = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })
const moedaUsd = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'USD' })
const percentual = new Intl.NumberFormat('pt-BR', { style: 'percent', maximumFractionDigits: 2 })

export function tituloResultado(metadata: MetadadosGenAi): string {
  if (metadata.query_id && TITULOS[metadata.query_id]) return TITULOS[metadata.query_id]
  if (metadata.metric === 'quantidade de filmes por ator') return 'Atores com mais filmes'
  if (metadata.metric === 'quantidade de filmes por produtora') return 'Produtoras com mais filmes'
  if (metadata.columns.includes('nome_genero') && metadata.columns.includes('total_filmes')) return 'Filmes por gênero'
  if (metadata.columns.includes('popularidade')) return 'Filmes mais populares'
  return 'Resultados encontrados'
}

export function contextoParaExibicao(metadata: MetadadosGenAi): Array<[string, string]> {
  const indicador = (metadata.query_id && INDICADORES[metadata.query_id]) ?? metadata.metric
  const unidade = metadata.unit ? (UNIDADES[metadata.unit] ?? metadata.unit) : null
  const periodo = metadata.period
    ? (/gold/i.test(metadata.period) ? 'Até a atualidade' : metadata.period.replace(/^anos presentes no /i, 'Anos disponíveis no '))
    : null
  const abrangencia = (metadata.query_id && ABRANGENCIAS[metadata.query_id])
    ?? metadata.population
      ?.replaceAll('receita_brl', 'receita')
      .replaceAll('orcamento_brl', 'orçamento')
      .replaceAll('nota_imdb', 'nota IMDb')
      .replaceAll('qtd_imdb', 'avaliações no IMDb')
      .replaceAll('não nula', 'registrada')
      .replaceAll('não nulos', 'registrados')

  const campos: Array<[string, string | null | undefined]> = [
    ['Indicador', indicador],
    ['Valores exibidos', unidade],
    ['Período', periodo],
    ['Abrangência', abrangencia],
  ]
  return campos.flatMap(([label, value]) => value ? [[label, value] as [string, string]] : [])
}

export function observacaoResultado(metadata: MetadadosGenAi): string | null {
  if (metadata.query_id && OBSERVACOES[metadata.query_id]) return OBSERVACOES[metadata.query_id]
  if (metadata.columns.includes('popularidade')) return OBSERVACOES.Q04
  return null
}

export function colunasVisiveis(columns: string[]): string[] {
  return columns.filter((column) => !/^(?:id|id_.*|.*_id)$/i.test(column))
}

export function rotuloColuna(column: string, metadata: MetadadosGenAi): string {
  if (column === 'nome_pessoa' && (metadata.query_id === 'Q07' || metadata.metric === 'quantidade de filmes por ator')) return 'Ator'
  if (column === 'nome_pessoa' && metadata.query_id === 'Q08') return 'Diretor'
  return ROTULOS[column] ?? column.replaceAll('_', ' ').replace(/^\w/, (letter) => letter.toUpperCase())
}

export function formatarCelula(column: string, value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'number') {
    if (column.endsWith('_brl')) return moedaBrl.format(value)
    if (column.endsWith('_usd')) return moedaUsd.format(value)
    if (column === 'margem' || column === 'margem_media') return percentual.format(value)
    return numero.format(value)
  }
  const text = String(value)
  if (column === 'nome_genero') return GENEROS[text.trim().toLowerCase()] ?? text
  if (column === 'nome_pessoa' && /^\d+(?:[.,]\d+)?$/.test(text.trim())) return 'Nome não informado'
  return text
}
