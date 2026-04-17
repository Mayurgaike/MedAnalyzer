import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ChevronDown, ChevronRight, Stethoscope, Pill, Thermometer,
  FlaskConical, Calendar, Scissors, Hash
} from 'lucide-react'

const CATEGORY_CONFIG = {
  diagnoses: { icon: Stethoscope, badgeColor: 'bg-white/[0.05] text-neutral-200 border-white/[0.08]' },
  drugs: { icon: Pill, badgeColor: 'bg-white/[0.05] text-neutral-200 border-white/[0.08]' },
  symptoms: { icon: Thermometer, badgeColor: 'bg-white/[0.05] text-neutral-200 border-white/[0.08]' },
  lab_values: { icon: FlaskConical, badgeColor: 'bg-white/[0.05] text-neutral-200 border-white/[0.08]' },
  procedures: { icon: Scissors, badgeColor: 'bg-white/[0.05] text-neutral-200 border-white/[0.08]' },
  dates: { icon: Calendar, badgeColor: 'bg-white/[0.05] text-neutral-200 border-white/[0.08]' },
  genes: { icon: Hash, badgeColor: 'bg-white/[0.05] text-neutral-200 border-white/[0.08]' },
  anatomy: { icon: Hash, badgeColor: 'bg-white/[0.05] text-neutral-200 border-white/[0.08]' },
}
const DEFAULT_CONFIG = { icon: Hash, badgeColor: 'bg-white/[0.05] text-neutral-200 border-white/[0.08]' }

function getEntityLabel(entity) {
  if (typeof entity === 'string') return entity
  return entity.entity || entity.name || entity.metric || entity.date_str || entity.normalized || JSON.stringify(entity)
}

function getEntityDetails(entity) {
  if (typeof entity === 'string') return null
  const parts = []
  if (entity.value != null) parts.push(`Value: ${entity.value}`)
  if (entity.unit) parts.push(`${entity.unit}`)
  if (entity.score) parts.push(`Conf: ${(entity.score * 100).toFixed(0)}%`)
  if (entity.source) parts.push(`Source: ${entity.source}`)
  if (entity.frequency) parts.push(`${entity.frequency}`)
  if (entity.raw_match) parts.push(`"${entity.raw_match}"`)
  if (entity.normalized && entity.date_str) parts.push(`→ ${entity.normalized}`)
  return parts.length > 0 ? parts.join(' · ') : null
}

export default function EntityExplorer({ entities }) {
  const { t } = useTranslation()
  const [openSections, setOpenSections] = useState(new Set(['diagnoses', 'drugs', 'lab_values']))

  if (!entities || Object.keys(entities).length === 0) {
    return <div className="glass-card p-12 text-center"><p className="text-neutral-500 text-lg">{t('entities.no_data')}</p></div>
  }

  const toggleSection = (key) => {
    setOpenSections(prev => { const next = new Set(prev); if (next.has(key)) next.delete(key); else next.add(key); return next })
  }

  const displayOrder = ['diagnoses', 'drugs', 'symptoms', 'lab_values', 'procedures', 'dates', 'genes', 'anatomy']
  const categories = displayOrder
    .filter(key => { const val = entities[key]; return val && ((Array.isArray(val) && val.length > 0) || (typeof val === 'string' && val)) })
    .map(key => ({ key, label: t(`entities.${key}`) || key, items: Array.isArray(entities[key]) ? entities[key] : [entities[key]] }))

  Object.keys(entities).forEach(key => {
    if (displayOrder.includes(key) || key.startsWith('_')) return
    const val = entities[key]
    if (val && ((Array.isArray(val) && val.length > 0) || (typeof val === 'string' && val))) {
      categories.push({ key, label: key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()), items: Array.isArray(val) ? val : [val] })
    }
  })

  return (
    <div className="space-y-3">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="glass-card p-4">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-semibold text-neutral-300 mr-2">{t('entities.title')}:</span>
          {categories.map(cat => (
            <span key={cat.key} className="px-2.5 py-1 rounded-full text-xs font-medium border bg-white/[0.05] text-neutral-300 border-white/[0.08]">
              {cat.label}: {cat.items.length}
            </span>
          ))}
        </div>
      </motion.div>

      {categories.map((cat, catIdx) => {
        const isOpen = openSections.has(cat.key)
        const cfg = CATEGORY_CONFIG[cat.key] || DEFAULT_CONFIG
        const Icon = cfg.icon
        return (
          <motion.div key={cat.key} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: catIdx * 0.04 }} className="glass-card overflow-hidden">
            <button onClick={() => toggleSection(cat.key)} className="w-full p-4 flex items-center justify-between hover:bg-white/[0.03] transition-colors" id={`entity-section-${cat.key}`}>
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 bg-[#292A2C] rounded-md flex items-center justify-center border border-white/8">
                  <Icon className="w-4 h-4 text-white" />
                </div>
                <span className="font-semibold text-white">{cat.label}</span>
                <span className="px-2 py-0.5 bg-white/[0.06] rounded-full text-xs font-medium text-neutral-400 border border-white/[0.06]">{cat.items.length}</span>
              </div>
              {isOpen ? <ChevronDown className="w-5 h-5 text-neutral-500" /> : <ChevronRight className="w-5 h-5 text-neutral-500" />}
            </button>
            <AnimatePresence>
              {isOpen && (
                <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.2 }} className="overflow-hidden">
                  <div className="px-4 pb-4">
                    <div className="flex flex-wrap gap-2">
                      {cat.items.map((item, i) => {
                        const label = getEntityLabel(item)
                        const details = getEntityDetails(item)
                        return (
                          <motion.div key={i} initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: i * 0.02 }} className={`px-3 py-2 rounded-md border text-sm ${cfg.badgeColor}`}>
                            <span className="font-medium">{label}</span>
                            {details && <span className="block text-[11px] opacity-60 mt-0.5">{details}</span>}
                          </motion.div>
                        )
                      })}
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        )
      })}
    </div>
  )
}
