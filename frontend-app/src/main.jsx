import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { initSentry, SentryErrorBoundary } from './sentry.js'

initSentry()

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <SentryErrorBoundary fallback={<p>Une erreur est survenue. Merci de recharger la page.</p>}>
      <App />
    </SentryErrorBoundary>
  </StrictMode>,
)
