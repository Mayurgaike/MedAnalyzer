import { useState, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { motion } from 'framer-motion'
import Upload from '../components/Upload'
import {
  Activity, Globe, ChevronDown, User, Hash, Clock, AlertCircle, X,
  Play
} from 'lucide-react'

const LANGUAGES = [
  { code: 'en', label: 'English' },
  { code: 'hi', label: 'हिंदी' },
  { code: 'mr', label: 'मराठी' },
]

export default function Home({
  onAnalyze, onDemoMode, onLoadPatient, onChangeLanguage,
  isLoading, error, onClearError
}) {
  const { t, i18n } = useTranslation()
  const [files, setFiles] = useState([])
  const [patientName, setPatientName] = useState('')
  const [patientId, setPatientId] = useState('')
  const [recentPatients, setRecentPatients] = useState([])
  const [showLangMenu, setShowLangMenu] = useState(false)

  useEffect(() => {
    fetch('http://localhost:8000/patients/recent?limit=5')
      .then(r => r.ok ? r.json() : [])
      .then(setRecentPatients)
      .catch(() => setRecentPatients([]))
  }, [])

  const handleSubmit = useCallback((e) => {
    e.preventDefault()
    if (files.length === 0) return
    if (!patientName.trim()) return
    onAnalyze(files, patientName.trim(), patientId || null, i18n.language)
  }, [files, patientName, patientId, onAnalyze, i18n.language])

  return (
    <div className="min-h-screen">
      {/* Navigation Bar */}
      <nav className="nav-glass sticky top-0 z-50 px-6 py-3">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <img src="/logo.png" alt="MedAnalyzer" className="w-10 h-10 rounded-md object-cover" />
            <div>
              <h1 className="text-lg font-bold text-white">{t('app_name')}</h1>
              <p className="text-xs text-neutral-500 -mt-0.5">{t('tagline')}</p>
            </div>
          </div>

          {/* Language selector */}
          <div className="relative">
            <button
              onClick={() => setShowLangMenu(!showLangMenu)}
              className="flex items-center gap-2 px-3 py-2 rounded-md bg-white/5 hover:bg-white/10 border border-white/8 transition-all text-sm"
            >
              <Globe className="w-4 h-4 text-neutral-400" />
              <span className="text-neutral-200">{LANGUAGES.find(l => l.code === i18n.language)?.label}</span>
              <ChevronDown className="w-3 h-3 text-neutral-500" />
            </button>
            {showLangMenu && (
              <motion.div
                initial={{ opacity: 0, y: -5 }}
                animate={{ opacity: 1, y: 0 }}
                className="absolute right-0 mt-1 w-44 rounded-md shadow-2xl overflow-hidden z-50 bg-[#1a1a1c] border border-white/8"
              >
                {LANGUAGES.map(lang => (
                  <button
                    key={lang.code}
                    onClick={() => { onChangeLanguage(lang.code); setShowLangMenu(false) }}
                    className={`w-full px-4 py-2.5 text-left text-sm flex items-center gap-2 hover:bg-white/5 transition-colors ${
                      i18n.language === lang.code ? 'bg-white/5 font-semibold text-white' : 'text-neutral-400'
                    }`}
                  >
                    <Globe className="w-3.5 h-3.5 text-neutral-500" />
                    <span>{lang.label}</span>
                  </button>
                ))}
              </motion.div>
            )}
          </div>
        </div>
      </nav>

      {/* Error Toast */}
      {error && (
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="fixed top-20 right-6 z-50 max-w-md"
        >
          <div className="rounded-md p-4 shadow-lg flex items-start gap-3 bg-red-500/10 border border-red-500/20">
            <AlertCircle className="w-5 h-5 text-red-400 mt-0.5 shrink-0" />
            <div className="flex-1">
              <p className="text-sm font-medium text-red-300">Error</p>
              <p className="text-sm text-red-400/80 mt-0.5">{error}</p>
            </div>
            <button onClick={onClearError} className="text-red-400/60 hover:text-red-300">
              <X className="w-4 h-4" />
            </button>
          </div>
        </motion.div>
      )}

      <main className="max-w-6xl mx-auto px-6 py-10">
        {/* Hero */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="text-center mb-10"
        >
          <h2 className="text-4xl md:text-5xl font-extrabold text-white mb-3">
            {t('home.title')}
          </h2>
          <p className="text-neutral-500 max-w-2xl mx-auto text-lg">
            {t('home.subtitle')}
          </p>
        </motion.div>

        <div className="grid lg:grid-cols-3 gap-8">
          {/* Left: Upload form */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.1 }}
            className="lg:col-span-2"
          >
            <form onSubmit={handleSubmit} className="space-y-6">
              {/* Patient Info */}
              <div className="glass-card p-6 space-y-4">
                <div className="grid md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-neutral-300 mb-1.5">
                      <User className="w-4 h-4 inline mr-1.5 text-neutral-400" />
                      {t('home.patient_name')}
                    </label>
                    <input
                      type="text"
                      value={patientName}
                      onChange={e => setPatientName(e.target.value)}
                      placeholder={t('home.patient_name_placeholder')}
                      className="input-dark"
                      required
                      id="patient-name-input"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-neutral-300 mb-1.5">
                      <Hash className="w-4 h-4 inline mr-1.5 text-neutral-400" />
                      {t('home.patient_id')}
                    </label>
                    <input
                      type="text"
                      value={patientId}
                      onChange={e => setPatientId(e.target.value)}
                      placeholder={t('home.patient_id_placeholder')}
                      className="input-dark"
                      id="patient-id-input"
                    />
                  </div>
                </div>
              </div>

              {/* Upload Area */}
              <Upload files={files} setFiles={setFiles} />

              {/* Submit */}
              <div className="flex flex-col sm:flex-row gap-3">
                <button
                  type="submit"
                  disabled={isLoading || files.length === 0 || !patientName.trim()}
                  className="flex-1 btn-primary"
                  id="analyze-button"
                >
                  {isLoading ? (
                    <>
                      <div className="loading-dots"><span></span><span></span><span></span></div>
                      <span>{t('home.analyzing')}</span>
                    </>
                  ) : (
                    <>
                      <Activity className="w-5 h-5" />
                      <span>{t('home.analyze_btn')}</span>
                    </>
                  )}
                </button>
              </div>
            </form>

            {/* Demo Mode */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
              className="mt-6"
            >
              <button
                onClick={onDemoMode}
                disabled={isLoading}
                className="w-full glass-card px-6 py-5 text-left hover:bg-[#222224] transition-all duration-300 group border border-dashed border-white/10 hover:border-white/15"
                id="demo-mode-button"
              >
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 bg-[#292A2C] rounded-md flex items-center justify-center group-hover:bg-[#333435] transition-colors">
                    <Play className="w-5 h-5 text-white" />
                  </div>
                  <div>
                    <p className="font-bold text-white text-lg">{t('home.demo_btn')}</p>
                    <p className="text-sm text-neutral-500 mt-0.5">{t('home.demo_subtitle')}</p>
                  </div>
                </div>
              </button>
            </motion.div>
          </motion.div>

          {/* Right: Recent Patients */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.2 }}
          >
            <div className="glass-card p-6">
              <h3 className="font-bold text-white flex items-center gap-2 mb-4">
                <Clock className="w-5 h-5 text-neutral-400" />
                {t('home.recent_patients')}
              </h3>
              {recentPatients.length === 0 ? (
                <p className="text-sm text-neutral-500 text-center py-8">
                  {t('home.no_recent')}
                </p>
              ) : (
                <div className="space-y-2">
                  {recentPatients.map(patient => (
                    <div
                      key={patient.id}
                      className="flex items-center justify-between p-3 rounded-md bg-white/[0.03] hover:bg-white/[0.06] transition-colors border border-white/[0.04]"
                    >
                      <div className="min-w-0">
                        <p className="font-medium text-neutral-200 text-sm truncate">{patient.name}</p>
                        <p className="text-xs text-neutral-500">
                          {patient.report_count} {t('dashboard.report_count')} · ID: {patient.external_id}
                        </p>
                      </div>
                      <button
                        onClick={() => onLoadPatient(patient.id)}
                        disabled={isLoading}
                        className="shrink-0 ml-2 px-3 py-1.5 text-xs font-medium bg-[#292A2C] text-white rounded-md hover:bg-[#363738] transition-colors disabled:opacity-50 border border-white/8"
                      >
                        {t('home.load_patient')}
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        </div>
      </main>

      {/* Loading overlay */}
      {isLoading && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 flex items-center justify-center">
          <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="glass-card p-8 text-center shadow-2xl"
          >
            <div className="w-16 h-16 mx-auto mb-4 rounded-full border-4 border-neutral-700 border-t-white animate-spin" />
            <p className="text-lg font-semibold text-white">{t('home.analyzing')}</p>
            <p className="text-sm text-neutral-500 mt-1">Processing your medical reports with AI...</p>
          </motion.div>
        </div>
      )}
    </div>
  )
}
