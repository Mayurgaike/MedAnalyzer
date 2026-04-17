import { useTranslation } from 'react-i18next'
import { motion } from 'framer-motion'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceArea
} from 'recharts'
import {
  TrendingUp, ArrowUpRight, ArrowDownRight,
  AlertTriangle, HelpCircle, CheckCircle, CircleAlert
} from 'lucide-react'

const TREND_ICONS = {
  RISING: { icon: ArrowUpRight, class: 'trend-rising' },
  FALLING: { icon: ArrowDownRight, class: 'trend-falling' },
  STABLE: { icon: CheckCircle, class: 'trend-stable' },
  CRITICAL: { icon: CircleAlert, class: 'trend-critical' },
  INSUFFICIENT_DATA: { icon: HelpCircle, class: 'bg-neutral-500/15 text-neutral-400 border border-neutral-500/25' },
}

const CHART_COLORS = [
  '#94a3b8', '#a3a3a3', '#78716c', '#9ca3af', '#a1a1aa',
  '#71717a', '#737373', '#6b7280', '#64748b', '#57534e',
]

function formatDate(dateStr) {
  try {
    const d = new Date(dateStr)
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  } catch { return dateStr }
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-md p-3 shadow-xl bg-[#1a1a1c] border border-white/10">
      <p className="text-xs font-semibold text-white mb-1">{label}</p>
      {payload.map((entry, i) => (
        <p key={i} className="text-sm text-neutral-300">
          {entry.name}: <span className="font-bold text-white">{entry.value}</span> {entry.payload?.unit || ''}
        </p>
      ))}
    </div>
  )
}

export default function TrendChart({ trends, labSeries }) {
  const { t } = useTranslation()

  if (!trends || trends.length === 0) {
    return <div className="glass-card p-12 text-center"><p className="text-neutral-500 text-lg">No trend data available</p></div>
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
        {trends.map((trend, i) => {
          const cfg = TREND_ICONS[trend.trend] || TREND_ICONS.STABLE
          const Icon = cfg.icon
          return (
            <motion.div
              key={trend.metric}
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: i * 0.05 }}
              className={`glass-card p-4 ${trend.trend === 'CRITICAL' ? 'critical-pulse' : ''}`}
            >
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-sm font-semibold text-neutral-300 truncate">{trend.metric}</h4>
                <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold flex items-center gap-1 ${cfg.class}`}>
                  <Icon className="w-3 h-3" />
                  {t(`trends.${trend.trend.toLowerCase()}`) || trend.trend}
                </span>
              </div>
              <p className="text-2xl font-bold text-white">
                {trend.current_value}
                <span className="text-sm font-normal text-neutral-500 ml-1">{trend.unit}</span>
              </p>
              {trend.trend !== 'INSUFFICIENT_DATA' && (
                <div className="flex items-center gap-1 mt-1">
                  <TrendingUp className={`w-3.5 h-3.5 ${
                    trend.change_percent > 0 ? 'text-red-400' : trend.change_percent < 0 ? 'text-blue-400' : 'text-emerald-400'
                  }`} />
                  <span className={`text-xs font-medium ${
                    trend.change_percent > 0 ? 'text-red-400' : trend.change_percent < 0 ? 'text-blue-400' : 'text-emerald-400'
                  }`}>
                    {trend.change_percent > 0 ? '+' : ''}{trend.change_percent}%
                  </span>
                  <span className="text-xs text-neutral-500 ml-1">
                    · {trend.data_point_count} {t('trends.data_points').toLowerCase()}
                  </span>
                </div>
              )}
              {trend.threshold_status !== 'normal' && (
                <p className="text-xs text-red-400 mt-1 font-medium">{trend.threshold_label}</p>
              )}
            </motion.div>
          )
        })}
      </div>

      {Object.entries(labSeries).map(([metric, dataPoints], chartIdx) => {
        if (dataPoints.length < 1) return null
        const trendInfo = trends.find(t => t.metric === metric)
        const chartData = dataPoints.map(dp => ({ date: formatDate(dp.date), value: dp.value, unit: dp.unit, fullDate: dp.date }))
        const refMin = dataPoints[0]?.reference_min
        const refMax = dataPoints[0]?.reference_max
        const allValues = dataPoints.map(d => d.value)
        const yMin = Math.min(...allValues, refMin || Infinity) * 0.85
        const yMax = Math.max(...allValues, refMax || -Infinity) * 1.15

        return (
          <motion.div key={metric} initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: chartIdx * 0.08 }} className="glass-card p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-lg font-bold text-white">{metric}</h3>
                <p className="text-sm text-neutral-500">{trendInfo?.message || `${dataPoints.length} data point(s)`}</p>
              </div>
              {trendInfo && (
                <span className={`px-3 py-1 rounded-full text-xs font-bold flex items-center gap-1 ${TREND_ICONS[trendInfo.trend]?.class || ''}`}>
                  {(() => { const TIcon = TREND_ICONS[trendInfo.trend]?.icon; return TIcon ? <TIcon className="w-3.5 h-3.5" /> : null })()}
                  {trendInfo.trend}
                </span>
              )}
            </div>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis dataKey="date" tick={{ fontSize: 12, fill: '#737373' }} axisLine={{ stroke: 'rgba(255,255,255,0.08)' }} tickLine={{ stroke: 'rgba(255,255,255,0.05)' }} />
                  <YAxis domain={[Math.floor(yMin), Math.ceil(yMax)]} tick={{ fontSize: 12, fill: '#737373' }} axisLine={{ stroke: 'rgba(255,255,255,0.08)' }} tickLine={{ stroke: 'rgba(255,255,255,0.05)' }} />
                  <Tooltip content={<CustomTooltip />} />
                  {refMin != null && refMax != null && (
                    <ReferenceArea y1={refMin} y2={refMax} fill="rgba(16, 185, 129, 0.06)" stroke="rgba(16, 185, 129, 0.2)" strokeDasharray="3 3" label={{ value: t('trends.reference_range'), position: 'insideTopRight', fill: '#10b981', fontSize: 10 }} />
                  )}
                  <Line type="monotone" dataKey="value" stroke={CHART_COLORS[chartIdx % CHART_COLORS.length]} strokeWidth={2} dot={{ r: 4, strokeWidth: 2, fill: '#121214' }} activeDot={{ r: 6, strokeWidth: 0, fill: '#fff' }} name={metric} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </motion.div>
        )
      })}
    </div>
  )
}
