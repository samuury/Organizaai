export type Perfil = 'CIDADAO' | 'INSTITUICAO' | 'EMPRESA'

export type Usuario = {
  id: number
  nome: string
  email: string
  perfil: Perfil
}

export function normalizarPerfil(value: string): Perfil {
  const normalized = value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toUpperCase()
  if (normalized === 'CIDADAO' || normalized === 'INSTITUICAO' || normalized === 'EMPRESA') {
    return normalized
  }
  throw new Error('O perfil retornado pela API não é reconhecido.')
}

export type Sessao = {
  access_token: string
  token_type: 'bearer'
  usuario: Usuario
}

export type DocumentoCarteira = {
  id: number
  nome_arquivo: string
  content_type: string
  tamanho_bytes: number
  estado_processamento: 'pendente' | 'processando' | 'concluido' | 'falhou'
  tipo_documento: 'diploma' | 'certidao' | 'comprovante' | null
  nome_extraido: string | null
  data_extraida: string | null
  emissor_extraido: string | null
  erro_processamento: string | null
  criado_em: string
  atualizado_em: string
}

export type Consentimento = {
  id: number
  documento_id: number
  empresa_id: number
  expira_em: string
  revogado_em: string | null
  criado_em: string
}

export type EmissaoEntrada = {
  usuario_id: number
  titulo: string
  tipo_documento: 'diploma' | 'certidao' | 'comprovante'
  conteudo: Record<string, unknown>
}

export type DocumentoEmitido = {
  id: number
  usuario_id: number
  titulo: string
  tipo_documento: EmissaoEntrada['tipo_documento']
  codigo: string
  hash_sha256: string
  estado: 'emitido' | 'revogado'
  emitido_em: string
  revogado_em: string | null
  verification_url: string
  qr_code_url: string
}

export type ErroLinha = { linha: number; erros: string[] }
export type ResultadoLote = {
  lote_id: string
  estado: string
  total_linhas: number
  validas: number
  erros: ErroLinha[]
}
export type RelatorioLote = {
  lote_id: string
  estado: string
  total_linhas: number
  validas: number
  erros_validacao: ErroLinha[]
  erros_processamento: ErroLinha[]
  documentos: Array<{
    linha: number | null
    codigo: string
    hash_sha256: string
    estado: 'emitido' | 'revogado'
    verification_url: string
    qr_code_url: string
  }>
}

export type Verificacao = {
  status: 'VALIDO' | 'INVALIDO' | 'REVOGADO'
  emissor: string | null
  data_emissao: string | null
}

export type DashboardResumo = {
  documentos_emitidos: number
  verificacoes: number
  usuarios_ativos: number
  periodo_dias: number
  tendencia: Array<{
    data: string
    documentos_emitidos: number
    verificacoes: number
  }>
}

export type MensagemChat = {
  role: 'user' | 'assistant'
  content: string
}

export type RespostaChat = {
  resposta: string
  modelo: string
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
const TOKEN_KEY = 'organizaai.accessToken'

export function guardarToken(token: string | null) {
  if (token) sessionStorage.setItem(TOKEN_KEY, token)
  else sessionStorage.removeItem(TOKEN_KEY)
}

async function request<T>(path: string, init: RequestInit = {}, authenticated = true): Promise<T> {
  const headers = new Headers(init.headers)
  const token = authenticated ? sessionStorage.getItem(TOKEN_KEY) : null
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  let response: Response
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      headers,
      credentials: 'include',
    })
  } catch {
    throw new ApiError('Não foi possível conectar à API. Verifique se o servidor está ativo.', 0)
  }

  const contentType = response.headers.get('content-type') ?? ''
  const body: unknown = contentType.includes('application/json')
    ? await response.json()
    : await response.text()
  if (!response.ok) {
    const detail = typeof body === 'object' && body !== null && 'detail' in body
      ? String(body.detail)
      : `A solicitação falhou (HTTP ${response.status}).`
    throw new ApiError(detail, response.status)
  }
  return body as T
}

export const api = {
  login: (email: string, senha: string) =>
    request<Sessao>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, senha }),
    }, false),

  cadastrar: (dados: { nome: string; email: string; senha: string; perfil: Perfil }) =>
    request<Sessao>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(dados),
    }, false),

  buscarUsuarios: (perfil?: Perfil, busca = '') => {
    const query = new URLSearchParams()
    if (perfil) query.set('perfil', perfil)
    if (busca.trim()) query.set('busca', busca.trim())
    return request<Usuario[]>(`/auth/users${query.size ? `?${query}` : ''}`)
  },

  listarDocumentos: (busca = '') => {
    const query = new URLSearchParams()
    if (busca.trim()) query.set('busca', busca.trim())
    return request<DocumentoCarteira[]>(`/wallet/documents${query.size ? `?${query}` : ''}`)
  },

  enviarDocumento: (arquivo: File) => {
    const formData = new FormData()
    formData.append('file', arquivo)
    return request<DocumentoCarteira>('/wallet/documents', { method: 'POST', body: formData })
  },

  baixarDocumento: async (id: number, filename: string) => {
    const headers = new Headers()
    const token = sessionStorage.getItem(TOKEN_KEY)
    if (token) headers.set('Authorization', `Bearer ${token}`)
    const response = await fetch(`${API_URL}/wallet/documents/${id}/download`, {
      headers,
      credentials: 'include',
    })
    if (!response.ok) throw new ApiError('Não foi possível baixar o documento.', response.status)
    const objectUrl = URL.createObjectURL(await response.blob())
    const link = document.createElement('a')
    link.href = objectUrl
    link.download = filename
    link.click()
    URL.revokeObjectURL(objectUrl)
  },

  listarConsentimentos: () => request<Consentimento[]>('/consent'),
  concederConsentimento: (dados: { documento_id: number; empresa_id: number; expira_em: string }) =>
    request<Consentimento>('/consent', { method: 'POST', body: JSON.stringify(dados) }),
  revogarConsentimento: (id: number) => request<void>(`/consent/${id}`, { method: 'DELETE' }),

  emitirDocumento: (dados: EmissaoEntrada) =>
    request<DocumentoEmitido>('/issuance', { method: 'POST', body: JSON.stringify(dados) }),
  enviarLote: (arquivo: File) => {
    const formData = new FormData()
    formData.append('file', arquivo)
    return request<ResultadoLote>('/issuance/batch', { method: 'POST', body: formData })
  },
  relatorioLote: (id: string) => request<RelatorioLote>(`/issuance/batch/${id}`),
  revogarDocumento: (codigo: string, motivo: string) =>
    request<DocumentoEmitido>(`/issuance/${encodeURIComponent(codigo)}/revoke`, {
      method: 'POST',
      body: JSON.stringify({ motivo }),
    }),

  verificar: (codigo: string) =>
    request<Verificacao>(`/verificar/${encodeURIComponent(codigo)}`, {}, false),
  resumoDashboard: () => request<DashboardResumo>('/dashboard/resumo'),
  enviarMensagemChat: (mensagem: string, historico: MensagemChat[] = []) =>
    request<RespostaChat>('/chat/message', {
      method: 'POST',
      body: JSON.stringify({ mensagem, historico }),
    }),
}