import { NavLink, Outlet } from 'react-router-dom'
import { BadgeCheck, Building2, FileText, LayoutDashboard, LogOut, Search, ShieldCheck } from 'lucide-react'
import { useAuth } from '../auth/AuthProvider'
import ChatbotWidget from './ChatbotWidget'
import type { Perfil } from '../api/client'

const linksPorPerfil: Record<Perfil, Array<{ to: string; label: string; icon: typeof FileText }>> = {
  CIDADAO: [
    { to: '/cidadao/carteira', label: 'Minha carteira', icon: FileText },
    { to: '/cidadao/consentimentos', label: 'Acessos concedidos', icon: ShieldCheck },
    { to: '/dashboard', label: 'Resumo', icon: LayoutDashboard },
  ],
  INSTITUICAO: [
    { to: '/instituicao/portal', label: 'Emissões', icon: Building2 },
    { to: '/dashboard', label: 'Resumo', icon: LayoutDashboard },
  ],
  EMPRESA: [
    { to: '/empresa/verificar', label: 'Verificar documento', icon: Search },
    { to: '/dashboard', label: 'Resumo', icon: LayoutDashboard },
  ],
}

const perfilLabel: Record<Perfil, string> = {
  CIDADAO: 'Cidadão',
  INSTITUICAO: 'Instituição',
  EMPRESA: 'Empresa',
}

export default function AppShell() {
  const { usuario, sair } = useAuth()
  if (!usuario) return null
  const links = linksPorPerfil[usuario.perfil]

  return (
    <div className="app-shell">
      <a className="skip-link" href="#conteudo">Pular para o conteúdo</a>
      <aside className="sidebar" aria-label="Navegação principal">
        <NavLink className="shell-brand" to={links[0].to}>
          <span className="brand-symbol" aria-hidden="true">o.</span>
          <span>organiza<span className="brand-light">ai</span></span>
        </NavLink>
        <div className="profile-chip">
          <span className="profile-avatar" aria-hidden="true">{usuario.nome.slice(0, 1).toUpperCase()}</span>
          <span className="profile-identity"><strong>{usuario.nome}</strong><small>{perfilLabel[usuario.perfil]}</small></span>
        </div>
        <nav className="side-nav">
          <p className="nav-caption">ESPAÇO DE TRABALHO</p>
          {links.map(({ to, label, icon: Icon }) => (
            <NavLink className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`} key={to} to={to}>
              <Icon size={18} aria-hidden="true" />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <button className="signout-button" onClick={sair} type="button">
          <LogOut size={17} aria-hidden="true" />
          <span>Sair da conta</span>
        </button>
        <span className="sidebar-version"><BadgeCheck size={14} aria-hidden="true" /> Documentos sob seu controle</span>
      </aside>
      <main className="app-main" id="conteudo">
        <header className="mobile-header">
          <NavLink className="shell-brand" to={links[0].to}>
            <span className="brand-symbol" aria-hidden="true">o.</span>
            <span>organiza<span className="brand-light">ai</span></span>
          </NavLink>
          <button className="mobile-signout" onClick={sair} type="button" aria-label="Sair da conta"><LogOut size={18} /></button>
        </header>
        <nav className="mobile-nav" aria-label="Navegação principal">
          {links.map(({ to, label, icon: Icon }) => (
            <NavLink className={({ isActive }) => `mobile-nav-link${isActive ? ' active' : ''}`} key={to} to={to}>
              <Icon size={16} aria-hidden="true" /><span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <Outlet />
        <ChatbotWidget />
      </main>
    </div>
  )
}