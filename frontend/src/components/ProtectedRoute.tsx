import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/AuthProvider'
import type { Perfil } from '../api/client'

export default function ProtectedRoute({ allowed }: { allowed?: Perfil[] }) {
  const { usuario } = useAuth()
  const location = useLocation()

  if (!usuario) return <Navigate to="/login" replace state={{ from: location }} />
  if (allowed && !allowed.includes(usuario.perfil)) {
    return <Navigate to={homeFor(usuario.perfil)} replace />
  }
  return <Outlet />
}

export function homeFor(perfil: Perfil) {
  if (perfil === 'CIDADAO') return '/cidadao/carteira'
  if (perfil === 'INSTITUICAO') return '/instituicao/portal'
  return '/empresa/verificar'
}