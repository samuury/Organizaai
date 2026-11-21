import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { ArrowDownToLine, Check, FilePlus2, FileText, Pencil, Search, ShieldCheck, Trash2, X } from 'lucide-react'
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

  const [documentoEditando, setDocumentoEditando] = useState<DocumentoCarteira | null>(null)
  const [formEdicao, setFormEdicao] = useState({
    nome_arquivo: '',
    tipo_documento: '',
    nome_extraido: '',
    emissor_extraido: '',
    data_extraida: '',
  })
  const [salvandoEdicao, setSalvandoEdicao] = useState(false)

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

  function iniciarEdicao(doc: DocumentoCarteira) {
    setDocumentoEditando(doc)
    setFormEdicao({
      nome_arquivo: doc.nome_arquivo,
      tipo_documento: doc.tipo_documento ?? '',
      nome_extraido: doc.nome_extraido ?? '',
      emissor_extraido: doc.emissor_extraido ?? '',
      data_extraida: doc.data_extraida ? doc.data_extraida.slice(0, 10) : '',
    })
  }

  async function salvarEdicao(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!documentoEditando) return
    setSalvandoEdicao(true)
    setErro('')
    try {
      const atualizado = await api.atualizarDocumento(documentoEditando.id, {
        nome_arquivo: formEdicao.nome_arquivo.trim() || undefined,
        tipo_documento: (formEdicao.tipo_documento as 'diploma' | 'certidao' | 'comprovante') || null,
        nome_extraido: formEdicao.nome_extraido.trim() || null,
        emissor_extraido: formEdicao.emissor_extraido.trim() || null,
        data_extraida: formEdicao.data_extraida || null,
      })
      setDocumentos((prev) => prev.map((d) => (d.id === atualizado.id ? atualizado : d)))
      setMensagem('Documento atualizado com sucesso.')
      setDocumentoEditando(null)
    } catch (error) {
      setErro(error instanceof ApiError ? error.message : 'Falha ao atualizar o documento.')
    } finally {
      setSalvandoEdicao(false)
    }
  }

  async function excluir(documento: DocumentoCarteira) {
    const confirmou = window.confirm(
      `Deseja realmente excluir o documento "${documento.nome_arquivo}"? Esta ação removerá o arquivo definitivamente.`,
    )
    if (!confirmou) return
    setErro('')
    try {
      await api.excluirDocumento(documento.id)
      setDocumentos((prev) => prev.filter((d) => d.id !== documento.id))
      setMensagem(`Documento "${documento.nome_arquivo}" excluído com sucesso.`)
    } catch (error) {
      setErro(error instanceof ApiError ? error.message : 'Falha ao excluir o documento.')
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
                <button
                  className="icon-button"
                  type="button"
                  title="Editar informações"
                  aria-label={`Editar ${documento.nome_arquivo}`}
                  onClick={() => iniciarEdicao(documento)}
                >
                  <Pencil size={15} aria-hidden="true" />
                </button>
                <button
                  className="icon-button"
                  type="button"
                  title="Baixar documento"
                  aria-label={`Baixar ${documento.nome_arquivo}`}
                  onClick={() => void baixar(documento)}
                >
                  <ArrowDownToLine size={16} aria-hidden="true" />
                </button>
                <Link
                  className="outline-button small-button"
                  to={`/cidadao/consentimentos?documento=${documento.id}`}
                  title="Gerenciar acessos de empresas"
                >
                  <ShieldCheck size={14} aria-hidden="true" /> Acessos
                </Link>
                <button
                  className="danger-icon-button"
                  type="button"
                  title="Excluir documento"
                  aria-label={`Excluir ${documento.nome_arquivo}`}
                  onClick={() => void excluir(documento)}
                >
                  <Trash2 size={15} aria-hidden="true" />
                </button>
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
      {documentoEditando ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="modal-edit-title">
          <div className="modal-content">
            <header className="modal-header">
              <div>
                <h2 id="modal-edit-title">Editar dados do documento</h2>
                <small>{documentoEditando.nome_arquivo}</small>
              </div>
              <button
                type="button"
                className="icon-button"
                onClick={() => setDocumentoEditando(null)}
                aria-label="Fechar"
              >
                <X size={16} />
              </button>
            </header>
            <form onSubmit={salvarEdicao} className="form-stack">
              <label className="field-label" htmlFor="edit-nome-arquivo">Nome do arquivo</label>
              <input
                id="edit-nome-arquivo"
                type="text"
                className="text-input"
                required
                value={formEdicao.nome_arquivo}
                onChange={(e) => setFormEdicao({ ...formEdicao, nome_arquivo: e.target.value })}
                placeholder="Ex: Declaracao_Matricula.pdf"
              />

              <label className="field-label" htmlFor="edit-tipo">Tipo de documento</label>
              <select
                id="edit-tipo"
                className="text-input"
                value={formEdicao.tipo_documento}
                onChange={(e) => setFormEdicao({ ...formEdicao, tipo_documento: e.target.value })}
              >
                <option value="">Não identificado</option>
                <option value="diploma">Diploma</option>
                <option value="certidao">Certidão</option>
                <option value="comprovante">Comprovante</option>
              </select>

              <label className="field-label" htmlFor="edit-nome">Nome do titular</label>
              <input
                id="edit-nome"
                type="text"
                className="text-input"
                value={formEdicao.nome_extraido}
                onChange={(e) => setFormEdicao({ ...formEdicao, nome_extraido: e.target.value })}
                placeholder="Ex: Nome Completo"
              />

              <label className="field-label" htmlFor="edit-emissor">Instituição emissora</label>
              <input
                id="edit-emissor"
                type="text"
                className="text-input"
                value={formEdicao.emissor_extraido}
                onChange={(e) => setFormEdicao({ ...formEdicao, emissor_extraido: e.target.value })}
                placeholder="Ex: Universidade ou Cartório"
              />

              <label className="field-label" htmlFor="edit-data">Data do documento</label>
              <input
                id="edit-data"
                type="date"
                className="text-input"
                value={formEdicao.data_extraida}
                onChange={(e) => setFormEdicao({ ...formEdicao, data_extraida: e.target.value })}
              />

              <div className="modal-actions">
                <button
                  type="button"
                  className="outline-button"
                  onClick={() => setDocumentoEditando(null)}
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="primary-button"
                  disabled={salvandoEdicao}
                >
                  <Check size={16} /> {salvandoEdicao ? 'Salvando...' : 'Salvar alterações'}
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </section>
  )
}