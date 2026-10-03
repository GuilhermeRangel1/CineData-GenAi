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
  ContextoConversaGenAi,
  RespostaGenAi,
  ConversaDetalhe,
  ConversaResumo,
} from '../types/api'
import { carregarSessao, obterTokenSessao } from '../auth/session'

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1'
const genAiApiBaseUrl = import.meta.env.VITE_GENAI_API_BASE_URL ?? '/genai/api/v1'
const CACHE_TTL_MS = 60_000
const MAPA_CACHE_TTL_MS = 30_000

type CacheEntry = { expiraEm: number; valor: unknown }
const cacheDeLeitura = new Map<string, CacheEntry>()
const leiturasPendentes = new Map<string, Promise<unknown>>()
const cacheMapaGostos = new Map<string, CacheEntry>()
const mapasPendentes = new Map<string, Promise<MapaGostos>>()
let geracaoCache = 0

export class ErroDaApi extends Error {
  readonly status: number
  readonly codigo: string | null
  constructor(message: string, status: number, codigo: string | null = null) {
    super(message)
    this.status = status
    this.codigo = codigo
  }
}

type ErroApiPayload = Partial<ErroApi> & {
  error?: { code?: string; message?: string }
}

async function obterErroDaResposta(resposta: Response): Promise<ErroDaApi> {
  const erro = (await resposta.json().catch(() => null)) as ErroApiPayload | null
  return new ErroDaApi(
    erro?.error?.message ?? erro?.mensagem ?? 'Não foi possível concluir a operação.',
    resposta.status,
    erro?.error?.code ?? erro?.codigo ?? null,
  )
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
    throw await obterErroDaResposta(resposta)
  }
  if (resposta.status === 204) return undefined as T
  return resposta.json() as Promise<T>
}

async function requisitarGenAi<T>(caminho: string, init?: RequestInit): Promise<T> {
  let resposta: Response
  try {
    resposta = await fetch(`${genAiApiBaseUrl}${caminho}`, {
      ...init,
      headers: {
        ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
        ...init?.headers,
      },
    })
  } catch {
    throw new ErroDaApi(
      'Não consegui conectar ao chatbot. Verifique se o serviço está disponível e tente novamente.',
      0,
      'network_error',
    )
  }

  if (!resposta.ok) throw await obterErroDaResposta(resposta)
  return resposta.json() as Promise<T>
}

async function requisitarComCache<T>(caminho: string, signal?: AbortSignal): Promise<T> {
  const chave = `${apiBaseUrl}${caminho}`
  const entrada = cacheDeLeitura.get(chave)
  if (entrada && entrada.expiraEm > Date.now()) return entrada.valor as T
  const pendente = leiturasPendentes.get(chave)
  if (pendente) return pendente as Promise<T>
  const geracao = geracaoCache
  const pedido = requisitar<T>(caminho, { signal, cache: 'no-store' }).then((dados) => {
    if (geracao === geracaoCache)
      cacheDeLeitura.set(chave, { expiraEm: Date.now() + CACHE_TTL_MS, valor: dados })
    return dados
  })
  if (signal) return pedido
  const compartilhado = pedido.finally(() => {
    if (leiturasPendentes.get(chave) === compartilhado) leiturasPendentes.delete(chave)
  })
  leiturasPendentes.set(chave, compartilhado)
  return compartilhado
}

export function obterPaginaFilmesEmCache(parametros: URLSearchParams): Pagina<FilmeResumo> | null {
  const chave = `${apiBaseUrl}/filmes?${parametros.toString()}`
  const entrada = cacheDeLeitura.get(chave)
  if (!entrada) return null
  if (entrada.expiraEm <= Date.now()) {
    cacheDeLeitura.delete(chave)
    return null
  }
  return entrada.valor as Pagina<FilmeResumo>
}

function invalidarCacheDeFilmes() {
  geracaoCache += 1
  cacheDeLeitura.clear()
  cacheMapaGostos.clear()
  leiturasPendentes.clear()
  mapasPendentes.clear()
}

