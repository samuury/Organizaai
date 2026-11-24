import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { BadgeCheck, ShieldAlert, ArrowLeft, ShieldCheck } from 'lucide-react'
import { api, type Verificacao } from '../api/client'

const resultadoLabel: Record<Verificacao['status'], string> = {
  VALIDO: 'Documento Autêntico e Válido',
  INVALIDO: 'Código Não Encontrado ou Inválido',
  REVOGADO: 'Documento Revogado pelo Emissor',
}

export default function PublicVerificationPage() {
  const { codigo } = useParams<{ codigo: string }>()
  const [resultado, setResultado] = useState<Verificacao | null>(null)
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState('')

  useEffect(() => {
    if (!codigo) return
    setCarregando(true)
    setErro('')
    api.verificar(codigo)
      .then((res) => setResultado(res))
      .catch(() => setErro('Não foi possível verificar a autenticidade deste documento.'))
      .finally(() => setCarregando(false))
  }, [codigo])

  return (
    <div className="auth-page" style={{ gridTemplateColumns: '1fr', minHeight: '100vh', placeItems: 'center', background: '#f5f7f4' }}>
      <main className="auth-content" style={{ width: 'min(540px, 92%)', padding: '36px 28px', background: '#fff', borderRadius: '8px', border: '1px solid #dce4dc', boxShadow: '0 8px 24px rgba(0,0,0,0.06)' }}>
        <header style={{ textAlign: 'center', marginBottom: '24px' }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', color: '#16654b', fontWeight: 800, fontSize: '18px', marginBottom: '10px' }}>
            <ShieldCheck size={24} /> Organiza AI
          </div>
          <h1 style={{ fontSize: '22px', margin: '0 0 6px', color: '#18241c' }}>Verificação Pública de Autenticidade</h1>
          <p style={{ color: '#687369', fontSize: '12px', margin: 0 }}>Conferência criptográfica de documentos e certificados sob a LGPD</p>
        </header>

        {carregando ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: '#526057' }}>
            <p>Consultando registros imutáveis de auditoria...</p>
          </div>
        ) : erro ? (
          <div className="form-alert page-alert" role="alert" style={{ marginBottom: '20px' }}>
            {erro}
          </div>
        ) : resultado ? (
          <div className={`verification-result result-${resultado.status.toLowerCase()}`} style={{ margin: '0 0 24px' }}>
            <div className="result-icon">
              {resultado.status === 'VALIDO' ? <BadgeCheck size={26} /> : <ShieldAlert size={26} />}
            </div>
            <div>
              <h2 style={{ fontSize: '16px', margin: '0 0 8px', fontWeight: 700 }}>{resultadoLabel[resultado.status]}</h2>
              <dl>
                <div>
                  <dt>Instituição Emissora</dt>
                  <dd><strong>{resultado.emissor ?? 'Não informado'}</strong></dd>
                </div>
                <div>
                  <dt>Data de Emissão</dt>
                  <dd>
                    {resultado.data_emissao
                      ? new Intl.DateTimeFormat('pt-BR', { dateStyle: 'long', timeStyle: 'short' }).format(new Date(resultado.data_emissao))
                      : '—'}
                  </dd>
                </div>
                <div>
                  <dt>Código de Verificação</dt>
                  <dd><code style={{ fontSize: '11px', wordBreak: 'break-all' }}>{codigo}</code></dd>
                </div>
              </dl>
            </div>
          </div>
        ) : null}

        <footer style={{ textAlign: 'center', borderTop: '1px solid #edf0ea', paddingTop: '18px' }}>
          <Link to="/login" style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: '#17684f', fontWeight: 600, textDecoration: 'none' }}>
            <ArrowLeft size={14} /> Ir para a página inicial do Organiza AI
          </Link>
        </footer>
      </main>
    </div>
  )
}
