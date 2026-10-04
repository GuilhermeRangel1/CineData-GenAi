import { useEffect, useRef, useState, type FormEvent } from 'react'
import {
  anexarMensagensConversa,
  criarConversa,
  ErroDaApi,
  listarConversas,
  obterCapacidadesGenAi,
  obterConversa,
  perguntarGenAi,
  removerConversa,
  renomearConversa,
} from '../api/client'
import type { ContextoConversaGenAi, ConversaResumo, MensagemConversa, RespostaGenAi } from '../types/api'
import { ChatbotRobot, type RobotMood } from './ChatbotRobot'
import { baixarResultadoCsv } from './chatbotExport'
import { ChatbotResultChart, temGraficoDeResultado } from './ChatbotResultChart'
import { colunasVisiveis, formatarCelula, observacaoResultado, rotuloColuna, tituloResultado } from './chatbotPresentation'
import './ChatbotHub.css'

const SUGESTOES = [
  'Quais são os 10 filmes com maior receita em BRL?',
  'Qual é o lucro médio em BRL por gênero?',
  'Qual é a nota IMDb média por ano de lançamento?',
]
const AJUDA_SUGESTOES = [
  {
    titulo: 'Explorar o CineData',
    tema: 'explorar',
    perguntas: [
      'O que o chatbot faz?',
      'Como usar a busca de filmes?',
      'Como criar uma lista no CineData?',
      'Como encontro amigos no CineData?',
      'Como funciona a aba Comunidades?',
      'Como funciona o mapa de gostos no CineData?',
    ],
  },
  {
    titulo: 'Painel administrativo',
    tema: 'admin',
    exigeAdmin: true,
    perguntas: ['O que mostra a aba Analytics?'],
  },
  {
    titulo: 'Finanças',
    tema: 'financas',
    perguntas: [
      'Quais são os 10 filmes com maior receita em BRL?',
      'Qual é o lucro médio em BRL por gênero?',
      'Quais filmes têm as maiores margens de lucro?',
    ],
  },
  {
    titulo: 'Popularidade e notas',
    tema: 'notas',
    perguntas: [
      'Quais são os 5 filmes mais populares?',
      'Em quais filmes há maior divergência entre as notas TMDB e IMDb?',
      'Qual é a nota IMDb média por ano de lançamento?',
    ],
  },
  {
    titulo: 'Elenco e direção',
    tema: 'pessoas',
    perguntas: [
      'Qual ator participou de mais filmes nos últimos cinco anos?',
      'Quais diretores têm a maior nota IMDb média considerando no mínimo cinco filmes?',
      'Qual dupla de ator e diretor trabalhou junta em mais filmes?',
    ],
  },
  {
    titulo: 'Gêneros e produtoras',
    tema: 'generos',
    perguntas: [
      'Quantos filmes existem associados a cada gênero?',
      'Qual produtora acumulou o maior lucro total em BRL?',
      'Qual gênero tem a maior margem média de lucro?',
    ],
  },
  {
    titulo: 'Avaliações do público',
    tema: 'avaliacoes',
    perguntas: [
      'Quais filmes têm a maior quantidade de avaliações de usuários?',
      'Qual filme tem a maior divergência entre a média dos usuários e a nota IMDb?',
    ],
  },
]
const FALAS: Record<RobotMood, string> = {
  idle: 'Tenho um universo de filmes para explorar com você.',
  listening: 'Pode escrever. Estou de olho na sua pergunta!',
  thinking: 'Um instante. Vou consultar os dados para você.',
  happy: 'Prontinho! Olha o que encontrei para você.',
  error: 'Vamos tentar de novo? Estou por aqui.',
  waving: 'Oii! Que bom ter você por aqui.',
}

type MensagemAssistente = MensagemConversa & { resposta?: RespostaGenAi }

function contextoDaConversa(mensagens: MensagemAssistente[]): ContextoConversaGenAi[] {
  const contexto = mensagens.flatMap((mensagem, indice) => {
    const perguntaAnterior = mensagens[indice - 1]
    if (mensagem.role !== 'assistant' || !mensagem.resposta || perguntaAnterior?.role !== 'user') return []
    const { metadata } = mensagem.resposta
    return [{
      question: perguntaAnterior.conteudo,
      metric: metadata.metric,
      unit: metadata.unit,
      period: metadata.period,
      population: metadata.population,
    }]
  })
  return contexto.length ? [contexto.at(-1)!] : []
}

