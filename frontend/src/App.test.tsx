import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

describe('App', () => {
  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  beforeEach(() => {
    sessionStorage.clear()
    window.history.replaceState({}, '', '/login')
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        headers: { get: () => 'application/json' },
        json: async () => ({
          documentos_emitidos: 128,
          verificacoes: 942,
          usuarios_ativos: 76,
          periodo_dias: 30,
          tendencia: [
            { data: '2026-11-20', documentos_emitidos: 4, verificacoes: 27 },
          ],
        }),
      }),
    )
  })

  it('exibe a tela de login sem sessão', async () => {
    render(<App />)

    expect(await screen.findByRole('heading', { name: 'Acesse sua conta' })).toBeInTheDocument()
    expect(screen.getByLabelText('E-mail')).toBeRequired()
    expect(screen.getByLabelText('Senha')).toBeRequired()
  })

  it('exibe cadastro com seleção de perfil', async () => {
    window.history.replaceState({}, '', '/cadastro')
    render(<App />)

    expect(await screen.findByRole('heading', { name: 'Crie sua conta' })).toBeInTheDocument()
    expect(screen.getByLabelText('Perfil')).toHaveValue('CIDADAO')
    expect(screen.getByLabelText('Senha')).toHaveAttribute('minLength', '8')
  })

  it('protege rotas internas e redireciona para login', async () => {
    window.history.replaceState({}, '', '/instituicao/portal')
    render(<App />)

    await waitFor(() => expect(window.location.pathname).toBe('/login'))
    expect(await screen.findByText('Acesse sua conta')).toBeInTheDocument()
  })

  it('exibe os indicadores da API para uma sessão autenticada', async () => {
    sessionStorage.setItem('organizaai.session', JSON.stringify({
      access_token: 'test-token',
      token_type: 'bearer',
      usuario: { id: 8, nome: 'Joana Silva', email: 'joana@example.test', perfil: 'CIDADAO' },
    }))
    window.history.replaceState({}, '', '/dashboard')
    render(<App />)

    expect(await screen.findByRole('heading', { name: 'Resumo da plataforma' })).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText('942')).toBeInTheDocument())
    expect(screen.getByText('Documentos emitidos')).toBeInTheDocument()
    expect(screen.getByText('Usuários ativos')).toBeInTheDocument()
  })

  it('envia cidadão que tenta abrir o portal para sua carteira', async () => {
    sessionStorage.setItem('organizaai.session', JSON.stringify({
      access_token: 'test-token',
      token_type: 'bearer',
      usuario: { id: 8, nome: 'Joana Silva', email: 'joana@example.test', perfil: 'CIDADAO' },
    }))
    window.history.replaceState({}, '', '/instituicao/portal')
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    render(<App />)

    expect(await screen.findByRole('heading', { name: 'Meus documentos' })).toBeInTheDocument()
  })

  it('abre emissão somente no perfil instituição', async () => {
    sessionStorage.setItem('organizaai.session', JSON.stringify({
      access_token: 'test-token',
      token_type: 'bearer',
      usuario: { id: 21, nome: 'Instituto Aurora', email: 'secretaria@example.test', perfil: 'INSTITUIÇÃO' },
    }))
    window.history.replaceState({}, '', '/instituicao/portal')
    render(<App />)

    expect(await screen.findByRole('heading', { name: 'Portal de emissão' })).toBeInTheDocument()
  })

  it('abre verificação somente no perfil empresa', async () => {
    sessionStorage.setItem('organizaai.session', JSON.stringify({
      access_token: 'test-token',
      token_type: 'bearer',
      usuario: { id: 34, nome: 'Empresa Exemplo', email: 'rh@example.test', perfil: 'EMPRESA' },
    }))
    window.history.replaceState({}, '', '/empresa/verificar')
    render(<App />)

    expect(await screen.findByRole('heading', { name: 'Verificar documento' })).toBeInTheDocument()
    expect(screen.getByLabelText('Código do documento')).toBeInTheDocument()
  })
})