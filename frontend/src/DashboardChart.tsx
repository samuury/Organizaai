import {
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

type TendenciaDiaria = {
  data: string
  documentos_emitidos: number
  verificacoes: number
}

function formatarData(value: string) {
  return new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: 'short' }).format(
    new Date(`${value}T12:00:00`),
  )
}

function formatarNumero(value: number) {
  return new Intl.NumberFormat('pt-BR').format(value)
}

export default function DashboardChart({ data }: { data: TendenciaDiaria[] }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <ComposedChart data={data} margin={{ top: 12, right: 12, bottom: 4, left: -16 }}>
        <CartesianGrid vertical={false} stroke="#e8e9e3" strokeDasharray="3 5" />
        <XAxis
          dataKey="data"
          tickFormatter={formatarData}
          tickLine={false}
          axisLine={false}
          minTickGap={28}
          tick={{ fill: '#536056', fontSize: 11 }}
        />
        <YAxis allowDecimals={false} tickLine={false} axisLine={false} tick={{ fill: '#536056', fontSize: 11 }} />
        <Tooltip
          labelFormatter={(value) => new Intl.DateTimeFormat('pt-BR', { dateStyle: 'medium' }).format(new Date(`${value}T12:00:00`))}
          formatter={(value, name) => [formatarNumero(Number(value)), name === 'documentos_emitidos' ? 'Documentos' : 'Verificações']}
          contentStyle={{ border: '1px solid #e6e8df', borderRadius: 8, boxShadow: '0 12px 30px #23352412' }}
        />
        <Line type="monotone" dataKey="documentos_emitidos" name="documentos_emitidos" stroke="#17745d" strokeWidth={2.5} dot={false} activeDot={{ r: 4, fill: '#17745d' }} />
        <Line type="monotone" dataKey="verificacoes" name="verificacoes" stroke="#d77b57" strokeWidth={2.5} dot={false} activeDot={{ r: 4, fill: '#d77b57' }} />
      </ComposedChart>
    </ResponsiveContainer>
  )
}