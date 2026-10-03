export type PapelPessoa = 'Ator' | 'Diretor' | 'Roteirista'
export type OrdenacaoFilme = 'titulo' | 'ano_lancamento' | 'relevancia'
export type DirecaoOrdenacao = 'asc' | 'desc'

export interface ErroApi {
  codigo: string
  mensagem: string
}

export interface MetadadosGenAi {
  source: 'gold' | 'platform' | 'mixed'
  query_id: string | null
  metric: string | null
  unit: string | null
  period: string | null
  population: string | null
  limitations: string | null
  columns: string[]
  row_count: number
  truncated: boolean
  tool_calls: number
}

export interface RespostaGenAi {
  status: 'success'
  answer: string
  rows: Array<Record<string, unknown>>
  insights: string[]
  metadata: MetadadosGenAi
}

export interface ErroGenAi {
  status: 'clarification' | 'error'
  error: {
    code: string
    message: string
    details: unknown
  }
}

export interface MensagemConversa {
  role: 'user' | 'assistant'
  conteudo: string
}

export interface MetadadosPagina {
  pagina: number
  tamanho_pagina: number
  total_itens: number
  total_paginas: number
}

export interface Pagina<T> {
  itens: T[]
  meta: MetadadosPagina
}

export interface GeneroResumo {
  id: string
  nome: string
}

export interface ProdutoraResumo {
  id: string
  nome: string
}

export interface PessoaResumo {
  id: string
  nome: string
  papel: PapelPessoa
}

export interface AvaliacaoCriacao {
  nota: number
  comentario: string
  visibilidade?: 'publica' | 'privada'
}

export interface AvaliacaoLeitura extends AvaliacaoCriacao {
  id: string
  nome: string
  criada_em: string
}

export interface UsuarioLeitura {
  id: string
  email: string
  nome: string
  role: 'user' | 'admin'
  created_at: string
  avatar_url?: string | null
}

export interface TokenAcesso {
  access_token: string
  token_type: 'bearer'
  expires_in: number
  usuario: UsuarioLeitura
}

export interface DesempenhoFilme {
  orcamento_usd: number | null
  receita_usd: number | null
  lucro_usd: number | null
  orcamento_brl: number | null
  receita_brl: number | null
  lucro_brl: number | null
  popularidade: number | null
  nota_tmdb: number | null
  quantidade_tmdb: number | null
  nota_imdb: number | null
  quantidade_imdb: number | null
}

export interface FilmeCriacao {
  titulo: string
  diretor: string
  ano_lancamento?: number
  generos: string[]
  sinopse?: string
  data_lancamento?: string
  duracao_minutos?: number
  status_filme?: string
  url_poster?: string
  url_backdrop?: string
  url_trailer?: string
  atores?: string[]
  roteiristas?: string[]
  produtoras?: string[]
}

export type FilmeAtualizacao = Partial<
  Pick<FilmeCriacao, 'titulo' | 'diretor' | 'generos' | 'atores' | 'roteiristas' | 'produtoras'>
> & {
  [
    K in
      | 'ano_lancamento'
      | 'sinopse'
      | 'data_lancamento'
      | 'duracao_minutos'
      | 'status_filme'
      | 'url_poster'
      | 'url_backdrop'
      | 'url_trailer'
  ]?: FilmeCriacao[K] | null
}

export interface FilmeResumo {
  id: string
  titulo: string
  ano_lancamento: number | null
  url_poster: string | null
  url_backdrop: string | null
  generos: GeneroResumo[]
  nota_media: number | null
  quantidade_avaliacoes: number
}

export interface FilmeDetalhe extends FilmeResumo {
  data_lancamento: string | null
  duracao_minutos: number | null
  status_filme: string | null
  sinopse: string | null
  url_backdrop: string | null
  url_trailer: string | null
  pessoas: PessoaResumo[]
  produtoras: ProdutoraResumo[]
  desempenho: DesempenhoFilme | null
  avaliacoes: AvaliacaoLeitura[]
}

export interface ConsultaCatalogo {
  busca?: string
  genero?: string
  pessoa?: string
  produtora?: string
  ano_inicial?: number
  ano_final?: number
  duracao_minima?: number
  duracao_maxima?: number
  nota_minima?: number
  pagina?: number
  tamanho_pagina?: number
  ordenar_por?: OrdenacaoFilme
  direcao?: DirecaoOrdenacao
  priorizar_capa?: boolean
  priorizar_trailer?: boolean
  somente_com_trailer?: boolean
}

export interface TmdbResultado {
  id: number
  titulo: string
  ano_lancamento: number | null
  url_poster: string | null
}