/** Uso exclusivo dos testes: cada caso começa sem respostas em memória. */
export function limparCacheDaApiParaTeste() {
  geracaoCache += 1
  cacheDeLeitura.clear()
  leiturasPendentes.clear()
  cacheMapaGostos.clear()
  mapasPendentes.clear()
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
  forcarAtualizacao = false,
): Promise<MapaGostos> {
  const consulta = new URLSearchParams({
    limite_nos: String(parametros.limiteNos),
    vizinhos_por_filme: String(parametros.vizinhosPorFilme),
  })
  if (parametros.busca?.trim()) consulta.set('busca', parametros.busca.trim())
  parametros.excluir?.forEach((id) => consulta.append('excluir', id))
  const chave = `${carregarSessao()?.usuario.id ?? 'visitante'}:${consulta.toString()}`
  const entrada = cacheMapaGostos.get(chave)
  if (!forcarAtualizacao && entrada && entrada.expiraEm > Date.now())
    return Promise.resolve(entrada.valor as MapaGostos)
  const pendente = mapasPendentes.get(chave)
  if (!forcarAtualizacao && pendente) return pendente
  const geracao = geracaoCache
  const request = requisitar<MapaGostos>(`/mapa-de-gostos?${consulta.toString()}`, {
    signal,
    cache: 'no-store',
  })
  const promise = request.then((mapa) => {
    if (geracao === geracaoCache)
      cacheMapaGostos.set(chave, { valor: mapa, expiraEm: Date.now() + MAPA_CACHE_TTL_MS })
    return mapa
  }).finally(() => {
    if (mapasPendentes.get(chave) === promise) mapasPendentes.delete(chave)
  })
  mapasPendentes.set(chave, promise)
  return promise
}

export function obterMapaGostosEmCache(
  parametros: { limiteNos: number; vizinhosPorFilme: number; excluir?: string[] },
): MapaGostos | null {
  const consulta = new URLSearchParams({
    limite_nos: String(parametros.limiteNos),
    vizinhos_por_filme: String(parametros.vizinhosPorFilme),
  })
  parametros.excluir?.forEach((id) => consulta.append('excluir', id))
  const entrada = cacheMapaGostos.get(`${carregarSessao()?.usuario.id ?? 'visitante'}:${consulta.toString()}`)
  return entrada && entrada.expiraEm > Date.now() ? entrada.valor as MapaGostos : null
}

export function perguntarGenAi(
  pergunta: string,
  contexto: ContextoConversaGenAi[] = [],
  conversationId?: string,
): Promise<RespostaGenAi> {
  return requisitarGenAi<RespostaGenAi>('/questions', {
    method: 'POST',
    body: JSON.stringify({ question: pergunta, context: contexto, conversation_id: conversationId }),
  })
}

export function listarConversas(signal?: AbortSignal): Promise<ConversaResumo[]> {
  return requisitar<ConversaResumo[]>('/minha-conta/conversas', { signal, cache: 'no-store' })
}

export function criarConversa(titulo: string): Promise<ConversaDetalhe> {
  return requisitar<ConversaDetalhe>('/minha-conta/conversas', {
    method: 'POST', body: JSON.stringify({ titulo }),
  })
}

export function obterConversa(id: string): Promise<ConversaDetalhe> {
  return requisitar<ConversaDetalhe>(`/minha-conta/conversas/${encodeURIComponent(id)}`, { cache: 'no-store' })
}

export function renomearConversa(id: string, titulo: string): Promise<ConversaResumo> {
  return requisitar<ConversaResumo>(`/minha-conta/conversas/${encodeURIComponent(id)}`, {
    method: 'PATCH', body: JSON.stringify({ titulo }),
  })
}

export function removerConversa(id: string): Promise<void> {
  return requisitar<void>(`/minha-conta/conversas/${encodeURIComponent(id)}`, { method: 'DELETE' })
}

export function anexarMensagensConversa(
  id: string,
  mensagens: Array<{ role: 'user' | 'assistant'; content: string; response_data?: RespostaGenAi }>,
): Promise<ConversaDetalhe> {
  return requisitar<ConversaDetalhe>(`/minha-conta/conversas/${encodeURIComponent(id)}/mensagens`, {
    method: 'POST', body: JSON.stringify({ mensagens }),
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
