import type {
  AvaliacaoCriacao,
  AvaliacaoLeitura,
  TokenAcesso,
  ErroApi,
  FilmeAtualizacao,
  FilmeCriacao,
  FilmeDetalhe,
  FilmeResumo,
  Pagina,
  UsuarioLeitura,
  ComentarioComunidade,
  ComunidadeCriacao,
  ComunidadeLeitura,
  PessoaComunidade,
  PerfilProprio,
  PerfilPublico,
  PublicacaoComunidade,
  ReacaoComunidade,
  TipoReacao,
  ListaDetalhe,
  ListaLeitura,
  VisibilidadeLista,
  ContatoAmizade,
  SolicitacaoAmizade,
  TmdbImportacao,
  TmdbResultado,
  ResumoAnalytics,
  MapaGostos,
  MensagemChatbot,
  RespostaChatbot,
} from '../types/api'
import { obterTokenSessao } from '../auth/session'

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1'
const CACHE_TTL_MS = 60_000

type CacheEntry = { expiraEm: number; valor: unknown }
const cacheDeLeitura = new Map<string, CacheEntry>()

export class ErroDaApi extends Error {
  readonly status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

async function requisitar<T>(caminho: string, init?: RequestInit): Promise<T> {
  const token = obterTokenSessao()
  const resposta = await fetch(`${apiBaseUrl}${caminho}`, {
    ...init,
    headers: {
      ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
  })

  if (!resposta.ok) {
    const erro = (await resposta.json().catch(() => null)) as ErroApi | null
    throw new ErroDaApi(erro?.mensagem ?? 'Não foi possível concluir a operação.', resposta.status)
  }
  if (resposta.status === 204) return undefined as T
  return resposta.json() as Promise<T>
}

async function requisitarComCache<T>(caminho: string, signal?: AbortSignal): Promise<T> {
  const chave = `${apiBaseUrl}${caminho}`
  const entrada = cacheDeLeitura.get(chave)
  if (entrada && entrada.expiraEm > Date.now()) return entrada.valor as T

  const dados = await requisitar<T>(caminho, { signal, cache: 'no-store' })
  cacheDeLeitura.set(chave, { expiraEm: Date.now() + CACHE_TTL_MS, valor: dados })
  return dados
}

function invalidarCacheDeFilmes() {
  cacheDeLeitura.clear()
}

/** Uso exclusivo dos testes: cada caso começa sem respostas em memória. */
export function limparCacheDaApiParaTeste() {
  cacheDeLeitura.clear()
}

export function registrar(dados: {
  nome: string
  email: string
  senha: string
}): Promise<UsuarioLeitura> {
  return requisitar<UsuarioLeitura>('/auth/cadastro', {
    method: 'POST',
    body: JSON.stringify(dados),
  })
}

export function entrar(dados: { email: string; senha: string }): Promise<TokenAcesso> {
  return requisitar<TokenAcesso>('/auth/login', {
    method: 'POST',
    body: JSON.stringify(dados),
  })
}

export function atualizarPerfil(dados: {
  nome?: string
  avatar_url?: string | null
}): Promise<UsuarioLeitura> {
  return requisitar<UsuarioLeitura>('/auth/perfil', {
    method: 'PATCH',
    body: JSON.stringify(dados),
  })
}

export function buscarFilmesTmdb(busca: string): Promise<TmdbResultado[]> {
  return requisitar<TmdbResultado[]>(`/admin/fontes/tmdb/busca?busca=${encodeURIComponent(busca)}`, {
    cache: 'no-store',
  })
}

export function obterFilmeTmdb(id: number): Promise<TmdbImportacao> {
  return requisitar<TmdbImportacao>(`/admin/fontes/tmdb/${id}`, { cache: 'no-store' })
}

export function obterResumoAnalytics(
  periodoDias: number,
  signal?: AbortSignal,
): Promise<ResumoAnalytics> {
  return requisitar<ResumoAnalytics>(`/admin/analytics/resumo?periodo_dias=${periodoDias}`, {
    signal,
    cache: 'no-store',
  })
}

export function obterMapaGostos(
  parametros: { limiteNos: number; vizinhosPorFilme: number; busca?: string; excluir?: string[] },
  signal?: AbortSignal,
): Promise<MapaGostos> {
  const consulta = new URLSearchParams({
    limite_nos: String(parametros.limiteNos),
    vizinhos_por_filme: String(parametros.vizinhosPorFilme),
  })
  if (parametros.busca?.trim()) consulta.set('busca', parametros.busca.trim())
  parametros.excluir?.forEach((id) => consulta.append('excluir', id))
  return requisitar<MapaGostos>(`/mapa-de-gostos?${consulta.toString()}`, {
    signal,
    cache: 'no-store',
  })
}

export function conversarComAssistente(mensagens: MensagemChatbot[]): Promise<RespostaChatbot> {
  return requisitar<RespostaChatbot>('/assistente/mensagens', {
    method: 'POST',
    body: JSON.stringify({ mensagens }),
  })
}

export function listarFilmes(
  parametros: URLSearchParams,
  signal?: AbortSignal,
): Promise<Pagina<FilmeResumo>> {
  return requisitarComCache(`/filmes?${parametros.toString()}`, signal)
}

export function obterFilme(id: string, signal?: AbortSignal): Promise<FilmeDetalhe> {
  return requisitarComCache(`/filmes/${encodeURIComponent(id)}`, signal)
}

export async function criarFilme(dados: FilmeCriacao): Promise<FilmeDetalhe> {
  const filme = await requisitar<FilmeDetalhe>('/filmes', {
    method: 'POST',
    body: JSON.stringify(dados),
  })
  invalidarCacheDeFilmes()
  return filme
}

export async function atualizarFilme(id: string, dados: FilmeAtualizacao): Promise<FilmeDetalhe> {
  const filme = await requisitar<FilmeDetalhe>(`/filmes/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    body: JSON.stringify(dados),
  })
  invalidarCacheDeFilmes()
  return filme
}

export async function removerFilme(id: string): Promise<void> {
  await requisitar<void>(`/filmes/${encodeURIComponent(id)}`, { method: 'DELETE' })
  invalidarCacheDeFilmes()
}

export async function criarAvaliacao(
  id: string,
  dados: AvaliacaoCriacao,
): Promise<AvaliacaoLeitura> {
  const avaliacao = await requisitar<AvaliacaoLeitura>(
    `/filmes/${encodeURIComponent(id)}/avaliacoes`,
    {
    method: 'POST',
    body: JSON.stringify(dados),
    },
  )
  invalidarCacheDeFilmes()
  return avaliacao
}

export function obterMinhaAvaliacao(
  id: string,
  signal?: AbortSignal,
): Promise<AvaliacaoLeitura | null> {
  return requisitar<AvaliacaoLeitura | null>(`/filmes/${encodeURIComponent(id)}/minha-avaliacao`, {
    signal,
    cache: 'no-store',
  })
}

export async function removerMinhaAvaliacao(id: string): Promise<void> {
  await requisitar<void>(`/filmes/${encodeURIComponent(id)}/minha-avaliacao`, {
    method: 'DELETE',
  })
  invalidarCacheDeFilmes()
}

export function obterTrailerFilme(id: string, signal?: AbortSignal): Promise<{ url_trailer: string | null }> {
  return requisitarComCache(`/filmes/${encodeURIComponent(id)}/trailer`, signal)
}

export function listarComunidades(signal?: AbortSignal): Promise<ComunidadeLeitura[]> {
  return requisitar<ComunidadeLeitura[]>('/comunidades', { signal, cache: 'no-store' })
}

export function registrarVisualizacaoComunidade(id: string): Promise<ComunidadeLeitura> {
  return requisitar<ComunidadeLeitura>(`/comunidades/${encodeURIComponent(id)}/visualizacoes`, { method: 'POST' })
}

export function obterPerfilPublico(id: string, signal?: AbortSignal): Promise<PerfilPublico> {
  return requisitar<PerfilPublico>(`/perfis/${encodeURIComponent(id)}`, { signal })
}

export function entrarComoAdministradorDeTeste(): Promise<TokenAcesso> {
  return requisitar<TokenAcesso>('/auth/sessao-teste', { method: 'POST' })
}

export function obterPerfilProprio(signal?: AbortSignal): Promise<PerfilProprio> {
  return requisitar<PerfilProprio>('/auth/perfil', { signal, cache: 'no-store' })
}

export function criarComunidade(dados: ComunidadeCriacao): Promise<ComunidadeLeitura> {
  return requisitar<ComunidadeLeitura>('/comunidades', {
    method: 'POST',
    body: JSON.stringify(dados),
  })
}

export function atualizarComunidade(
  id: string,
  dados: Partial<ComunidadeCriacao>,
): Promise<ComunidadeLeitura> {
  return requisitar<ComunidadeLeitura>(`/comunidades/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    body: JSON.stringify(dados),
  })
}

export function removerComunidade(id: string): Promise<void> {
  return requisitar<void>(`/comunidades/${encodeURIComponent(id)}`, { method: 'DELETE' })
}

export function listarMembrosComunidade(
  id: string,
  signal?: AbortSignal,
): Promise<PessoaComunidade[]> {
  return requisitar<PessoaComunidade[]>(`/comunidades/${encodeURIComponent(id)}/membros`, {
    signal,
    cache: 'no-store',
  })
}

export function entrarNaComunidade(id: string): Promise<void> {
  return requisitar<void>(`/comunidades/${encodeURIComponent(id)}/participacao`, {
    method: 'POST',
  })
}

export function sairDaComunidade(id: string): Promise<void> {
  return requisitar<void>(`/comunidades/${encodeURIComponent(id)}/participacao`, {
    method: 'DELETE',
  })
}

export function listarPublicacoesComunidade(
  id: string,
  signal?: AbortSignal,
): Promise<PublicacaoComunidade[]> {
  return requisitar<PublicacaoComunidade[]>(
    `/comunidades/${encodeURIComponent(id)}/publicacoes`,
    { signal, cache: 'no-store' },
  )
}

export function criarPublicacaoComunidade(
  id: string,
  dados: { conteudo: string; movie_id?: string },
): Promise<PublicacaoComunidade> {
  return requisitar<PublicacaoComunidade>(
    `/comunidades/${encodeURIComponent(id)}/publicacoes`,
    { method: 'POST', body: JSON.stringify(dados) },
  )
}

export function comentarPublicacao(
  id: string,
  conteudo: string,
): Promise<ComentarioComunidade> {
  return requisitar<ComentarioComunidade>(
    `/comunidades/publicacoes/${encodeURIComponent(id)}/comentarios`,
    { method: 'POST', body: JSON.stringify({ conteudo }) },
  )
}

export function removerPublicacaoComunidade(id: string): Promise<void> {
  return requisitar<void>(`/comunidades/publicacoes/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  })
}

export function removerComentarioComunidade(id: string): Promise<void> {
  return requisitar<void>(`/comunidades/comentarios/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  })
}

