import { useState, useRef, useEffect, type FormEvent } from 'react'
import { Bot, MessageSquare, Send, Sparkles, X } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { api, type MensagemChat } from '../api/client'
import { useAuth } from '../auth/AuthProvider'

const SUGESTOES = [
  'Como funciona o consentimento LGPD?',
  'Como emitir documento com QR Code?',
  'Como verificar a autenticidade?',
  'Como enviar documentos para OCR?',
]

export default function ChatbotWidget() {
  const { usuario } = useAuth()
  const [aberto, setAberto] = useState(false)
  const [mensagens, setMensagens] = useState<MensagemChat[]>([
    {
      role: 'assistant',
      content: `Olá${usuario ? `, ${usuario.nome}` : ''}! Sou o assistente inteligente do **Organiza AI** (usando Anthropic Claude Haiku 5.5). Posso esclarecer dúvidas sobre carteira, consentimentos, emissão ou verificação.`,
    },
  ])
  const [entrada, setEntrada] = useState('')
  const [carregando, setCarregando] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (aberto) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [mensagens, aberto])

  async function enviar(textoParaEnviar?: string) {
    const texto = (textoParaEnviar ?? entrada).trim()
    if (!texto || carregando) return

    const novasMensagens: MensagemChat[] = [...mensagens, { role: 'user', content: texto }]
    setMensagens(novasMensagens)
    setEntrada('')
    setCarregando(true)

    try {
      const historicoEnvio = novasMensagens.slice(-6)
      const res = await api.enviarMensagemChat(texto, historicoEnvio)
      setMensagens((prev) => [...prev, { role: 'assistant', content: res.resposta }])
    } catch {
      setMensagens((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: 'Desculpe, ocorreu um erro ao consultar o assistente. Verifique a conexão com o servidor.',
        },
      ])
    } finally {
      setCarregando(false)
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    void enviar()
  }

  return (
    <div className="chatbot-wrapper">
      {!aberto ? (
        <button
          className="chatbot-toggle-button"
          type="button"
          onClick={() => setAberto(true)}
          aria-label="Abrir assistente virtual"
        >
          <Bot size={20} aria-hidden="true" />
          <span className="chatbot-toggle-label">Assistente AI</span>
          <span className="chatbot-toggle-badge">Haiku</span>
        </button>
      ) : (
        <section className="chatbot-window" aria-label="Janela do assistente inteligente">
          <header className="chatbot-header">
            <div className="chatbot-header-info">
              <div className="chatbot-header-avatar">
                <Sparkles size={16} aria-hidden="true" />
              </div>
              <div>
                <strong>Assistente Organiza AI</strong>
                <small>Anthropic Claude Haiku 5.5</small>
              </div>
            </div>
            <button
              className="chatbot-close-button"
              type="button"
              onClick={() => setAberto(false)}
              aria-label="Fechar assistente"
            >
              <X size={18} />
            </button>
          </header>

          <div className="chatbot-messages">
            {mensagens.map((msg, idx) => (
              <div
                key={idx}
                className={`chatbot-bubble ${msg.role === 'user' ? 'chatbot-bubble-user' : 'chatbot-bubble-bot'}`}
              >
                {msg.role === 'assistant' ? (
                  <div className="chatbot-bot-meta">
                    <Bot size={13} aria-hidden="true" />
                    <span>Claude Haiku</span>
                  </div>
                ) : null}
                <div className="chatbot-bubble-text">
                  {msg.role === 'assistant' ? <ReactMarkdown>{msg.content}</ReactMarkdown> : msg.content}
                </div>
              </div>
            ))}
            {carregando ? (
              <div className="chatbot-bubble chatbot-bubble-bot chatbot-loading">
                <span className="dot-flashing" />
                <span className="dot-flashing" />
                <span className="dot-flashing" />
              </div>
            ) : null}
            <div ref={messagesEndRef} />
          </div>

          {mensagens.length <= 2 ? (
            <div className="chatbot-suggestions" aria-label="Sugestões de perguntas">
              {SUGESTOES.map((sugestao, i) => (
                <button
                  key={i}
                  className="chatbot-suggestion-pill"
                  type="button"
                  onClick={() => void enviar(sugestao)}
                  disabled={carregando}
                >
                  <MessageSquare size={12} aria-hidden="true" />
                  <span>{sugestao}</span>
                </button>
              ))}
            </div>
          ) : null}

          <form className="chatbot-input-row" onSubmit={submit}>
            <input
              className="chatbot-input"
              type="text"
              placeholder="Digite sua dúvida sobre o sistema..."
              value={entrada}
              onChange={(e) => setEntrada(e.target.value)}
              disabled={carregando}
              aria-label="Mensagem para o assistente"
            />
            <button
              className="chatbot-send-button"
              type="submit"
              disabled={!entrada.trim() || carregando}
              aria-label="Enviar mensagem"
            >
              <Send size={15} aria-hidden="true" />
            </button>
          </form>
        </section>
      )}
    </div>
  )
}
