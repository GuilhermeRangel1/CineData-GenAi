import { useEffect, useRef, useState, type FormEvent } from 'react'
import { conversarComAssistente } from '../api/client'
import type { MensagemChatbot, UsuarioLeitura } from '../types/api'
import './ChatbotHub.css'

const SUGESTOES = [
  'Me recomenda um filme',
  'Quero algo parecido com Interestelar',
  'Me ajuda com o CineData',
]

function BaymaxHead({ className = '' }: { className?: string }) {
  const gradientId = className.includes('hero') ? 'baymax-head-hero' : 'baymax-head-chat'
  return (
    <svg className={`chatbot-baymax-head ${className}`} viewBox="0 0 120 100" role="img" aria-label="Cabeça estilizada do assistente">
      <defs>
        <linearGradient id={gradientId} x1=".15" y1=".05" x2=".85" y2=".95">
          <stop offset="0" stopColor="#fff" />
          <stop offset=".48" stopColor="#f5faf9" />
          <stop offset="1" stopColor="#b9d1d4" />
        </linearGradient>
      </defs>
      <g transform="rotate(-11 60 50) skewX(-3)">
        <path d="M15 48C15 22 33 9 61 9c28 0 45 15 45 40 0 25-18 42-47 42C31 91 15 75 15 48Z" fill={`url(#${gradientId})`} stroke="#d8e8e8" strokeWidth="1.5" />
        <path d="M23 43c2-17 16-27 35-29" fill="none" stroke="#fff" strokeOpacity=".9" strokeWidth="4" strokeLinecap="round" />
        <path d="M39 48c13 5 30 6 44 0" fill="none" stroke="#343e43" strokeWidth="2.1" strokeLinecap="round" />
        <circle cx="39" cy="47.5" r="4.4" fill="#1f272b" />
        <circle cx="84" cy="47.5" r="4.4" fill="#1f272b" />
        <ellipse cx="28" cy="67" rx="7" ry="3" fill="#c8e9e7" opacity=".38" />
        <ellipse cx="94" cy="67" rx="6" ry="2.5" fill="#a8d5d4" opacity=".3" />
      </g>
    </svg>
  )
}

function SendIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 12 20 4l-5 16-3-7-8-1Zm8 1 8-9" />
    </svg>
  )
}

export function ChatbotHub({ usuario, onLoginRequested }: {
  usuario: UsuarioLeitura | null
  onLoginRequested: () => void
}) {
  const [mensagens, setMensagens] = useState<MensagemChatbot[]>([])
  const [texto, setTexto] = useState('')
  const [erro, setErro] = useState('')
  const [carregando, setCarregando] = useState(false)
  const fimDaConversa = useRef<HTMLDivElement>(null)

  useEffect(() => {
    fimDaConversa.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [mensagens, carregando])

  async function enviar(mensagem = texto) {
    const conteudo = mensagem.trim()
    if (!conteudo || carregando) return
    if (!usuario) {
      onLoginRequested()
      return
    }

    const mensagemUsuario: MensagemChatbot = { role: 'user', conteudo }
    const historicoExibido = [...mensagens, mensagemUsuario]
    const historicoDaRequisicao = historicoExibido.slice(-16)
    while (historicoDaRequisicao[0]?.role === 'assistant') historicoDaRequisicao.shift()
    setMensagens(historicoExibido)
    setTexto('')
    setErro('')
    setCarregando(true)

    try {
      const resposta = await conversarComAssistente(historicoDaRequisicao)
      setMensagens((atuais) => [...atuais, { role: 'assistant', conteudo: resposta.mensagem }])
    } catch (falha) {
      setErro(falha instanceof Error ? falha.message : 'Não consegui responder agora. Tente novamente.')
    } finally {
      setCarregando(false)
    }
  }

  function enviarFormulario(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    void enviar()
  }

  return (
    <main className="chatbot-page" id="assistente">
      <header className="chatbot-header">
        <div className="chatbot-header-copy">
            <p><span /> TODA BOA CONVERSA MERECE UM FILME</p>
            <h1>CHATBOT</h1>
        </div>
        <div className="chatbot-header-orbit" aria-hidden="true" />
        <BaymaxHead className="chatbot-baymax-head--hero" />
      </header>

      <div className="chatbot-content">
        <section className={`chatbot-chat-area ${mensagens.length ? 'has-messages' : ''}`} aria-label="Conversa com o assistente">
          {mensagens.length === 0 ? (
            <div className="chatbot-welcome">
              <span className="chatbot-online"><i /> ASSISTENTE DE CINEMA · GEMINI 3.8 FLASH</span>
              <h2>Oi! O que vamos assistir?</h2>
              <p>Peça uma recomendação ou converse sobre qualquer filme.</p>
            </div>
          ) : (
            <div className="chatbot-messages" aria-live="polite" aria-relevant="additions text">
              {mensagens.map((mensagem, indice) => (
                <article key={`${indice}-${mensagem.role}`} className={`chatbot-message chatbot-message--${mensagem.role}`}>
                  {mensagem.role === 'assistant' && <BaymaxHead className="chatbot-baymax-head--message" />}
                  <p>{mensagem.conteudo}</p>
                </article>
              ))}
              {carregando && (
                <article className="chatbot-message chatbot-message--assistant chatbot-message--loading" aria-label="Assistente está respondendo">
                  <BaymaxHead className="chatbot-baymax-head--message" />
                  <span><i /><i /><i /></span>
                </article>
              )}
              <div ref={fimDaConversa} />
            </div>
          )}

          {!usuario && (
            <div className="chatbot-login-prompt">
              <span>Entre na sua conta para conversar com o assistente.</span>
              <button type="button" onClick={onLoginRequested}>Entrar</button>
            </div>
          )}

          {erro && <p className="chatbot-error" role="alert">{erro}</p>}

          <form className="chatbot-composer" onSubmit={enviarFormulario}>
            <input
              aria-label="Escreva sua mensagem"
              placeholder={usuario ? 'Escreva sua mensagem...' : 'Entre para enviar uma mensagem'}
              value={texto}
              onChange={(event) => setTexto(event.target.value)}
              maxLength={2000}
              disabled={!usuario || carregando}
            />
            <button type="submit" aria-label="Enviar mensagem" disabled={!usuario || carregando || !texto.trim()}>
              <SendIcon />
            </button>
          </form>

          {mensagens.length === 0 && usuario && (
            <div className="chatbot-suggestions" aria-label="Sugestões para começar">
              {SUGESTOES.map((sugestao) => (
                <button key={sugestao} type="button" onClick={() => void enviar(sugestao)} disabled={carregando}>
                  {sugestao}
                </button>
              ))}
            </div>
          )}
          <p className="chatbot-privacy-note">As mensagens são enviadas ao Gemini e não ficam salvas no CineData.</p>
        </section>
      </div>
    </main>
  )
}