export function reagirPublicacao(
  id: string,
  tipo: TipoReacao,
): Promise<ReacaoComunidade[]> {
  return requisitar<ReacaoComunidade[]>(
    `/comunidades/publicacoes/${encodeURIComponent(id)}/reacoes`,
    { method: 'POST', body: JSON.stringify({ tipo }) },
  )
}

export function removerReacaoPublicacao(id: string): Promise<void> {
  return requisitar<void>(`/comunidades/publicacoes/${encodeURIComponent(id)}/reacoes`, {
    method: 'DELETE',
  })
}

export function listarAmigos(signal?: AbortSignal): Promise<ContatoAmizade[]> {
  return requisitar<ContatoAmizade[]>('/minha-conta/amigos', { signal, cache: 'no-store' })
}

export function listarSolicitacoesAmizade(signal?: AbortSignal): Promise<SolicitacaoAmizade[]> {
  return requisitar<SolicitacaoAmizade[]>('/minha-conta/amigos/solicitacoes', { signal, cache: 'no-store' })
}

export function pesquisarPessoas(busca: string, signal?: AbortSignal): Promise<ContatoAmizade[]> {
  return requisitar<ContatoAmizade[]>(`/minha-conta/amigos/pesquisa?busca=${encodeURIComponent(busca)}`, { signal, cache: 'no-store' })
}

