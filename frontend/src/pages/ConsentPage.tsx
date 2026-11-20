import { useEffect, useState, type FormEvent } from 'react'
import { Clock3, ShieldCheck, ShieldOff } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { api, ApiError, type Consentimento, type DocumentoCarteira, type Usuario } from '../api/client'

function horarioLocalFuturo() {
  const date = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000)
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset())
  return date.toISOString().slice(0, 16)
}

export default function ConsentPage() {
  const [params, setParams] = useSearchParams()
  const [documentos, setDocumentos] = useState<DocumentoCarteira[]>([])
  const [acessos, setAcessos] = useState<Consentimento[]>([])
  const [empresas, setEmpresas] = useState<Usuario[]>([])
  const [documentoId, setDocumentoId] = useState(params.get('documento') ?? '')
  const [empresaId, setEmpresaId] = useState('')
  const [expiraEm, setExpiraEm] = useState(horarioLocalFuturo)
  const [erro, setErro] = useState('')
  const [mensagem, setMensagem] = useState('')
  const [carregando, setCarregando] = useState(true)
  const [enviando, setEnviando] = useState(false)

  async function carregar() {
    setCarregando(true)
    setErro('')
    try {
      const [docs, grants, emps] = await Promise.all([
        api.listarDocumentos(),
        api.listarConsentimentos(),
        api.buscarUsuarios('EMPRESA').catch(() => []),
      ])
      setDocumentos(docs)
      setAcessos(grants)
      setEmpresas(emps)
    } catch (error) {
      setErro(error instanceof ApiError ? error.message : 'Não foi possível carregar os acessos.')
    } finally {
      setCarregando(false)
    }
  }

  useEffect(() => { void carregar() }, [])

  function selecionarDocumento(value: string) {
    setDocumentoId(value)
    if (value) setParams({ documento: value }, { replace: true })
    else setParams({}, { replace: true })
  }

  async function conceder(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setErro('')
    setMensagem('')
    setEnviando(true)
    try {
      await api.concederConsentimento({
        documento_id: Number(documentoId),
        empresa_id: Number(empresaId),
        expira_em: new Date(expiraEm).toISOString(),
      })
      setMensagem('Acesso concedido. A empresa poderá consultar o documento até a data definida.')
      setEmpresaId('')
      await carregar()
    } catch (error) {
      setErro(error instanceof ApiError ? error.message : 'Não foi possível conceder o acesso.')
    } finally {
      setEnviando(false)
    }
  }

  async function revogar(id: number) {
    setErro('')
    try {
      await api.revogarConsentimento(id)
      setAcessos((current) => current.filter((grant) => grant.id !== id))
      setMensagem('O acesso foi revogado.')
    } catch (error) {
      setErro(error instanceof ApiError ? error.message : 'Não foi possível revogar o acesso.')
    }
  }

  return (
    <section className="workspace-page" aria-labelledby="consent-title">
      <header className="page-heading workspace-heading">
        <div>
          <p className="eyebrow">CIDADÃO / PRIVACIDADE</p>
          <h1 id="consent-title">Acessos concedidos</h1>
          <p className="heading-copy">Escolha qual empresa pode acessar cada documento e quando o acesso termina.</p>
        </div>
      </header>

      <div className="consent-layout">
        <section className="content-panel" aria-labelledby="grant-title">
          <div className="panel-heading">
            <div className="panel-icon"><ShieldCheck size={18} aria-hidden="true" /></div>
            <div><h2 id="grant-title">Conceder acesso</h2><p>O acesso expira automaticamente na data escolhida.</p></div>
          </div>
          <form className="form-stack compact-form" onSubmit={conceder}>
            <label className="field-label" htmlFor="consent-document">Documento</label>
            <select id="consent-document" className="text-input" required value={documentoId} onChange={(event) => selecionarDocumento(event.target.value)}>
              <option value="">Selecione um documento</option>
              {documentos.map((doc) => <option key={doc.id} value={doc.id}>{doc.nome_arquivo}</option>)}
            </select>
            <label className="field-label" htmlFor="consent-company">Empresa autorizada</label>
            {empresas.length > 0 ? (
              <select
                id="consent-company"
                className="text-input"
                required
                value={empresaId}
                onChange={(event) => setEmpresaId(event.target.value)}
              >
                <option value="">Selecione uma empresa</option>
                {empresas.map((emp) => (
                  <option key={emp.id} value={emp.id}>
                    {emp.nome} ({emp.email})
                  </option>
                ))}
              </select>
            ) : (
              <input
                id="consent-company"
                className="text-input"
                type="number"
                min="1"
                step="1"
                placeholder="ID da empresa"
                required
                value={empresaId}
                onChange={(event) => setEmpresaId(event.target.value)}
              />
            )}
            <label className="field-label" htmlFor="consent-expiry">Acesso válido até</label>
            <input id="consent-expiry" className="text-input" type="datetime-local" required value={expiraEm} onChange={(event) => setExpiraEm(event.target.value)} />
            {erro ? <p className="form-alert" role="alert">{erro}</p> : null}
            {mensagem ? <p className="success-inline" role="status">{mensagem}</p> : null}
            <button className="primary-button" type="submit" disabled={enviando || carregando}>
              <ShieldCheck size={16} aria-hidden="true" /> {enviando ? 'Salvando...' : 'Conceder acesso'}
            </button>
          </form>
        </section>

        <section className="content-panel access-panel" aria-labelledby="active-access-title">
          <div className="panel-heading">
            <div className="panel-icon panel-icon-gold"><Clock3 size={18} aria-hidden="true" /></div>
            <div><h2 id="active-access-title">Quem pode acessar</h2><p>Concessões ativas nos seus documentos.</p></div>
          </div>
          {carregando ? <p className="muted-copy">Carregando acessos...</p> : acessos.length ? (
            <ul className="access-list">
              {acessos.map((grant) => {
                const doc = documentos.find((item) => item.id === grant.documento_id)
                const emp = empresas.find((item) => item.id === grant.empresa_id)
                const nomeEmpresa = emp ? emp.nome : `Empresa #${grant.empresa_id}`
                return (
                  <li className="access-row" key={grant.id}>
                    <div className="access-company"><span className="company-avatar" aria-hidden="true">{nomeEmpresa.slice(0, 2).toUpperCase()}</span><div><strong>{nomeEmpresa}</strong><small>{doc?.nome_arquivo ?? `Documento #${grant.documento_id}`}</small></div></div>
                    <div className="access-expiry"><span>Expira</span><strong>{new Intl.DateTimeFormat('pt-BR', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(grant.expira_em))}</strong></div>
                    <button className="danger-icon-button" type="button" aria-label={`Revogar acesso de ${nomeEmpresa}`} title="Revogar acesso" onClick={() => void revogar(grant.id)}><ShieldOff size={17} aria-hidden="true" /></button>
                  </li>
                )
              })}
            </ul>
          ) : (
            <div className="empty-inline"><ShieldOff size={20} aria-hidden="true" /><span>Nenhuma empresa tem acesso ativo aos seus documentos.</span></div>
          )}
        </section>
      </div>
    </section>
  )
}