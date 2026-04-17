import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import App from './App'
import './index.css'

import en from './i18n/en.json'
import hi from './i18n/hi.json'
import mr from './i18n/mr.json'

// Initialize i18next
i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    hi: { translation: hi },
    mr: { translation: mr },
  },
  lng: localStorage.getItem('medanalyzer-lang') || 'en',
  fallbackLng: 'en',
  interpolation: {
    escapeValue: false,
  },
})

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
)