export function enviarSolicitacaoAmizade(usuarioId: string): Promise<SolicitacaoAmizade> {
  return requisitar<SolicitacaoAmizade>(`/minha-conta/amigos/solicitacoes/${encodeURIComponent(usuarioId)}`, { method: 'POST' })
}

export function responderSolicitacaoAmizade(
  solicitacaoId: string,
  acao: 'aceitar' | 'bloquear',
): Promise<SolicitacaoAmizade> {
  return requisitar<SolicitacaoAmizade>(`/minha-conta/amigos/solicitacoes/${encodeURIComponent(solicitacaoId)}`, {
    method: 'PATCH',
    body: JSON.stringify({ acao }),
  })
}

export function removerAmigo(usuarioId: string): Promise<void> {
  return requisitar<void>(`/minha-conta/amigos/${encodeURIComponent(usuarioId)}`, { method: 'DELETE' })
}

export function listarListas(signal?: AbortSignal): Promise<ListaLeitura[]> {
  return requisitar<ListaLeitura[]>('/minha-conta/listas', { signal, cache: 'no-store' })
}

export function obterLista(id: string, signal?: AbortSignal): Promise<ListaDetalhe> {
  return requisitar<ListaDetalhe>(`/minha-conta/listas/${encodeURIComponent(id)}`, { signal, cache: 'no-store' })
}

