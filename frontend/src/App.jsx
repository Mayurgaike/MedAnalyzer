import { useState, useCallback } from 'react'
import { Routes, Route, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { AnimatePresence } from 'framer-motion'
import Home from './pages/Home'
import Dashboard from './pages/Dashboard'

const API_BASE = 'http://localhost:8000'

export default function App() {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const [analysisData, setAnalysisData] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)

  const changeLanguage = useCallback((lng) => {
    i18n.changeLanguage(lng)
    localStorage.setItem('medanalyzer-lang', lng)
  }, [i18n])

  const handleAnalysis = useCallback(async (files, patientName, patientId, language) => {
    setIsLoading(true)
    setError(null)

    try {
      const formData = new FormData()
      formData.append('patient_name', patientName)
      formData.append('language', language || i18n.language)
      if (patientId) formData.append('patient_id', patientId)

      let endpoint = `${API_BASE}/analyze`
      if (files.length === 1) {
        formData.append('file', files[0])
      } else {
        endpoint = `${API_BASE}/analyze-multiple`
        files.forEach(f => formData.append('files', f))
      }

      const response = await fetch(endpoint, {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        throw new Error(errData.detail || `Server error: ${response.status}`)
      }

      const data = await response.json()
      setAnalysisData(data)
      navigate('/dashboard')
    } catch (err) {
      console.error('Analysis error:', err)
      setError(err.message || t('errors.analysis_failed'))
    } finally {
      setIsLoading(false)
    }
  }, [i18n.language, navigate, t])

  const handleDemoMode = useCallback(async () => {
    setIsLoading(true)
    setError(null)

    try {
      const response = await fetch(`${API_BASE}/demo/data`)
      if (!response.ok) throw new Error('Demo data load failed')
      const data = await response.json()
      setAnalysisData(data)
      navigate('/dashboard')
    } catch (err) {
      console.error('Demo mode error:', err)
      setError(err.message || t('errors.server_error'))
    } finally {
      setIsLoading(false)
    }
  }, [navigate, t])

  const handleLoadPatient = useCallback(async (patientId) => {
    setIsLoading(true)
    setError(null)

    try {
      const [timelineRes, summaryRes] = await Promise.all([
        fetch(`${API_BASE}/patient/${patientId}/timeline`),
        fetch(`${API_BASE}/patient/${patientId}/summary`),
      ])

      if (!timelineRes.ok) throw new Error('Failed to load patient timeline')

      const timelineData = await timelineRes.json()
      const summaryData = summaryRes.ok ? await summaryRes.json() : {}

      setAnalysisData({
        status: 'success',
        patient: timelineData.patient,
        timeline: timelineData.timeline,
        lab_series: timelineData.lab_series,
        trends: timelineData.trends,
        drug_interactions: { drug_labels: [], potential_interactions: [], summary: 'Load full analysis for drug checks' },
        summary: summaryData.summary || {},
      })
      navigate('/dashboard')
    } catch (err) {
      console.error('Load patient error:', err)
      setError(err.message)
    } finally {
      setIsLoading(false)
    }
  }, [navigate])

  return (
    <div className="min-h-screen bg-background">
      <AnimatePresence mode="wait">
        <Routes>
          <Route
            path="/"
            element={
              <Home
                onAnalyze={handleAnalysis}
                onDemoMode={handleDemoMode}
                onLoadPatient={handleLoadPatient}
                onChangeLanguage={changeLanguage}
                isLoading={isLoading}
                error={error}
                onClearError={() => setError(null)}
              />
            }
          />
          <Route
            path="/dashboard"
            element={
              <Dashboard
                data={analysisData}
                onBack={() => navigate('/')}
                onChangeLanguage={changeLanguage}
              />
            }
          />
        </Routes>
      </AnimatePresence>
    </div>
  )
}