export interface TmdbImportacao {
  titulo: string | null
  diretor: string | null
  generos: string[]
  sinopse: string | null
  ano_lancamento: number | null
  data_lancamento: string | null
  url_poster: string | null
  url_backdrop: string | null
  url_trailer: string | null
}

export interface MetricaAnalytics {
  chave: 'filmes' | 'usuarios' | 'avaliacoes' | 'listas' | 'comunidades'
  rotulo: string
  valor: number
  detalhe: string
}

export interface PontoEvolucaoAnalytics {
  data: string
  usuarios: number
  avaliacoes: number
  listas: number
  publicacoes: number
}

export interface GeneroAnalytics {
  nome: string
  quantidade: number
  nota_media: number | null
}

export interface FilmeAnalytics {
  id: string
  titulo: string
  url_poster: string | null
  quantidade_avaliacoes: number
  nota_media: number | null
}

export interface ComunidadeAnalytics {
  id: string
  nome: string
  imagem_url: string | null
  membros: number
  publicacoes: number
  visualizacoes: number
}

export interface ResumoAnalytics {
  periodo_dias: number
  metricas: MetricaAnalytics[]
  evolucao: PontoEvolucaoAnalytics[]
  generos: GeneroAnalytics[]
  filmes_mais_avaliados: FilmeAnalytics[]
  comunidades_em_alta: ComunidadeAnalytics[]
}

export interface NoMapaGostos {
  id: string
  titulo: string
  ano_lancamento: number | null
  url_poster: string | null
  genero_principal: string | null
  generos: string[]
  nota_usuario: number | null
  tipo: 'avaliado' | 'recomendado'
  afinidade: number | null
}

export interface ArestaMapaGostos {
  origem: string
  destino: string
  peso: number
  explicacao: string
}

export interface MapaGostos {
  nos: NoMapaGostos[]
  arestas: ArestaMapaGostos[]
  total_avaliados: number
  limite_nos: number
  vizinhos_por_filme: number
}


export interface PessoaComunidade {
  id: string
  nome: string
  avatar_url: string | null
}

export interface ContatoAmizade {
  id: string
  nome: string
  avatar_url: string | null
}

export type StatusSolicitacaoAmizade = 'pendente' | 'aceita' | 'bloqueada'

export interface SolicitacaoAmizade {
  id: string
  status: StatusSolicitacaoAmizade
  direcao: 'enviada' | 'recebida'
  pessoa: ContatoAmizade
  criada_em: string
}

export interface ComunidadeLeitura {
  id: string
  nome: string
  descricao: string
  imagem_url: string | null
  quantidade_membros: number
  visualizacoes: number
  criada_em: string
}

export interface ComunidadeCriacao {
  nome: string
  descricao: string
  imagem_url?: string | null
}

export interface ComentarioComunidade {
  id: string
  conteudo: string
  removida_por_moderacao: boolean
  autor: PessoaComunidade
  criado_em: string
}

export type TipoReacao = 'curtir' | 'amei' | 'interessante' | 'nao_curti'

export interface ReacaoComunidade {
  tipo: TipoReacao
  quantidade: number
}

export interface PublicacaoComunidade {
  id: string
  comunidade_id: string
  conteudo: string
  removida_por_moderacao: boolean
  autor: PessoaComunidade
  filme: FilmeResumo | null
  comentarios: ComentarioComunidade[]
  reacoes: ReacaoComunidade[]
  criada_em: string
}

export interface PerfilPublico {
  id: string
  nome: string
  avatar_url: string | null
  quantidade_amigos: number
  avaliacoes: (AvaliacaoLeitura & { filme: FilmeResumo })[]
  listas_publicas: { id: string; nome: string; quantidade_filmes: number; filmes: FilmeResumo[] }[]
  comunidades: { id: string; nome: string; descricao: string }[]
}

export interface PerfilProprio {
  id: string
  nome: string
  avatar_url: string | null
  quantidade_amigos: number
  avaliacoes: (AvaliacaoLeitura & { filme: FilmeResumo })[]
  listas: {
    id: string
    nome: string
    visibilidade: VisibilidadeLista
    quantidade_filmes: number
    filmes: FilmeResumo[]
  }[]
  comunidades: { id: string; nome: string; descricao: string }[]
}

export type VisibilidadeLista = 'publica' | 'privada'

export interface ListaLeitura {
  id: string
  nome: string
  visibilidade: VisibilidadeLista
  quantidade_filmes: number
  capa_url: string | null
  criada_em: string
}

export interface ListaDetalhe extends ListaLeitura {
  filmes: FilmeResumo[]
}