export function criarLista(dados: { nome: string; visibilidade: VisibilidadeLista }): Promise<ListaLeitura> {
  return requisitar<ListaLeitura>('/minha-conta/listas', { method: 'POST', body: JSON.stringify(dados) })
}

export function atualizarLista(id: string, dados: { nome?: string; visibilidade?: VisibilidadeLista }): Promise<ListaLeitura> {
  return requisitar<ListaLeitura>(`/minha-conta/listas/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(dados) })
}

export function removerLista(id: string): Promise<void> {
  return requisitar<void>(`/minha-conta/listas/${encodeURIComponent(id)}`, { method: 'DELETE' })
}

export function adicionarFilmeALista(listaId: string, filmeId: string): Promise<ListaDetalhe> {
  return requisitar<ListaDetalhe>(`/minha-conta/listas/${encodeURIComponent(listaId)}/filmes/${encodeURIComponent(filmeId)}`, { method: 'POST' })
}

export function removerFilmeDaLista(listaId: string, filmeId: string): Promise<void> {
  return requisitar<void>(`/minha-conta/listas/${encodeURIComponent(listaId)}/filmes/${encodeURIComponent(filmeId)}`, { method: 'DELETE' })
}

export function listarAssistirDepois(signal?: AbortSignal): Promise<FilmeResumo[]> {
  return requisitar<FilmeResumo[]>('/minha-conta/assistir-depois', { signal, cache: 'no-store' })
}

export function adicionarAssistirDepois(filmeId: string): Promise<void> {
  return requisitar<void>(`/minha-conta/assistir-depois/${encodeURIComponent(filmeId)}`, { method: 'PUT' })
}

export function removerAssistirDepois(filmeId: string): Promise<void> {
  return requisitar<void>(`/minha-conta/assistir-depois/${encodeURIComponent(filmeId)}`, { method: 'DELETE' })
}

export function listarFilmesAvaliados(signal?: AbortSignal): Promise<FilmeResumo[]> {
  return requisitar<FilmeResumo[]>('/minha-conta/filmes-avaliados', { signal, cache: 'no-store' })
}
