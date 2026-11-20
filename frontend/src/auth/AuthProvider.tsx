import { createContext, useContext, useMemo, useState, type ReactNode } from 'react'
import { api, guardarToken, normalizarPerfil, type Perfil, type Sessao, type Usuario } from '../api/client'

type AuthContextValue = {
  usuario: Usuario | null
  entrar: (email: string, senha: string) => Promise<Sessao>
  cadastrar: (dados: { nome: string; email: string; senha: string; perfil: Perfil }) => Promise<Sessao>
  sair: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)
const SESSION_KEY = 'organizaai.session'

function lerSessao(): Sessao | null {
  const stored = sessionStorage.getItem(SESSION_KEY)
  if (!stored) return null
  try {
    const data = JSON.parse(stored) as Sessao
    return { ...data, usuario: { ...data.usuario, perfil: normalizarPerfil(data.usuario.perfil) } }
  } catch {
    sessionStorage.removeItem(SESSION_KEY)
    guardarToken(null)
    return null
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [sessao, setSessao] = useState<Sessao | null>(lerSessao)

  function salvarSessao(data: Sessao) {
    const normalized = {
      ...data,
      usuario: { ...data.usuario, perfil: normalizarPerfil(data.usuario.perfil) },
    }
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(normalized))
    guardarToken(normalized.access_token)
    setSessao(normalized)
  }

  async function entrar(email: string, senha: string) {
    const data = await api.login(email, senha)
    salvarSessao(data)
    return data
  }

  async function cadastrar(dados: { nome: string; email: string; senha: string; perfil: Perfil }) {
    const data = await api.cadastrar(dados)
    salvarSessao(data)
    return data
  }

  function sair() {
    sessionStorage.removeItem(SESSION_KEY)
    guardarToken(null)
    setSessao(null)
  }

  const value = useMemo(
    () => ({ usuario: sessao?.usuario ?? null, entrar, cadastrar, sair }),
    [sessao],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth deve ser usado dentro de AuthProvider.')
  return context
}