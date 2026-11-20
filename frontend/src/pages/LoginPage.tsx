import { useState, type FormEvent } from 'react'
import { ArrowRight, LockKeyhole } from 'lucide-react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { ApiError } from '../api/client'
import { useAuth } from '../auth/AuthProvider'
import { homeFor } from '../components/ProtectedRoute'

type LocationState = { from?: { pathname?: string } }

export default function LoginPage() {
  const { usuario, entrar } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [senha, setSenha] = useState('')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  if (usuario) return <Navigate to={homeFor(usuario.perfil)} replace />

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setErro('')
    setEnviando(true)
    try {
      const session = await entrar(email.trim(), senha)
      const state = location.state as LocationState | null
      const destination = state?.from?.pathname ?? homeFor(session.usuario.perfil)
      navigate(destination, { replace: true })
    } catch (error) {
      setErro(error instanceof ApiError ? error.message : 'Não foi possível entrar. Tente novamente.')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-aside" aria-label="Organiza AI">
        <Link className="auth-brand" to="/login"><span className="brand-symbol">o.</span> organiza<span>ai</span></Link>
        <div className="auth-aside-copy">
          <span className="auth-kicker">DOCUMENTOS, COM AUTONOMIA</span>
          <h1>O que é seu,<br />sob seu controle.</h1>
          <p>Guarde, compartilhe e verifique documentos com segurança e consentimento.</p>
        </div>
        <span className="auth-aside-note">Organiza AI · Carteira digital</span>
      </section>
      <section className="auth-content" aria-labelledby="login-title">
        <div className="auth-form-wrap">
          <div className="auth-icon"><LockKeyhole size={21} aria-hidden="true" /></div>
          <p className="eyebrow">BEM-VINDO DE VOLTA</p>
          <h2 id="login-title">Acesse sua conta</h2>
          <p className="auth-subtitle">Entre para continuar de onde parou.</p>
          <form className="form-stack" onSubmit={submit}>
            <label className="field-label" htmlFor="login-email">E-mail</label>
            <input id="login-email" className="text-input" type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} />
            <div className="field-label-row">
              <label className="field-label" htmlFor="login-password">Senha</label>
            </div>
            <input id="login-password" className="text-input" type="password" autoComplete="current-password" required value={senha} onChange={(event) => setSenha(event.target.value)} />
            {erro ? <p className="form-alert" role="alert">{erro}</p> : null}
            <button className="primary-button full-button" type="submit" disabled={enviando}>
              {enviando ? 'Entrando...' : 'Entrar'} <ArrowRight size={17} aria-hidden="true" />
            </button>
          </form>
          <p className="auth-switch">Ainda não tem uma conta? <Link to="/cadastro">Criar conta</Link></p>
          <p className="auth-privacy">Ao continuar, seus documentos permanecem privados até você conceder acesso.</p>
        </div>
      </section>
    </main>
  )
}