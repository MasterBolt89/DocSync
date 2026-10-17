import { useState, useEffect } from 'react'
import { analyzeRepo, fetchConfigStatus } from './utils/api'
import type { AnalysisResult, ConfigStatus } from './types'
import LandingPage from './components/LandingPage'
import Dashboard from './components/Dashboard'
import Navbar from './components/Navbar'

type AppState = 'landing' | 'loading' | 'results' | 'error';

export default function App() {
  const [appState, setAppState] = useState<AppState>('landing')
  const [repoUrl, setRepoUrl] = useState('')
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [error, setError] = useState<string>('')
  const [configStatus, setConfigStatus] = useState<ConfigStatus | null>(null)
  const [loadingStep, setLoadingStep] = useState(0)

  useEffect(() => {
    fetchConfigStatus().then(setConfigStatus).catch(() => {})
  }, [])

  const handleAnalyze = async (url: string, demoMode = false) => {
    setRepoUrl(url)
    setAppState('loading')
    setError('')
    setLoadingStep(0)

    // Animate loading steps
    const steps = [0, 1, 2, 3, 4]
    const timers = steps.map((s, i) =>
      setTimeout(() => setLoadingStep(s), i * 900)
    )

    try {
      const res = await analyzeRepo(url, demoMode)
      timers.forEach(clearTimeout)
      setResult(res)
      setAppState('results')
    } catch (e: unknown) {
      timers.forEach(clearTimeout)
      setError(e instanceof Error ? e.message : 'Analysis failed')
      setAppState('error')
    }
  }

  const handleReset = () => {
    setAppState('landing')
    setResult(null)
    setError('')
    setLoadingStep(0)
  }

  return (
    <>
      <Navbar onLogoClick={handleReset} />
      <main style={{ flex: 1 }}>
        {appState === 'landing' && (
          <LandingPage
            onAnalyze={handleAnalyze}
            configStatus={configStatus}
          />
        )}
        {appState === 'loading' && (
          <div className="loading-state fade-in">
            <div className="spinner" />
            <div>
              <h3 style={{ marginBottom: '1rem' }}>Analyzing repository…</h3>
              <div className="loading-steps">
                {[
                  'Fetching repository structure',
                  'Downloading relevant files',
                  'Extracting code facts',
                  'Running deterministic checks',
                  'Running Gemma 4 semantic analysis',
                ].map((step, i) => (
                  <div
                    key={i}
                    className={`loading-step ${
                      i < loadingStep ? 'done' : i === loadingStep ? 'active' : ''
                    }`}
                  >
                    {step}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
        {appState === 'results' && result && (
          <Dashboard result={result} onBack={handleReset} />
        )}
        {appState === 'error' && (
          <div className="loading-state fade-in">
            <div className="empty-icon error-state">⚠</div>
            <h3 className="error-state">Analysis Failed</h3>
            <p className="text-secondary" style={{ maxWidth: 480, textAlign: 'center' }}>{error}</p>
            <button className="btn btn-ghost" onClick={handleReset}>← Back</button>
          </div>
        )}
      </main>
    </>
  )
}
