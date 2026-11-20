import { Suspense, lazy, useEffect, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { api, ApiError, type DashboardResumo } from '../api/client'

const DashboardChart = lazy(() => import('../DashboardChart'))

function formatarNumero(value: number) {
  return new Intl.NumberFormat('pt-BR').format(value)
}

export default function DashboardPage() {
  const [resumo, setResumo] = useState<DashboardResumo | null>(null)
  const [erro, setErro] = useState('')
  const [carregando, setCarregando] = useState(true)
  const [atualizacao, setAtualizacao] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    async function carregar() {
      setCarregando(true)
      setErro('')
      try {
        setResumo(await api.resumoDashboard())
      } catch (error) {
        if (!controller.signal.aborted) {
          setErro(error instanceof ApiError ? error.message : 'Não foi possível carregar o resumo.')
        }
      } finally {
        if (!controller.signal.aborted) setCarregando(false)
      }
    }
    void carregar()
    return () => controller.abort()
  }, [atualizacao])

  const cards = resumo ? [
    { label: 'Documentos emitidos', value: resumo.documentos_emitidos, caption: 'Total registrado', tone: 'mint', mark: '01' },
    { label: 'Verificações', value: resumo.verificacoes, caption: `Nos últimos ${resumo.periodo_dias} dias`, tone: 'gold', mark: '02' },
    { label: 'Usuários ativos', value: resumo.usuarios_ativos, caption: `Com atividade em ${resumo.periodo_dias} dias`, tone: 'coral', mark: '03' },
  ] : []

  return (
    <section className="workspace-page dashboard-page" aria-labelledby="page-title">
      <div className="page-heading workspace-heading">
        <div><p className="eyebrow">VISÃO GERAL / ÚLTIMOS 30 DIAS</p><h1 id="page-title">Resumo da plataforma</h1><p className="heading-copy">Atividade de documentos e verificações em um só lugar.</p></div>
        <button className="outline-button" type="button" onClick={() => setAtualizacao((value) => value + 1)} disabled={carregando}><RefreshCw size={16} aria-hidden="true" />Atualizar</button>
      </div>
      {erro ? <div className="form-alert page-alert" role="alert"><span>{erro}</span><button className="link-button" onClick={() => setAtualizacao((value) => value + 1)} type="button">Tentar novamente</button></div> : null}
      <div className="metric-grid" aria-live="polite">
        {cards.map((card, index) => <article className={`metric-card tone-${card.tone}`} key={card.label} style={{ animationDelay: `${index * 90}ms` }}><div className="metric-topline"><span>{card.label}</span><span className="metric-mark">{card.mark}</span></div><strong className="metric-value">{formatarNumero(card.value)}</strong><p>{card.caption}</p></article>)}
        {carregando && !resumo ? [0, 1, 2].map((item) => <article className="metric-card metric-loading" key={item} aria-hidden="true"><span className="skeleton-label" /><span className="skeleton-value" /><span className="skeleton-caption" /></article>) : null}
      </div>
      <section className="chart-panel" aria-labelledby="activity-title">
        <div className="chart-header"><div><p className="eyebrow">MOVIMENTO</p><h2 id="activity-title">Emissões e verificações</h2></div><div className="chart-legend" aria-label="Legenda do gráfico"><span><i className="legend-key key-documents" />Documentos</span><span><i className="legend-key key-checks" />Verificações</span></div></div>
        <div className="chart-area">
          {carregando && !resumo ? <div className="chart-skeleton" aria-label="Carregando gráfico" /> : resumo?.tendencia.length ? <Suspense fallback={<div className="chart-skeleton" aria-label="Carregando gráfico" />}><DashboardChart data={resumo.tendencia} /></Suspense> : <div className="empty-chart">Sem atividade registrada neste período.</div>}
        </div>
        <footer className="chart-footer"><span>Dados agregados por dia</span><span>Período móvel de 30 dias</span></footer>
      </section>
    </section>
  )
}