import { useEffect, useState, type FormEvent } from 'react'
import { AlertCircle, BadgeCheck, FileUp, RotateCcw, Send } from 'lucide-react'
import { api, ApiError, type DocumentoEmitido, type ResultadoLote, type Usuario } from '../api/client'

const TIPOS = ['diploma', 'certidao', 'comprovante'] as const
const MAX_BATCH_BYTES = 10 * 1024 * 1024

export default function InstitutionPortalPage() {
  const [titulares, setTitulares] = useState<Usuario[]>([])
  const [userId, setUserId] = useState('')
  const [titulo, setTitulo] = useState('')
  const [tipo, setTipo] = useState<(typeof TIPOS)[number]>('diploma')
  const [conteudo, setConteudo] = useState('{\n  \n}')
  const [documentoEmitido, setDocumentoEmitido] = useState<DocumentoEmitido | null>(null)
  const [lote, setLote] = useState<ResultadoLote | null>(null)
  const [relatorio, setRelatorio] = useState<Awaited<ReturnType<typeof api.relatorioLote>> | null>(null)
  const [codigoRevogacao, setCodigoRevogacao] = useState('')
  const [motivo, setMotivo] = useState('')
  const [erro, setErro] = useState('')
  const [status, setStatus] = useState('')
  const [enviando, setEnviando] = useState(false)

  useEffect(() => {
    void api.buscarUsuarios('CIDADAO')
      .then(setTitulares)
      .catch(() => {})
  }, [])

  async function emitir(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setErro('')
    setStatus('')
    setDocumentoEmitido(null)
    let data: Record<string, unknown>
    try {
      const parsed: unknown = JSON.parse(conteudo)
      if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) throw new Error()
      data = parsed as Record<string, unknown>
    } catch {
      setErro('O conteúdo precisa ser um objeto JSON válido.')
      return
    }
    setEnviando(true)
    try {
      const result = await api.emitirDocumento({ usuario_id: Number(userId), titulo: titulo.trim(), tipo_documento: tipo, conteudo: data })
      setDocumentoEmitido(result)
      setStatus('Documento emitido e pronto para verificação.')
      setTitulo('')
    } catch (error) {
      setErro(error instanceof ApiError ? error.message : 'Não foi possível emitir o documento.')
    } finally {
      setEnviando(false)
    }
  }

  async function enviarLote(event: FormEvent<HTMLInputElement>) {
    const file = event.currentTarget.files?.[0]
    event.currentTarget.value = ''
    if (!file) return
    setErro('')
    setStatus('')
    setLote(null)
    setRelatorio(null)
    if (!/\.(csv|json)$/i.test(file.name)) {
      setErro('Escolha um arquivo .csv ou .json.')
      return
    }
    if (file.size > MAX_BATCH_BYTES) {
      setErro('O arquivo deve ter no máximo 10 MB.')
      return
    }
    setEnviando(true)
    try {
      const result = await api.enviarLote(file)
      setLote(result)
      setStatus('Arquivo validado. As linhas válidas foram enviadas para processamento.')
      setRelatorio(await api.relatorioLote(result.lote_id))
    } catch (error) {
      setErro(error instanceof ApiError ? error.message : 'Não foi possível processar o lote.')
    } finally {
      setEnviando(false)
    }
  }

  async function atualizarRelatorio() {
    if (!lote) return
    setErro('')
    try {
      setRelatorio(await api.relatorioLote(lote.lote_id))
    } catch (error) {
      setErro(error instanceof ApiError ? error.message : 'Não foi possível consultar o lote.')
    }
  }

  async function revogar(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setErro('')
    setStatus('')
    setEnviando(true)
    try {
      const document = await api.revogarDocumento(codigoRevogacao.trim(), motivo.trim())
      setStatus(`Documento ${document.codigo} revogado.`)
      setCodigoRevogacao('')
      setMotivo('')
    } catch (error) {
      setErro(error instanceof ApiError ? error.message : 'Não foi possível revogar o documento.')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <section className="workspace-page" aria-labelledby="issuance-title">
      <header className="page-heading workspace-heading">
        <div><p className="eyebrow">INSTITUIÇÃO / EMISSÃO</p><h1 id="issuance-title">Portal de emissão</h1><p className="heading-copy">Emita certificados, processe lotes e gerencie documentos.</p></div>
      </header>
      {erro ? <div className="form-alert page-alert" role="alert"><AlertCircle size={17} />{erro}</div> : null}
      {status ? <div className="success-banner" role="status"><BadgeCheck size={17} />{status}</div> : null}

      <div className="institution-grid">
        <section className="content-panel" aria-labelledby="single-issue-title">
          <div className="panel-heading"><div className="panel-icon"><Send size={17} aria-hidden="true" /></div><div><h2 id="single-issue-title">Emissão individual</h2><p>Emita um documento com código e QR de verificação.</p></div></div>
          <form className="form-stack compact-form" onSubmit={emitir}>
            <label className="field-label" htmlFor="issue-user">Titular do documento</label>
            {titulares.length > 0 ? (
              <select
                className="text-input"
                id="issue-user"
                required
                value={userId}
                onChange={(event) => setUserId(event.target.value)}
              >
                <option value="">Selecione o titular cadastrado</option>
                {titulares.map((titular) => (
                  <option key={titular.id} value={titular.id}>
                    {titular.nome} ({titular.email})
                  </option>
                ))}
              </select>
            ) : (
              <input
                className="text-input"
                id="issue-user"
                type="number"
                min="1"
                step="1"
                placeholder="ID do titular"
                required
                value={userId}
                onChange={(event) => setUserId(event.target.value)}
              />
            )}
            <label className="field-label" htmlFor="issue-title">Título do documento</label>
            <input className="text-input" id="issue-title" maxLength={255} required value={titulo} onChange={(event) => setTitulo(event.target.value)} />
            <label className="field-label" htmlFor="issue-type">Tipo</label>
            <select className="text-input" id="issue-type" value={tipo} onChange={(event) => setTipo(event.target.value as (typeof TIPOS)[number])}>
              <option value="diploma">Diploma</option><option value="certidao">Certidão</option><option value="comprovante">Comprovante</option>
            </select>
            <label className="field-label" htmlFor="issue-content">Conteúdo estruturado (JSON)</label>
            <textarea className="text-input code-input" id="issue-content" rows={5} spellCheck={false} required value={conteudo} onChange={(event) => setConteudo(event.target.value)} />
            <button className="primary-button" type="submit" disabled={enviando}><Send size={16} aria-hidden="true" />{enviando ? 'Emitindo...' : 'Emitir documento'}</button>
          </form>
          {documentoEmitido ? <div className="issued-result" role="status"><strong>{documentoEmitido.titulo}</strong><span>Código: <code>{documentoEmitido.codigo}</code></span><a href={documentoEmitido.verification_url} target="_blank" rel="noreferrer">Abrir verificação pública</a></div> : null}
        </section>

        <section className="content-panel" aria-labelledby="batch-title">
          <div className="panel-heading"><div className="panel-icon panel-icon-gold"><FileUp size={18} aria-hidden="true" /></div><div><h2 id="batch-title">Emissão em lote</h2><p>Envie um arquivo CSV ou JSON (máximo 10 MB).</p></div></div>
          <label className={`batch-dropzone${enviando ? ' disabled' : ''}`}>
            <FileUp size={24} aria-hidden="true" />
            <strong>{enviando ? 'Enviando arquivo...' : 'Selecionar CSV ou JSON'}</strong>
            <span>As linhas válidas serão processadas em segundo plano.</span>
            <input type="file" accept=".csv,.json,text/csv,application/json" disabled={enviando} aria-label="Selecionar arquivo CSV ou JSON para emissão em lote" onChange={enviarLote} />
          </label>
          {lote ? <div className="batch-summary"><div><span>Lote</span><strong><code>{lote.lote_id}</code></strong></div><div><span>Registros</span><strong>{lote.total_linhas}</strong></div><div><span>Válidos</span><strong>{lote.validas}</strong></div><div><span>Erros</span><strong className={lote.erros.length ? 'text-danger' : ''}>{lote.erros.length}</strong></div><button className="icon-button" type="button" onClick={() => void atualizarRelatorio()} aria-label="Atualizar relatório do lote" title="Atualizar relatório"><RotateCcw size={16} /></button></div> : null}
          {relatorio ? <div className="batch-report" aria-live="polite"><div className="report-heading"><strong>Relatório: {relatorio.estado.replaceAll('_', ' ')}</strong><span>{relatorio.documentos.length} emitidos</span></div>{relatorio.erros_validacao.length || relatorio.erros_processamento.length ? <ul className="line-errors">{[...relatorio.erros_validacao, ...relatorio.erros_processamento].map((item, index) => <li key={`${item.linha}-${index}`}><strong>Linha {item.linha}:</strong> {item.erros.join('; ')}</li>)}</ul> : <p className="muted-copy">Nenhum erro de validação ou processamento.</p>}</div> : null}
        </section>
      </div>

      <section className="content-panel revoke-panel" aria-labelledby="revoke-title">
        <div className="panel-heading"><div className="panel-icon panel-icon-danger"><RotateCcw size={17} aria-hidden="true" /></div><div><h2 id="revoke-title">Revogar documento</h2><p>Informe o código de verificação do documento emitido por esta instituição.</p></div></div>
        <form className="revoke-form" onSubmit={revogar}>
          <div><label className="field-label" htmlFor="revoke-code">Código</label><input className="text-input" id="revoke-code" required value={codigoRevogacao} onChange={(event) => setCodigoRevogacao(event.target.value)} /></div>
          <div><label className="field-label" htmlFor="revoke-reason">Motivo (opcional)</label><input className="text-input" id="revoke-reason" maxLength={1000} value={motivo} onChange={(event) => setMotivo(event.target.value)} /></div>
          <button className="danger-button" type="submit" disabled={enviando}>Revogar emissão</button>
        </form>
      </section>
    </section>
  )
}