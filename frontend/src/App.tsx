import { Suspense, lazy } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './auth/AuthProvider'
import AppShell from './components/AppShell'
import ProtectedRoute, { homeFor } from './components/ProtectedRoute'

const CitizenWalletPage = lazy(() => import('./pages/CitizenWalletPage'))
const CompanyVerificationPage = lazy(() => import('./pages/CompanyVerificationPage'))
const ConsentPage = lazy(() => import('./pages/ConsentPage'))
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const InstitutionPortalPage = lazy(() => import('./pages/InstitutionPortalPage'))
const LoginPage = lazy(() => import('./pages/LoginPage'))
const RegisterPage = lazy(() => import('./pages/RegisterPage'))
const PublicVerificationPage = lazy(() => import('./pages/PublicVerificationPage'))

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Suspense fallback={<div className="route-loading" role="status">Carregando tela...</div>}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/cadastro" element={<RegisterPage />} />
            <Route path="/verificar/:codigo" element={<PublicVerificationPage />} />
            <Route element={<ProtectedRoute />}>
              <Route element={<AppShell />}>
                <Route path="/" element={<HomeRedirect />} />
                <Route path="/dashboard" element={<DashboardPage />} />
                <Route element={<ProtectedRoute allowed={['CIDADAO']} />}>
                  <Route path="/cidadao/carteira" element={<CitizenWalletPage />} />
                  <Route path="/cidadao/consentimentos" element={<ConsentPage />} />
                </Route>
                <Route element={<ProtectedRoute allowed={['INSTITUICAO']} />}>
                  <Route path="/instituicao/portal" element={<InstitutionPortalPage />} />
                </Route>
                <Route element={<ProtectedRoute allowed={['EMPRESA']} />}>
                  <Route path="/empresa/verificar" element={<CompanyVerificationPage />} />
                </Route>
              </Route>
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </BrowserRouter>
    </AuthProvider>
  )
}

function HomeRedirect() {
  const { usuario } = useAuth()
  return <Navigate to={usuario ? homeFor(usuario.perfil) : '/login'} replace />
}