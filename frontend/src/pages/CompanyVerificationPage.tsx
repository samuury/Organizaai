import { useEffect, useRef, useState, type FormEvent } from 'react'
import { BrowserQRCodeReader } from '@zxing/browser'
import { BadgeCheck, Camera, CameraOff, FileQuestion, ShieldAlert } from 'lucide-react'
import { ApiError, api, type Verificacao } from '../api/client'

function codigoDaLeitura(value: string) {
  try {
    const url = new URL(value)
    const match = url.pathname.match(/\/verificar\/([^/]+)/)
    return match?.[1] ?? value
  } catch {
    return value.trim()
  }
}

const resultadoLabel: Record<Verificacao['status'], string> = {
  VALIDO: 'Documento válido',
  INVALIDO: 'Código não encontrado',
  REVOGADO: 'Documento revogado',
}

export default function CompanyVerificationPage() {
  const [codigo, setCodigo] = useState('')
  const [resultado, setResultado] = useState<Verificacao | null>(null)
  const [erro, setErro] = useState('')
  const [consultando, setConsultando] = useState(false)
  const [scanning, setScanning] = useState(false)
  const [cameraError, setCameraError] = useState('')
  const videoRef = useRef<HTMLVideoElement>(null)
  const stopScannerRef = useRef<(() => void) | null>(null)

  async function consultar(cleanCode: string) {
    if (!cleanCode) return
    setConsultando(true)
    setErro('')
    setResultado(null)
    try {
      setCodigo(cleanCode)
      setResultado(await api.verificar(cleanCode))
    } catch (error) {
      setErro(error instanceof ApiError ? error.message : 'Não foi possível consultar a verificação.')
    } finally {
      setConsultando(false)
    }
  }

  async function verificar(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    await consultar(codigoDaLeitura(codigo))
  }

  async function iniciarCamera() {
    setCameraError('')
    if (!navigator.mediaDevices?.getUserMedia || !videoRef.current) {
      setCameraError('Este navegador não permite leitura de QR pela câmera.')
      return
    }
    try {
      const reader = new BrowserQRCodeReader()
      const controls = await reader.decodeFromVideoDevice(undefined, videoRef.current, (result) => {
        if (!result) return
        const scannedCode = codigoDaLeitura(result.getText())
        setCodigo(scannedCode)
        stopScannerRef.current?.()
        setScanning(false)
        void consultar(scannedCode)
      })
      stopScannerRef.current = () => controls.stop()
      setScanning(true)
    } catch {
      setCameraError('Não foi possível acessar a câmera. Confira a permissão do navegador.')
      setScanning(false)
    }
  }

  function pararCamera() {
    stopScannerRef.current?.()
    stopScannerRef.current = null
    setScanning(false)
  }

  useEffect(() => () => stopScannerRef.current?.(), [])

  return (
    <section className="workspace-page" aria-labelledby="verification-title">
      <header className="page-heading workspace-heading">
        <div><p className="eyebrow">EMPRESA / AUTENTICIDADE</p><h1 id="verification-title">Verificar documento</h1><p className="heading-copy">Consulte o código ou leia o QR para confirmar uma emissão.</p></div>
      </header>

      <div className="verification-grid">
        <section className="content-panel verify-panel" aria-labelledby="code-lookup-title">
          <div className="panel-heading"><div className="panel-icon"><FileQuestion size={18} aria-hidden="true" /></div><div><h2 id="code-lookup-title">Consulta por código</h2><p>Digite ou cole o código de verificação.</p></div></div>
          <form className="verify-form" onSubmit={verificar}>
            <label className="field-label" htmlFor="verification-code">Código do documento</label>
            <div className="verify-input-row"><input className="text-input" id="verification-code" autoComplete="off" required value={codigo} onChange={(event) => setCodigo(event.target.value)} /><button className="primary-button" type="submit" disabled={consultando}>{consultando ? 'Consultando...' : 'Verificar'}</button></div>
          </form>
          {erro ? <p className="form-alert" role="alert">{erro}</p> : null}
          {resultado ? <div className={`verification-result result-${resultado.status.toLowerCase()}`} role="status"><div className="result-icon">{resultado.status === 'VALIDO' ? <BadgeCheck size={22} /> : <ShieldAlert size={22} />}</div><div><h3>{resultadoLabel[resultado.status]}</h3><dl><div><dt>Emissor</dt><dd>{resultado.emissor ?? 'Não identificado'}</dd></div><div><dt>Data de emissão</dt><dd>{resultado.data_emissao ? new Intl.DateTimeFormat('pt-BR', { dateStyle: 'long' }).format(new Date(resultado.data_emissao)) : '—'}</dd></div></dl></div></div> : null}
        </section>

        <section className="content-panel scan-panel" aria-labelledby="qr-lookup-title">
          <div className="panel-heading"><div className="panel-icon panel-icon-gold"><Camera size={18} aria-hidden="true" /></div><div><h2 id="qr-lookup-title">Leitura por QR Code</h2><p>Aponte a câmera para o código do documento.</p></div></div>
          <div className={`camera-frame${scanning ? ' camera-active' : ''}`}>
            <video ref={videoRef} muted playsInline aria-label="Visualização da câmera para ler código QR" />
            {!scanning ? <div className="camera-placeholder"><Camera size={28} aria-hidden="true" /><span>A câmera será ativada após sua permissão.</span></div> : null}
          </div>
          {cameraError ? <p className="form-alert" role="alert">{cameraError}</p> : null}
          <button className="outline-button camera-button" type="button" onClick={scanning ? pararCamera : () => void iniciarCamera()}>
            {scanning ? <><CameraOff size={16} aria-hidden="true" /> Parar câmera</> : <><Camera size={16} aria-hidden="true" /> Ativar câmera</>}
          </button>
          {codigo && resultado ? <p className="scan-code">Código lido: <code>{codigo}</code></p> : null}
        </section>
      </div>
    </section>
  )
}