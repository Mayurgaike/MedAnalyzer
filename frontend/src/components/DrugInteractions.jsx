import { useTranslation } from 'react-i18next'
import { motion } from 'framer-motion'
import { AlertTriangle, Eye, ShieldCheck, Pill, Info, CircleAlert, CircleCheck } from 'lucide-react'

const SEVERITY_CONFIG = {
  dangerous: { icon: CircleAlert, class: 'severity-dangerous', badge: 'bg-red-500/15 text-red-300 border-red-500/25', iconColor: 'text-red-400' },
  monitor: { icon: Eye, class: 'severity-monitor', badge: 'bg-amber-500/15 text-amber-300 border-amber-500/25', iconColor: 'text-amber-400' },
  safe: { icon: CircleCheck, class: 'severity-safe', badge: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/25', iconColor: 'text-emerald-400' },
}

export default function DrugInteractions({ data }) {
  const { t } = useTranslation()
  if (!data) return null
  const { drug_labels = [], potential_interactions = [], summary = '' } = data

  return (
    <div className="space-y-6">
      {summary && (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="glass-card p-5">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 bg-[#292A2C] rounded-md flex items-center justify-center shrink-0 border border-white/8">
              <Pill className="w-5 h-5 text-white" />
            </div>
            <div>
              <h3 className="font-bold text-white">{t('drugs.title')}</h3>
              <p className="text-sm text-neutral-400 mt-1">{summary}</p>
            </div>
          </div>
        </motion.div>
      )}

      {potential_interactions.length > 0 ? (
        <div className="grid md:grid-cols-2 gap-4">
          {potential_interactions.map((interaction, i) => {
            const cfg = SEVERITY_CONFIG[interaction.severity] || SEVERITY_CONFIG.safe
            const Icon = cfg.icon
            return (
              <motion.div key={i} initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.08 }}
                className={`glass-card p-5 border-l-4 hover:bg-[#1f1f21] transition-all duration-200 ${cfg.class} ${interaction.severity === 'dangerous' ? 'critical-pulse' : ''}`}>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Icon className={`w-5 h-5 ${cfg.iconColor}`} />
                    <div className="flex items-center gap-1.5">
                      <span className="px-2.5 py-1 bg-white/[0.06] rounded-md text-sm font-semibold text-white border border-white/[0.08]">{interaction.drug_pair?.[0]}</span>
                      <span className="text-neutral-600 text-xs font-bold">+</span>
                      <span className="px-2.5 py-1 bg-white/[0.06] rounded-md text-sm font-semibold text-white border border-white/[0.08]">{interaction.drug_pair?.[1]}</span>
                    </div>
                  </div>
                  <span className={`px-2.5 py-1 rounded-full text-[10px] font-bold uppercase border flex items-center gap-1 ${cfg.badge}`}>
                    <Icon className="w-3 h-3" /> {t(`drugs.${interaction.severity}`)}
                  </span>
                </div>
                <p className="text-sm text-neutral-400 leading-relaxed">{interaction.warning_text}</p>
                <div className="mt-3 flex items-center gap-1.5 text-xs text-neutral-500">
                  <Info className="w-3 h-3" />
                  <span>{t('drugs.source')}: {interaction.source}</span>
                </div>
              </motion.div>
            )
          })}
        </div>
      ) : (
        <div className="glass-card p-12 text-center">
          <ShieldCheck className="w-12 h-12 mx-auto text-emerald-400 mb-3" />
          <p className="text-neutral-400 text-lg">{t('drugs.no_interactions')}</p>
        </div>
      )}

      {drug_labels.length > 0 && (
        <div>
          <h4 className="text-sm font-semibold text-neutral-300 mb-3 flex items-center gap-2">
            <Pill className="w-4 h-4 text-neutral-500" />
            Individual Drug Warnings ({drug_labels.length})
          </h4>
          <div className="grid md:grid-cols-2 gap-3">
            {drug_labels.map((label, i) => (
              <motion.div key={i} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 + i * 0.05 }} className="glass-card p-4">
                <h5 className="font-bold text-sm text-white mb-1">{label.drug}</h5>
                {label.warnings && label.warnings !== 'No warnings listed' && <p className="text-xs text-neutral-500 line-clamp-3">{label.warnings}</p>}
              </motion.div>
            ))}
          </div>
        </div>
      )}

      <div className="text-center">
        <p className="text-xs text-neutral-600 italic max-w-lg mx-auto">{t('drugs.disclaimer')}</p>
      </div>
    </div>
  )
}
