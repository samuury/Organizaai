import { useState, type FormEvent } from 'react'
import { ArrowRight, UserRoundPlus } from 'lucide-react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { ApiError, type Perfil } from '../api/client'
import { useAuth } from '../auth/AuthProvider'
import { homeFor } from '../components/ProtectedRoute'

export default function RegisterPage() {
  const { usuario, cadastrar } = useAuth()
  const navigate = useNavigate()
  const [nome, setNome] = useState('')
  const [email, setEmail] = useState('')
  const [senha, setSenha] = useState('')
  const [perfil, setPerfil] = useState<Perfil>('CIDADAO')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  if (usuario) return <Navigate to={homeFor(usuario.perfil)} replace />

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setErro('')
    setEnviando(true)
    try {
      const session = await cadastrar({ nome: nome.trim(), email: email.trim(), senha, perfil })
      navigate(homeFor(session.usuario.perfil), { replace: true })
    } catch (error) {
      setErro(error instanceof ApiError ? error.message : 'Não foi possível criar a conta. Tente novamente.')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <main className="auth-page register-page">
      <section className="auth-aside" aria-label="Organiza AI">
        <Link className="auth-brand" to="/login"><span className="brand-symbol">o.</span> organiza<span>ai</span></Link>
        <div className="auth-aside-copy">
          <span className="auth-kicker">UM LUGAR PARA CADA DOCUMENTO</span>
          <h1>Mais clareza<br />para compartilhar.</h1>
          <p>Você decide quem acessa seus documentos e por quanto tempo.</p>
        </div>
        <span className="auth-aside-note">Organiza AI · Carteira digital</span>
      </section>
      <section className="auth-content" aria-labelledby="register-title">
        <div className="auth-form-wrap">
          <div className="auth-icon"><UserRoundPlus size={21} aria-hidden="true" /></div>
          <p className="eyebrow">COMECE POR AQUI</p>
          <h2 id="register-title">Crie sua conta</h2>
          <p className="auth-subtitle">Escolha como você vai usar o Organiza AI.</p>
          <form className="form-stack" onSubmit={submit}>
            <label className="field-label" htmlFor="register-name">Nome completo ou razão social</label>
            <input id="register-name" className="text-input" autoComplete="name" minLength={2} maxLength={255} required value={nome} onChange={(event) => setNome(event.target.value)} />
            <label className="field-label" htmlFor="register-email">E-mail</label>
            <input id="register-email" className="text-input" type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} />
            <label className="field-label" htmlFor="register-role">Perfil</label>
            <select id="register-role" className="text-input select-input" value={perfil} onChange={(event) => setPerfil(event.target.value as Perfil)}>
              <option value="CIDADAO">Cidadão · organizar documentos</option>
              <option value="INSTITUICAO">Instituição · emitir documentos</option>
              <option value="EMPRESA">Empresa · verificar documentos</option>
            </select>
            <label className="field-label" htmlFor="register-password">Senha</label>
            <input id="register-password" className="text-input" type="password" autoComplete="new-password" minLength={8} required value={senha} onChange={(event) => setSenha(event.target.value)} />
            <span className="field-hint">Use pelo menos 8 caracteres.</span>
            {erro ? <p className="form-alert" role="alert">{erro}</p> : null}
            <button className="primary-button full-button" type="submit" disabled={enviando}>
              {enviando ? 'Criando conta...' : 'Criar conta'} <ArrowRight size={17} aria-hidden="true" />
            </button>
          </form>
          <p className="auth-switch">Já tem uma conta? <Link to="/login">Entrar</Link></p>
        </div>
      </section>
    </main>
  )
}