function criarIdConversa() {
  return globalThis.crypto?.randomUUID?.() ?? `chat-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

function SendIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 12 20 4l-5 16-3-7-8-1Zm8 1 8-9" />
    </svg>
  )
}

export function ChatbotHub({ isAdmin = false, isAuthenticated = false }: { isAdmin?: boolean; isAuthenticated?: boolean }) {
  const [mensagens, setMensagens] = useState<MensagemAssistente[]>([])
  const [texto, setTexto] = useState('')
  const [erro, setErro] = useState('')
  const [perguntaFalhou, setPerguntaFalhou] = useState('')
  const [carregando, setCarregando] = useState(false)
  const [progresso, setProgresso] = useState('')
  const [focado, setFocado] = useState(false)
  const [ajudaAberta, setAjudaAberta] = useState(false)
  const [gesto, setGesto] = useState<'happy' | 'waving' | null>(null)
  const [conversasSalvas, setConversasSalvas] = useState<ConversaResumo[]>([])
  const [conversaAtiva, setConversaAtiva] = useState<string | null>(null)
  const [tituloConversaAtiva, setTituloConversaAtiva] = useState('')
  const [modoTemporario, setModoTemporario] = useState(!isAuthenticated)
  const [carregandoHistorico, setCarregandoHistorico] = useState(false)
  const [abrindoConversa, setAbrindoConversa] = useState(false)
  const [erroHistorico, setErroHistorico] = useState('')
  const [versaoHistorico, setVersaoHistorico] = useState(0)
  const [analiseDisponivel, setAnaliseDisponivel] = useState<boolean | null>(null)
  const conversa = useRef<HTMLDivElement>(null)
  const entrada = useRef<HTMLTextAreaElement>(null)
  const botaoAjuda = useRef<HTMLButtonElement>(null)
  const idConversa = useRef(criarIdConversa())
  const estado: RobotMood = carregando ? 'thinking' : gesto ?? (erro ? 'error' : focado || texto ? 'listening' : 'idle')

  useEffect(() => {
    let active = true
    void obterCapacidadesGenAi().then((capacidades) => {
      if (active) setAnaliseDisponivel(capacidades.analytics_available)
    }).catch(() => {
      // A API da pergunta ainda informa erros caso a verificação falhe.
    })
    return () => { active = false }
  }, [])

  useEffect(() => {
    if (!isAuthenticated) {
      setConversasSalvas([])
      setConversaAtiva(null)
      setTituloConversaAtiva('')
      setModoTemporario(true)
      setErroHistorico('')
      return
    }
    setModoTemporario(false)
  }, [isAuthenticated])

  useEffect(() => {
    if (!isAuthenticated) return
    let active = true
    setCarregandoHistorico(true)
    setErroHistorico('')
    void listarConversas().then((items) => {
      if (active) setConversasSalvas(items)
    }).catch(() => {
      if (active) setErroHistorico('Não foi possível carregar suas conversas.')
    }).finally(() => {
      if (active) setCarregandoHistorico(false)
    })
    return () => { active = false }
  }, [isAuthenticated, versaoHistorico])

  useEffect(() => {
    const painel = conversa.current
    if (!painel) return
    painel.scrollTop = painel.scrollHeight
  }, [mensagens, carregando])

  useEffect(() => {
    if (!gesto) return
    const timer = window.setTimeout(() => setGesto(null), 3200)
    return () => window.clearTimeout(timer)
  }, [gesto])

  async function enviar(mensagem = texto, adicionarAoHistorico = true) {
    const conteudo = mensagem.trim()
    if (!conteudo || carregando) return

    if (adicionarAoHistorico) {
      const mensagemUsuario: MensagemConversa = { role: 'user', conteudo }
      setMensagens((atuais) => [...atuais, mensagemUsuario])
    }
    setTexto('')
    setErro('')
    setAjudaAberta(false)
    setGesto(null)
    setProgresso('Entendendo sua pergunta…')
    setCarregando(true)

    try {
      const resposta = await perguntarGenAi(
        conteudo,
        contextoDaConversa(mensagens),
        idConversa.current,
        (etapa) => setProgresso(etapa.message),
      )
      setMensagens((atuais) => [...atuais, { role: 'assistant', conteudo: resposta.answer, resposta }])
      setGesto('happy')
      setPerguntaFalhou('')
      if (isAuthenticated && !modoTemporario) {
        let id = conversaAtiva
        try {
          if (!id) {
            const conversaCriada = await criarConversa(conteudo.slice(0, 120))
            id = conversaCriada.id
            setConversaAtiva(id)
            setTituloConversaAtiva(conversaCriada.titulo)
          }
          const conversaAtualizada = await anexarMensagensConversa(id, [
            { role: 'user', content: conteudo },
            { role: 'assistant', content: resposta.answer, response_data: resposta },
          ])
          setConversasSalvas((atuais) => [
            { id: conversaAtualizada.id, titulo: conversaAtualizada.titulo, created_at: conversaAtualizada.created_at, updated_at: conversaAtualizada.updated_at },
            ...atuais.filter((conversa) => conversa.id !== conversaAtualizada.id),
          ])
          setErroHistorico('')
        } catch {
          setErroHistorico('A resposta foi exibida, mas não pôde ser salva no histórico.')
        }
      }
    } catch (falha) {
      if (falha instanceof ErroDaApi && falha.codigo === 'ambiguous_question') {
        setErro(`Preciso de um detalhe para continuar: ${falha.message}`)
      } else if (falha instanceof ErroDaApi && falha.codigo === 'guardrail_rejected') {
        setErro(falha.message)
        setPerguntaFalhou('')
      } else if (falha instanceof ErroDaApi && falha.codigo === 'provider_not_configured') {
        setAnaliseDisponivel(false)
        setErro(falha.message)
        setPerguntaFalhou('')
      } else {
        setErro(falha instanceof Error ? falha.message : 'Não consegui responder agora. Tente novamente.')
        setPerguntaFalhou(conteudo)
      }
    } finally {
      setCarregando(false)
      setProgresso('')
    }
  }

  function enviarFormulario(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    void enviar()
  }

  function limparConversa() {
    if (carregando) return
    setMensagens([])
    setTexto('')
    setErro('')
    setPerguntaFalhou('')
    setAjudaAberta(false)
    setGesto(null)
    idConversa.current = criarIdConversa()
    entrada.current?.focus({ preventScroll: true })
  }

  function iniciarConversa(temporaria: boolean) {
    if (carregando) return
    limparConversa()
    setConversaAtiva(null)
    setTituloConversaAtiva('')
    setModoTemporario(temporaria || !isAuthenticated)
  }

  async function abrirConversa(id: string) {
    if (carregando || id === conversaAtiva) return
    const resumo = conversasSalvas.find((conversaSalva) => conversaSalva.id === id)
    setAbrindoConversa(true)
    setErro('')
    try {
      const conversaSalva = await obterConversa(id)
      setMensagens(conversaSalva.mensagens.map((mensagem) => ({
        role: mensagem.role,
        conteudo: mensagem.content,
        resposta: mensagem.response_data ?? undefined,
      })))
      setConversaAtiva(id)
      setTituloConversaAtiva(conversaSalva.titulo)
      setModoTemporario(false)
      idConversa.current = criarIdConversa()
    } catch (falha) {
      setErro(falha instanceof Error ? falha.message : 'Não foi possível abrir esta conversa.')
      setTituloConversaAtiva(resumo?.titulo ?? '')
    } finally {
      setAbrindoConversa(false)
    }
  }

  async function excluirConversa(id: string) {
    if (carregando) return
    try {
      await removerConversa(id)
      setConversasSalvas((atuais) => atuais.filter((conversa) => conversa.id !== id))
      if (conversaAtiva === id) iniciarConversa(false)
    } catch (falha) {
      setErro(falha instanceof Error ? falha.message : 'Não foi possível excluir esta conversa.')
    }
  }

  async function editarTitulo(conversa: ConversaResumo) {
    const titulo = window.prompt('Nome da conversa', conversa.titulo)?.trim()
    if (!titulo || titulo === conversa.titulo) return
    try {
      const atualizada = await renomearConversa(conversa.id, titulo)
      setConversasSalvas((atuais) => atuais.map((item) => item.id === atualizada.id ? atualizada : item))
    } catch (falha) {
      setErro(falha instanceof Error ? falha.message : 'Não foi possível renomear esta conversa.')
    }
  }

  return (
    <main className="chatbot-page chatbot-motion-on" id="chatbot">
      <header className="chatbot-header">
        <div className="chatbot-header-copy">
          <p className="eyebrow chatbot-eyebrow"><span className="red-line" />BOAS CONVERSAS COMEÇAM COM CINEMA</p>
          <h1>Chatbot</h1>
        </div>
      </header>

      <div className="chatbot-content">
        <section className={`chatbot-chat-area ${mensagens.length ? 'has-messages' : ''}`} aria-label="Conversa no chatbot">
          <aside className="chatbot-companion" aria-label="Seu companheiro de cinema">
          <div className="chatbot-companion-heading">{carregando && <span className={`chatbot-state chatbot-state--${estado}`}><i />CONSULTANDO</span>}</div>
          <div className="chatbot-robot-scene">
            <div className="chatbot-orbit chatbot-orbit--one" aria-hidden="true" />
            <div className="chatbot-orbit chatbot-orbit--two" aria-hidden="true" />
            <span className="chatbot-star chatbot-star--one" aria-hidden="true">+</span>
            <span className="chatbot-star chatbot-star--two" aria-hidden="true">✦</span>
            <span className="chatbot-star chatbot-star--three" aria-hidden="true">·</span>
            <button className="chatbot-robot-button" type="button" aria-label="Acenar para o robô" onClick={() => setGesto('waving')} disabled={carregando || gesto === 'waving'}>
              <ChatbotRobot mood={estado} incognito={modoTemporario} />
            </button>
          </div>
          <p className="sr-only" role="status">{FALAS[estado]}</p>
            <section className="chatbot-history" aria-label={isAuthenticated ? 'Conversas salvas' : 'Nova conversa'}>
              <div><strong>{isAuthenticated ? 'Suas conversas' : 'Conversa temporária'}</strong><button className="chatbot-history-create" type="button" aria-label="Criar nova conversa" title="Nova conversa" onClick={() => iniciarConversa(false)} disabled={carregando}><span aria-hidden="true" /></button></div>
              {!isAuthenticated ? <p>Entre na sua conta para salvar conversas.</p> : carregandoHistorico ? <p>Carregando conversas…</p> : erroHistorico ? <p className="chatbot-history-error">{erroHistorico} <button type="button" onClick={() => setVersaoHistorico((versao) => versao + 1)}>Tentar novamente</button></p> : conversasSalvas.length === 0 ? <p>Nenhuma conversa salva ainda.</p> : (
                <ul>{conversasSalvas.map((conversaSalva) => (
                  <li key={conversaSalva.id} className={conversaAtiva === conversaSalva.id ? 'is-active' : undefined}>
                    <button type="button" onClick={() => void abrirConversa(conversaSalva.id)} disabled={carregandoHistorico}>{conversaSalva.titulo}</button>
                    <span><button type="button" aria-label={`Renomear ${conversaSalva.titulo}`} onClick={() => void editarTitulo(conversaSalva)}>✎</button><button type="button" aria-label={`Excluir ${conversaSalva.titulo}`} onClick={() => void excluirConversa(conversaSalva.id)}>×</button></span>
                  </li>
                ))}</ul>
              )}
            </section>
          <div className="chatbot-companion-footer"><span aria-hidden="true">✦</span></div>
          </aside>
          <div className="chatbot-chat-column">
            <div className="chatbot-conversation-heading">
            <div><span className="chatbot-mini-mark" aria-hidden="true">✦</span><h2>{abrindoConversa ? 'Abrindo conversa…' : tituloConversaAtiva || 'Conversa'}</h2></div>
            <div className="chatbot-conversation-actions">
              <button
                className={`chatbot-temporary-trigger ${modoTemporario ? 'is-active' : ''}`}
                type="button"
                aria-pressed={modoTemporario}
                aria-label={modoTemporario ? 'Desativar modo temporário' : 'Ativar modo temporário'}
                title={!isAuthenticated ? 'Entre na sua conta para alternar entre conversas salvas e temporárias' : undefined}
                onClick={() => iniciarConversa(!modoTemporario)}
                disabled={carregando || !isAuthenticated}
              >
                Temporário
              </button>
              <button
                ref={botaoAjuda}
                className="chatbot-help-trigger"
                type="button"
                aria-expanded={ajudaAberta}
                aria-controls={ajudaAberta ? 'chatbot-help-panel' : undefined}
                onClick={() => setAjudaAberta((aberta) => !aberta)}
                onKeyDown={(event) => { if (event.key === 'Escape') setAjudaAberta(false) }}
              >Ajuda</button>
            </div>
          </div>
          {analiseDisponivel === false && (
            <div className="chatbot-setup-notice" aria-label="Configuração do chatbot">
              <strong>Consultas aos filmes precisam de uma chave Gemini.</strong>
              <span>Preencha <code>GENAI_GEMINI_API_KEY</code> em <code>genai/.env</code> e reinicie o serviço GenAI. A ajuda sobre o CineData continua disponível.</span>
            </div>
          )}
          {ajudaAberta && (
            <div
              className="chatbot-help-panel"
              id="chatbot-help-panel"
              role="region"
              aria-label="Perguntas sugeridas"
              onKeyDown={(event) => {
                if (event.key === 'Escape') {
                  setAjudaAberta(false)
                  botaoAjuda.current?.focus()
                }
              }}
            >
              {AJUDA_SUGESTOES.filter((grupo) => !grupo.exigeAdmin || isAdmin).map((grupo) => (
                <div className={`chatbot-help-group chatbot-help-group--${grupo.tema}`} key={grupo.titulo}>
                  <h3>{grupo.titulo}</h3>
                  {grupo.perguntas.map((pergunta) => (
                    <button key={pergunta} type="button" disabled={carregando || (analiseDisponivel === false && grupo.tema !== 'explorar' && grupo.tema !== 'admin')} title={analiseDisponivel === false && grupo.tema !== 'explorar' && grupo.tema !== 'admin' ? 'Configure a chave Gemini para consultar os filmes' : undefined} onClick={() => void enviar(pergunta)}>
                      {pergunta}<span aria-hidden="true">↗</span>
                    </button>
                  ))}
                </div>
              ))}
            </div>
          )}
          {abrindoConversa ? (
            <div className="chatbot-opening" role="status">Carregando mensagens salvas…</div>
          ) : mensagens.length === 0 && conversaAtiva ? (
            <div className="chatbot-opening">
              <strong>{tituloConversaAtiva || 'Conversa salva'}</strong>
              <span>Esta conversa ainda não tem mensagens salvas.</span>
            </div>
          ) : mensagens.length === 0 ? (
            <div className="chatbot-welcome">
              <span className="chatbot-welcome-symbol" aria-hidden="true">✳</span>
              <h3>O que vamos descobrir?</h3>
              <div className="chatbot-suggestions" aria-label="Sugestões para começar">
                {SUGESTOES.map((sugestao, index) => (
                  <button key={sugestao} type="button" aria-label={sugestao} onClick={() => void enviar(sugestao)} disabled={carregando || analiseDisponivel === false} title={analiseDisponivel === false ? 'Configure a chave Gemini para consultar os filmes' : undefined}>
                    <span className="chatbot-suggestion-number">0{index + 1}</span><span>{sugestao}</span><span className="chatbot-suggestion-arrow" aria-hidden="true">↗</span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="chatbot-messages" ref={conversa} role="log" aria-label="Histórico da conversa" aria-live="polite" aria-relevant="additions text">
              {mensagens.map((mensagem, indice) => (
                <article key={`${indice}-${mensagem.role}`} className={`chatbot-message chatbot-message--${mensagem.role}`} data-chatbot-result={mensagem.resposta ? '' : undefined}>
                  {mensagem.role === 'assistant' && <span className="chatbot-message-avatar"><ChatbotRobot compact mood="happy" incognito={modoTemporario} /></span>}
                  {mensagem.resposta ? <ResultadoGenAi resposta={mensagem.resposta} /> : <p>{mensagem.conteudo}</p>}
                </article>
              ))}
              {carregando && (
                <article className="chatbot-message chatbot-message--assistant chatbot-message--loading" aria-label="Chatbot está respondendo">
                  <span className="chatbot-message-avatar"><ChatbotRobot compact mood="thinking" incognito={modoTemporario} /></span>
                  <div className="chatbot-loading-bubble"><span className="chatbot-loading-dots" aria-hidden="true"><i /><i /><i /></span><span key={progresso} className="chatbot-loading-status">{progresso || 'Entendendo sua pergunta…'}</span></div>
                </article>
              )}
            </div>
          )}

          {erro && (
            <div className="chatbot-error-wrap">
              <p className="chatbot-error" role="alert">{erro}</p>
              {perguntaFalhou && (
                <button className="chatbot-retry" type="button" onClick={() => void enviar(perguntaFalhou, false)}>
                  Tentar novamente
                </button>
              )}
            </div>
          )}

          <form className="chatbot-composer" onSubmit={enviarFormulario}>
            <textarea
              ref={entrada}
              aria-label="Escreva sua mensagem"
              placeholder="Pergunte sobre cinema…"
              value={texto}
              onChange={(event) => setTexto(event.target.value)}
              onFocus={() => setFocado(true)}
              onBlur={() => setFocado(false)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
                  event.preventDefault()
                  void enviar()
                }
              }}
              rows={2}
              maxLength={1000}
              disabled={carregando}
            />
            <button type="submit" aria-label="Enviar mensagem" disabled={carregando || !texto.trim()}>
              <SendIcon />
            </button>
          </form>

          <p className="chatbot-privacy-note">{modoTemporario ? 'Conversa temporária · as mensagens não serão salvas.' : 'Conversa salva na sua conta · você pode retomá-la quando quiser.'}</p>
          </div>
        </section>
      </div>
    </main>
  )
}

function ResultadoGenAi({ resposta }: { resposta: RespostaGenAi }) {
  const { metadata, rows } = resposta
  const columns = colunasVisiveis(metadata.columns)
  const titulo = tituloResultado(metadata)
  const observacao = observacaoResultado(metadata)
  const mostrarTexto = metadata.source === 'platform' || metadata.source === 'mixed'
  const possuiGrafico = temGraficoDeResultado(metadata, rows)
  return (
    <div className="chatbot-result" aria-label="Resposta do chatbot">
      {metadata.cached && <p className="chatbot-cache-note">Resposta recuperada do cache desta conversa</p>}
      {mostrarTexto && <p className="chatbot-result-answer">{resposta.answer}</p>}
      {rows.length > 0 && (
        <div className="chatbot-result-heading">
          <h3>{tituloResultado(metadata)}</h3>
          <div><span>{rows.length} {rows.length === 1 ? 'resultado' : 'resultados'}</span><button className="chatbot-export-csv" type="button" onClick={() => baixarResultadoCsv({ titulo, metadata, columns, rows })}><svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="M10 2.5v9m0 0 3.5-3.5M10 11.5 6.5 8M3.5 13v2.5c0 .55.45 1 1 1h11c.55 0 1-.45 1-1V13" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" /></svg>Baixar CSV</button></div>
        </div>
      )}
      <ChatbotResultChart metadata={metadata} rows={rows} />
      {possuiGrafico && resposta.insights.length > 0 && (
        <section className="chatbot-insights" aria-label="Insights sobre os dados">
          <span>Insights</span>
          <ul>{resposta.insights.map((insight) => <li key={insight}>{insight}</li>)}</ul>
        </section>
      )}
      {rows.length > 0 && columns.length > 0 && (
        <details className={`chatbot-result-data ${possuiGrafico ? '' : 'is-open'}`} open={!possuiGrafico}>
          {possuiGrafico && <summary>Ver dados em tabela <span>{rows.length} {rows.length === 1 ? 'resultado' : 'resultados'}</span></summary>}
          <div className="chatbot-result-table-wrap">
            <table className="chatbot-result-table">
              <thead><tr>{columns.map((column) => <th key={column} scope="col">{rotuloColuna(column, metadata)}</th>)}</tr></thead>
              <tbody>
                {rows.map((row, index) => (
                  <tr key={index}>
                    {columns.map((column) => <td key={column}>{formatarCelula(column, row[column])}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
      {rows.length > 0 && columns.length === 0 && <p className="chatbot-result-note">Não há detalhes para mostrar nesta resposta.</p>}
      {rows.length === 0 && !mostrarTexto && <p className="chatbot-result-note">Não encontrei resultados. Tente perguntar de outro jeito.</p>}
      {metadata.truncated && <p className="chatbot-result-note">Exibindo os primeiros {rows.length} resultados.</p>}
      {observacao && <p className="chatbot-result-note">{observacao}</p>}
    </div>
  )
}
