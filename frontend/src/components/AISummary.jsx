import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { motion } from 'framer-motion'
import {
  Brain, AlertTriangle, TrendingUp, Pill, Shield, Stethoscope,
  ClipboardList, FlaskConical, Download, Loader2, FileText,
  CircleAlert, CircleDot, CircleCheck, TriangleAlert
} from 'lucide-react'
import jsPDF from 'jspdf'

const SECTION_CONFIG = {
  patient_overview: { icon: FileText },
  critical_alerts: { icon: AlertTriangle },
  lab_trends: { icon: TrendingUp },
  medication_summary: { icon: Pill },
  drug_interaction_warnings: { icon: Shield },
  diagnoses_summary: { icon: Stethoscope },
  recommendations: { icon: ClipboardList },
  follow_up_tests_suggested: { icon: FlaskConical },
  risk_assessment: { icon: Shield },
}

function SummarySection({ title, sectionKey, delay = 0, children }) {
  const cfg = SECTION_CONFIG[sectionKey] || SECTION_CONFIG.patient_overview
  const Icon = cfg.icon
  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay }} className="glass-card p-5">
      <div className="flex items-center gap-3 mb-3">
        <div className="w-8 h-8 bg-[#292A2C] rounded-md flex items-center justify-center border border-white/8">
          <Icon className="w-4 h-4 text-white" />
        </div>
        <h4 className="font-bold text-white">{title}</h4>
      </div>
      {children}
    </motion.div>
  )
}

