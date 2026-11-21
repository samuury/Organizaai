import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { ArrowDownToLine, FilePlus2, FileText, Search, ShieldCheck } from 'lucide-react'
import { Link } from 'react-router-dom'
import { api, ApiError, type DocumentoCarteira } from '../api/client'

const MAX_FILE_BYTES = 10 * 1024 * 1024
const ACCEPTED_TYPES = ['application/pdf', 'image/jpeg', 'image/png']

function formatBytes(bytes: number) {
  return new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 }).format(bytes / (1024 * 1024)) + ' MB'
}

function statusLabel(status: DocumentoCarteira['estado_processamento']) {
  return {
    pendente: 'Na fila',
    processando: 'Lendo documento',
    concluido: 'Pronto',
    falhou: 'Leitura falhou',
  }[status]
}

export default function CitizenWalletPage() {
  const [documentos, setDocumentos] = useState<DocumentoCarteira[]>([])
  const [busca, setBusca] = useState('')
  const [erro, setErro] = useState('')
  const [mensagem, setMensagem] = useState('')
  const [carregando, setCarregando] = useState(true)
  const [enviando, setEnviando] = useState(false)
  const [reload, setReload] = useState(0)

  const carregar = useCallback(async (term = '') => {
    setCarregando(true)
    setErro('')
    try {
      setDocumentos(await api.listarDocumentos(term))
    } catch (error) {
      setErro(error instanceof ApiError ? error.message : 'Não foi possível carregar sua carteira.')
    } finally {
      setCarregando(false)
    }
  }, [])

  useEffect(() => { void carregar() }, [carregar, reload])

  async function pesquisar(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    await carregar(busca)
  }

  async function baixar(documento: DocumentoCarteira) {
    setErro('')
    try {
      await api.baixarDocumento(documento.id, documento.nome_arquivo)
    } catch (error) {
      setErro(error instanceof ApiError ? error.message : 'Não foi possível baixar o documento.')
    }
  }

  async function abrir(documento: DocumentoCarteira) {
    setErro('')
    try {
      await api.abrirDocumento(documento.id)
    } catch (error) {
      setErro(error instanceof ApiError ? error.message : 'Não foi possível abrir o documento no navegador.')
    }
  }

  async function upload(event: FormEvent<HTMLInputElement>) {
    const file = event.currentTarget.files?.[0]
    event.currentTarget.value = ''
    if (!file) return
    setErro('')
    setMensagem('')
    if (!ACCEPTED_TYPES.includes(file.type)) {
      setErro('Escolha um arquivo PDF, JPG ou PNG.')
      return
    }
    if (file.size > MAX_FILE_BYTES) {
      setErro('O arquivo deve ter no máximo 10 MB.')
      return
    }
    setEnviando(true)
    try {
      await api.enviarDocumento(file)
      setMensagem('Documento enviado. A leitura automática começará em instantes.')
      setReload((value) => value + 1)
    } catch (error) {
      setErro(error instanceof ApiError ? error.message : 'O envio falhou. Tente novamente.')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <section className="workspace-page" aria-labelledby="wallet-title">
      <header className="page-heading workspace-heading">
        <div>
          <p className="eyebrow">CIDADÃO / CARTEIRA</p>
          <h1 id="wallet-title">Meus documentos</h1>
          <p className="heading-copy">Seus arquivos ficam privados. Você escolhe quando e com quem compartilhar.</p>
        </div>
        <label className={`primary-button upload-button${enviando ? ' disabled' : ''}`}>
          <FilePlus2 size={17} aria-hidden="true" />
          {enviando ? 'Enviando...' : 'Adicionar documento'}
          <input
            type="file"
            accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
            disabled={enviando}
            onChange={upload}
            aria-label="Adicionar documento PDF, JPG ou PNG de até 10 MB"
          />
        </label>
      </header>

      <div className="wallet-toolbar">
        <form className="search-form" role="search" onSubmit={pesquisar}>
          <Search size={17} aria-hidden="true" />
          <label className="sr-only" htmlFor="document-search">Buscar documentos</label>
          <input id="document-search" value={busca} onChange={(event) => setBusca(event.target.value)} placeholder="Buscar por tipo, nome ou ano" />
          <button type="submit">Buscar</button>
        </form>
        <span className="result-count" aria-live="polite">{carregando ? 'Atualizando...' : `${documentos.length} ${documentos.length === 1 ? 'documento' : 'documentos'}`}</span>
      </div>

      {erro ? <div className="form-alert page-alert" role="alert">{erro}</div> : null}
      {mensagem ? <div className="success-banner" role="status">{mensagem}</div> : null}

      {carregando ? (
        <div className="document-list" aria-label="Carregando documentos"><div className="list-skeleton" /><div className="list-skeleton" /></div>
      ) : documentos.length ? (
        <div className="document-list">
          {documentos.map((documento) => (
            <article className="document-row" key={documento.id}>
              <span className="document-type-icon"><FileText size={20} aria-hidden="true" /></span>
              <div className="document-main">
                <h2>
                  <button
                    type="button"
                    className="document-name-button"
                    onClick={() => void abrir(documento)}
                    title="Clique para abrir no leitor do navegador"
                    aria-label={`Abrir ${documento.nome_arquivo} no leitor do navegador`}
                  >
                    {documento.nome_arquivo}
                  </button>
                </h2>
                <p>{documento.tipo_documento ?? 'Tipo não identificado'} <span aria-hidden="true">·</span> {formatBytes(documento.tamanho_bytes)}</p>
                {documento.nome_extraido || documento.emissor_extraido ? (
                  <p className="document-extracted">{documento.nome_extraido ? `Nome: ${documento.nome_extraido}` : ''}{documento.nome_extraido && documento.emissor_extraido ? ' · ' : ''}{documento.emissor_extraido ? `Emissor: ${documento.emissor_extraido}` : ''}</p>
                ) : null}
              </div>
              <span className={`status-tag status-${documento.estado_processamento}`} aria-label={`Estado: ${statusLabel(documento.estado_processamento)}`}>
                <i aria-hidden="true" />{statusLabel(documento.estado_processamento)}
              </span>
              <div className="document-actions">
                <button className="icon-button" type="button" title="Baixar documento" aria-label={`Baixar ${documento.nome_arquivo}`} onClick={() => void baixar(documento)}>
                  <ArrowDownToLine size={17} aria-hidden="true" />
                </button>
                <Link className="outline-button small-button" to={`/cidadao/consentimentos?documento=${documento.id}`}>
                  <ShieldCheck size={15} aria-hidden="true" /> Acessos
                </Link>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="empty-state">
          <div className="empty-icon"><FileText size={23} aria-hidden="true" /></div>
          <h2>{busca ? 'Nenhum resultado encontrado' : 'Sua carteira está vazia'}</h2>
          <p>{busca ? 'Experimente outro termo de busca.' : 'Adicione um documento para começar a organizar sua carteira.'}</p>
        </div>
      )}
    </section>
  )
}