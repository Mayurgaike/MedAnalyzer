import { useTranslation } from 'react-i18next'
import { motion } from 'framer-motion'
import {
  Building2, Pill, FlaskConical, AlertTriangle, Stethoscope, Star,
  Siren, TriangleAlert, CalendarDays
} from 'lucide-react'

const EVENT_CONFIG = {
  hospital_visit: { icon: Building2, color: 'bg-blue-500/15 text-blue-400 border-blue-500/25', dotColor: 'bg-blue-500' },
  new_medication: { icon: Pill, color: 'bg-purple-500/15 text-purple-400 border-purple-500/25', dotColor: 'bg-purple-500' },
  medication: { icon: Pill, color: 'bg-indigo-500/15 text-indigo-400 border-indigo-500/25', dotColor: 'bg-indigo-400' },
  lab_test: { icon: FlaskConical, color: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/25', dotColor: 'bg-emerald-500' },
  anomaly: { icon: AlertTriangle, color: 'bg-red-500/15 text-red-400 border-red-500/25', dotColor: 'bg-red-500' },
  diagnosis: { icon: Stethoscope, color: 'bg-amber-500/15 text-amber-400 border-amber-500/25', dotColor: 'bg-amber-500' },
}
const DEFAULT_CONFIG = { icon: Star, color: 'bg-neutral-500/15 text-neutral-400 border-neutral-500/25', dotColor: 'bg-neutral-400' }

function groupEventsByDate(events) {
  const groups = {}
  events.forEach(event => {
    const date = event.event_date || 'Unknown Date'
    if (!groups[date]) groups[date] = []
    groups[date].push(event)
  })
  return Object.entries(groups).sort(([a], [b]) => b.localeCompare(a))
}

function formatDate(dateStr) {
  try {
    const d = new Date(dateStr)
    if (isNaN(d)) return dateStr
    return d.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
  } catch { return dateStr }
}

export default function Timeline({ events }) {
  const { t } = useTranslation()

  if (!events || events.length === 0) {
    return <div className="glass-card p-12 text-center"><p className="text-neutral-500 text-lg">{t('timeline.empty')}</p></div>
  }

  const groupedEvents = groupEventsByDate(events)

  return (
    <div className="space-y-1">
      <div className="relative">
        <div className="absolute left-[23px] top-4 bottom-4 w-0.5 rounded-full bg-white/10" />

        {groupedEvents.map(([date, dateEvents], groupIndex) => (
          <div key={date} className="mb-6">
            <motion.div
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: groupIndex * 0.05 }}
              className="flex items-center gap-3 mb-3 relative z-10"
            >
              <div className="w-12 h-12 rounded-full bg-[#292A2C] flex items-center justify-center border-2 border-[#1a1a1c]">
                <CalendarDays className="w-5 h-5 text-white" />
              </div>
              <div>
                <p className="text-sm font-bold text-white">{formatDate(date)}</p>
                <p className="text-xs text-neutral-500">{dateEvents.length} event{dateEvents.length !== 1 ? 's' : ''}</p>
              </div>
            </motion.div>

            <div className="ml-[47px] space-y-2">
              {dateEvents.map((event, eventIndex) => {
                const config = EVENT_CONFIG[event.event_type] || DEFAULT_CONFIG
                const Icon = config.icon
                const isHighSeverity = event.severity === 'critical' || event.severity === 'warning'

                return (
                  <motion.div
                    key={event.id || `${date}-${eventIndex}`}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: groupIndex * 0.05 + eventIndex * 0.03 }}
                    className={`glass-card p-4 border-l-4 hover:bg-[#1f1f21] transition-all duration-200 ${
                      isHighSeverity ? 'border-l-red-400' : 'border-l-neutral-700'
                    } ${event.severity === 'critical' ? 'critical-pulse' : ''}`}
                  >
                    <div className="flex items-start gap-3">
                      <div className={`w-9 h-9 rounded-md flex items-center justify-center shrink-0 border ${config.color}`}>
                        <Icon className="w-4 h-4" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <h4 className="font-semibold text-sm text-white">{event.title}</h4>
                          {event.is_first_occurrence && (
                            <span className="px-2 py-0.5 bg-amber-500/15 text-amber-300 rounded-full text-[10px] font-bold uppercase border border-amber-500/25">
                              {t('timeline.first_occurrence')}
                            </span>
                          )}
                          {event.severity === 'critical' && (
                            <span className="px-2 py-0.5 bg-red-500/15 text-red-300 rounded-full text-[10px] font-bold uppercase border border-red-500/25 flex items-center gap-1">
                              <Siren className="w-3 h-3" /> Critical
                            </span>
                          )}
                          {event.severity === 'warning' && (
                            <span className="px-2 py-0.5 bg-amber-500/15 text-amber-300 rounded-full text-[10px] font-bold uppercase border border-amber-500/25 flex items-center gap-1">
                              <TriangleAlert className="w-3 h-3" /> Warning
                            </span>
                          )}
                        </div>
                        {event.description && <p className="text-sm text-neutral-500 mt-1">{event.description}</p>}
                      </div>
                    </div>
                  </motion.div>
                )
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