export default function AISummary({ summary, patient }) {
  const { t } = useTranslation()
  const [isGeneratingPdf, setIsGeneratingPdf] = useState(false)

  if (!summary || Object.keys(summary).length === 0) {
    return (
      <div className="glass-card p-12 text-center">
        <Brain className="w-12 h-12 mx-auto text-neutral-600 mb-3" />
        <p className="text-neutral-500 text-lg">No AI summary available</p>
      </div>
    )
  }

  const handleDownloadPdf = async () => {
    setIsGeneratingPdf(true)
    try {
      const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' })
      const pageWidth = doc.internal.pageSize.getWidth()
      const margin = 15
      const maxWidth = pageWidth - margin * 2
      let yPos = margin
      const addText = (text, fontSize = 10, isBold = false, color = [26, 39, 68]) => {
        doc.setFontSize(fontSize); doc.setFont('helvetica', isBold ? 'bold' : 'normal'); doc.setTextColor(...color)
        const lines = doc.splitTextToSize(text, maxWidth)
        for (const line of lines) { if (yPos > 275) { doc.addPage(); yPos = margin } doc.text(line, margin, yPos); yPos += fontSize * 0.45 }
        yPos += 2
      }
      addText('Medical Report — AI Summary', 18, true, [26, 39, 68]); yPos += 3
      addText(`Patient: ${patient?.name || 'Unknown'}`, 11, false, [80, 80, 80])
      addText(`ID: ${patient?.external_id || '—'}  |  Generated: ${new Date().toLocaleDateString()}`, 9, false, [120, 120, 120]); yPos += 4
      doc.setDrawColor(200, 200, 200); doc.line(margin, yPos, pageWidth - margin, yPos); yPos += 6
      const sections = [
        { key: 'patient_overview', title: t('summary.overview') }, { key: 'critical_alerts', title: t('summary.critical_alerts') },
        { key: 'diagnoses_summary', title: t('summary.diagnoses') }, { key: 'medication_summary', title: t('summary.medications') },
        { key: 'drug_interaction_warnings', title: t('summary.interaction_warnings') }, { key: 'recommendations', title: t('summary.recommendations') },
        { key: 'follow_up_tests_suggested', title: t('summary.follow_up') }, { key: 'risk_assessment', title: t('summary.risk') },
      ]
      for (const section of sections) {
        const value = summary[section.key]; if (!value) continue
        addText(`■ ${section.title}`, 12, true, [26, 39, 68])
        if (typeof value === 'string') { addText(value, 10, false, [60, 60, 60]) }
        else if (Array.isArray(value)) { value.forEach((item, i) => { const text = typeof item === 'object' ? Object.entries(item).map(([k,v])=>`${k}: ${v}`).join(' | ') : String(item); addText(`  ${i+1}. ${text}`, 10, false, [60, 60, 60]) }) }
        else if (typeof value === 'object') { Object.entries(value).forEach(([k, v]) => { if (Array.isArray(v)) { addText(`  ${k}:`, 10, true, [60, 60, 60]); v.forEach((item, i) => addText(`    ${i+1}. ${String(item)}`, 9, false, [80, 80, 80])) } else { addText(`  ${k}: ${v}`, 10, false, [60, 60, 60]) } }) }
        yPos += 3
      }
      yPos += 5; doc.setDrawColor(200, 200, 200); doc.line(margin, yPos, pageWidth - margin, yPos); yPos += 4
      addText(t('summary.disclaimer'), 7, false, [150, 150, 150])
      doc.save(`MedAnalyzer_Report_${patient?.name || 'Patient'}_${new Date().toISOString().slice(0, 10)}.pdf`)
    } catch (err) { console.error('PDF generation failed:', err) }
    finally { setIsGeneratingPdf(false) }
  }

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="glass-card p-5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 bg-[#292A2C] rounded-md flex items-center justify-center border border-white/8">
            <Brain className="w-6 h-6 text-white" />
          </div>
          <div>
            <h3 className="font-bold text-white text-lg">{t('summary.title')}</h3>
            <p className="text-xs text-neutral-500">{t('summary.generated_by')}: {summary._metadata?.model || 'AI'}</p>
          </div>
        </div>
        <button onClick={handleDownloadPdf} disabled={isGeneratingPdf} className="flex items-center gap-2 px-4 py-2.5 text-sm font-medium rounded-md transition-all disabled:opacity-50 bg-[#292A2C] text-white hover:bg-[#363738] border border-white/8" id="download-pdf-button">
          {isGeneratingPdf ? (<><Loader2 className="w-4 h-4 animate-spin" />{t('dashboard.generating_pdf')}</>) : (<><Download className="w-4 h-4" />{t('dashboard.download_pdf')}</>)}
        </button>
      </motion.div>

      <div className="grid gap-4">
        {summary.patient_overview && <SummarySection title={t('summary.overview')} sectionKey="patient_overview" delay={0}><p className="text-neutral-400 leading-relaxed">{summary.patient_overview}</p></SummarySection>}

        {summary.critical_alerts && <SummarySection title={t('summary.critical_alerts')} sectionKey="critical_alerts" delay={0.05}>
          <div className="space-y-2">
            {(Array.isArray(summary.critical_alerts) ? summary.critical_alerts : [summary.critical_alerts]).map((alert, i) => (
              <div key={i} className="flex items-start gap-2 p-3 rounded-md bg-red-500/[0.08] border border-red-500/20">
                <AlertTriangle className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
                <p className="text-sm text-red-300">{typeof alert === 'string' ? alert : JSON.stringify(alert)}</p>
              </div>
            ))}
          </div>
        </SummarySection>}

        {summary.lab_trends && Array.isArray(summary.lab_trends) && <SummarySection title={t('summary.lab_trends')} sectionKey="lab_trends" delay={0.1}>
          <div className="grid md:grid-cols-2 gap-3">
            {summary.lab_trends.map((trend, i) => (
              <div key={i} className="p-3 rounded-md bg-white/[0.03] border border-white/[0.06]">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-semibold text-sm text-white">{trend.metric}</span>
                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${trend.status === 'CRITICAL' ? 'trend-critical' : trend.status === 'RISING' ? 'trend-rising' : trend.status === 'FALLING' ? 'trend-falling' : 'trend-stable'}`}>{trend.status}</span>
                </div>
                <p className="text-xs text-neutral-500">{trend.interpretation}</p>
                {trend.action && <p className="text-xs text-neutral-300 mt-1 font-medium">→ {trend.action}</p>}
              </div>
            ))}
          </div>
        </SummarySection>}

        {summary.medication_summary && <SummarySection title={t('summary.medications')} sectionKey="medication_summary" delay={0.15}>
          <div className="space-y-2">
            {summary.medication_summary.current_medications && <div className="flex flex-wrap gap-2">
              {(Array.isArray(summary.medication_summary.current_medications) ? summary.medication_summary.current_medications : [summary.medication_summary.current_medications]).map((med, i) => (
                <span key={i} className="px-3 py-1.5 bg-white/[0.05] text-neutral-200 rounded-md text-sm font-medium border border-white/[0.08] flex items-center gap-1.5"><Pill className="w-3.5 h-3.5 text-neutral-400" />{typeof med === 'string' ? med : JSON.stringify(med)}</span>
              ))}
            </div>}
            {summary.medication_summary.notes && <p className="text-sm text-neutral-500 mt-2">{summary.medication_summary.notes}</p>}
          </div>
        </SummarySection>}

        {summary.drug_interaction_warnings && <SummarySection title={t('summary.interaction_warnings')} sectionKey="drug_interaction_warnings" delay={0.2}>
          <ul className="space-y-1.5">
            {(Array.isArray(summary.drug_interaction_warnings) ? summary.drug_interaction_warnings : [summary.drug_interaction_warnings]).map((warning, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-neutral-400"><TriangleAlert className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />{typeof warning === 'string' ? warning : JSON.stringify(warning)}</li>
            ))}
          </ul>
        </SummarySection>}

        {summary.diagnoses_summary && <SummarySection title={t('summary.diagnoses')} sectionKey="diagnoses_summary" delay={0.25}>
          <div className="flex flex-wrap gap-2">
            {(Array.isArray(summary.diagnoses_summary) ? summary.diagnoses_summary : [summary.diagnoses_summary]).map((diag, i) => (
              <span key={i} className="px-3 py-1.5 bg-white/[0.05] text-neutral-200 rounded-md text-sm font-medium border border-white/[0.08] flex items-center gap-1.5"><Stethoscope className="w-3.5 h-3.5 text-neutral-400" />{typeof diag === 'string' ? diag : JSON.stringify(diag)}</span>
            ))}
          </div>
        </SummarySection>}

        {summary.recommendations && <SummarySection title={t('summary.recommendations')} sectionKey="recommendations" delay={0.3}>
          <ol className="space-y-2">
            {(Array.isArray(summary.recommendations) ? summary.recommendations : [summary.recommendations]).map((rec, i) => (
              <li key={i} className="flex items-start gap-3 text-sm text-neutral-400">
                <span className="w-6 h-6 bg-[#292A2C] rounded-full flex items-center justify-center text-xs font-bold text-white shrink-0 border border-white/8">{i + 1}</span>
                <span>{typeof rec === 'string' ? rec : JSON.stringify(rec)}</span>
              </li>
            ))}
          </ol>
        </SummarySection>}

        {summary.follow_up_tests_suggested && <SummarySection title={t('summary.follow_up')} sectionKey="follow_up_tests_suggested" delay={0.35}>
          <div className="flex flex-wrap gap-2">
            {(Array.isArray(summary.follow_up_tests_suggested) ? summary.follow_up_tests_suggested : [summary.follow_up_tests_suggested]).map((test, i) => (
              <span key={i} className="px-3 py-1.5 bg-white/[0.05] text-neutral-200 rounded-md text-sm font-medium border border-white/[0.08] flex items-center gap-1.5"><FlaskConical className="w-3.5 h-3.5 text-neutral-400" />{typeof test === 'string' ? test : JSON.stringify(test)}</span>
            ))}
          </div>
        </SummarySection>}

        {summary.risk_assessment && <SummarySection title={t('summary.risk')} sectionKey="risk_assessment" delay={0.4}>
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <span className="text-sm text-neutral-400 font-medium">Overall Risk:</span>
              <span className={`px-4 py-1.5 rounded-full text-sm font-bold flex items-center gap-1.5 ${summary.risk_assessment.overall_risk === 'HIGH' ? 'bg-red-500/15 text-red-300 border border-red-500/25' : summary.risk_assessment.overall_risk === 'MODERATE' ? 'bg-amber-500/15 text-amber-300 border border-amber-500/25' : 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/25'}`}>
                {summary.risk_assessment.overall_risk === 'HIGH' ? <CircleAlert className="w-4 h-4" /> : summary.risk_assessment.overall_risk === 'MODERATE' ? <CircleDot className="w-4 h-4" /> : <CircleCheck className="w-4 h-4" />}
                {summary.risk_assessment.overall_risk}
              </span>
            </div>
            {summary.risk_assessment.risk_factors && <ul className="space-y-1">
              {(Array.isArray(summary.risk_assessment.risk_factors) ? summary.risk_assessment.risk_factors : [summary.risk_assessment.risk_factors]).map((factor, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-neutral-400"><CircleAlert className="w-3 h-3 text-red-400 mt-1 shrink-0" />{typeof factor === 'string' ? factor : JSON.stringify(factor)}</li>
              ))}
            </ul>}
          </div>
        </SummarySection>}
      </div>

      <div className="text-center pt-2"><p className="text-xs text-neutral-600 italic max-w-lg mx-auto">{t('summary.disclaimer')}</p></div>
    </div>
  )
}
