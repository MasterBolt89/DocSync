import { useState } from 'react'
import type { ConfigStatus } from '../types'

interface LandingPageProps {
  onAnalyze: (url: string, demoMode?: boolean) => void
  configStatus: ConfigStatus | null
}

const SAMPLE_REPOS = [
  { label: 'Demo mode (no internet needed)', url: 'DEMO', badge: '🎭 Demo' },
  { label: 'requests', url: 'https://github.com/psf/requests', badge: '🐍 Python' },
  { label: 'fastapi', url: 'https://github.com/fastapi/fastapi', badge: '⚡ FastAPI' },
  { label: 'lodash', url: 'https://github.com/lodash/lodash', badge: '🟨 JS' },
]

const HOW_STEPS = [
  'Fetch repo',
  'Parse files',
  'Extract facts',
  'Detect drift',
  'AI analysis',
  'Show results',
]

export default function LandingPage({ onAnalyze, configStatus }: LandingPageProps) {
  const [url, setUrl] = useState('')
  const [error, setError] = useState('')

  const validate = (val: string) => {
    if (!val.trim()) return 'Please enter a GitHub repository URL.'
    if (!val.includes('github.com')) return 'Only GitHub repositories are supported.'
    return ''
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const err = validate(url)
    if (err) { setError(err); return }
    setError('')
    onAnalyze(url.trim())
  }

  const handleSample = (sample: typeof SAMPLE_REPOS[0]) => {
    if (sample.url === 'DEMO') {
      onAnalyze('demo', true)
    } else {
      setUrl(sample.url)
    }
  }

  return (
    <div>
      {/* Config banner */}
      {configStatus && !configStatus.gemma_configured && (
        <div className="config-banner" style={{ margin: '1rem 1.5rem' }}>
          <span>⚠</span>
          <span>
            <strong>Gemma 4 not configured</strong> — deterministic checks and demo mode work without credentials.{' '}
            Set <code>GEMMA_API_URL</code> and <code>GEMMA_API_KEY</code> in <code>backend/.env</code> to enable AI analysis.
          </span>
        </div>
      )}
      {configStatus?.gemma_configured && (
        <div className="config-banner config-banner-info" style={{ margin: '1rem 1.5rem' }}>
          <div className="gemma-badge"><div className="gemma-pulse" /> Gemma 4 ready</div>
          <span>AI-powered semantic analysis is enabled. Model: {configStatus.gemma_model || 'configured'}</span>
        </div>
      )}

      {/* Hero */}
      <section className="hero">
        <div className="hero-eyebrow">
          <span>✦</span>
          Powered by Gemma 4
        </div>
        <h1>DocSync</h1>
        <p className="hero-tagline">
          Keep your docs aligned with your code.
        </p>
        <p className="text-secondary" style={{ maxWidth: 480, marginBottom: '0.5rem' }}>
          Point DocSync at any public GitHub repository. It analyzes your source code and
          documentation using deterministic parsing and Gemma 4 to surface outdated, misleading,
          or broken documentation.
        </p>

        <form className="hero-form" onSubmit={handleSubmit}>
          <input
            className="input"
            type="url"
            placeholder="https://github.com/owner/repo"
            value={url}
            onChange={e => { setUrl(e.target.value); setError('') }}
            aria-label="GitHub repository URL"
            id="repo-url-input"
          />
          <button type="submit" className="btn btn-primary" id="analyze-btn">
            <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
            </svg>
            Analyze
          </button>
        </form>
        {error && <p style={{ color: 'var(--critical)', fontSize: '0.85rem' }}>{error}</p>}

        {/* Sample repos */}
        <div className="flex gap-2" style={{ flexWrap: 'wrap', justifyContent: 'center' }}>
          <span className="text-muted text-sm">Try:</span>
          {SAMPLE_REPOS.map(s => (
            <button
              key={s.url}
              className="btn btn-ghost btn-sm"
              onClick={() => handleSample(s)}
              id={`sample-${s.label.replace(/\s+/g, '-').toLowerCase()}`}
            >
              {s.badge} {s.label}
            </button>
          ))}
        </div>

        {/* How it works */}
        <div className="how-it-works" style={{ marginTop: '2.5rem' }}>
          {HOW_STEPS.map((step, i) => (
            <div key={i} className="step">
              <div className="step-dot">{i + 1}</div>
              <div className="step-label">{step}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Features grid */}
      <section style={{ padding: '2rem 1.5rem 4rem' }}>
        <div className="container">
          <h4 style={{ textAlign: 'center', marginBottom: '1.5rem' }}>What DocSync detects</h4>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
            {[
              { icon: '🔀', title: 'Renamed symbols', desc: 'Functions, classes, or methods that changed name but docs still use the old one.' },
              { icon: '✒️', title: 'Signature mismatches', desc: 'Documentation examples pass wrong number of arguments to a function.' },
              { icon: '⚙️', title: 'Config drift', desc: 'Environment variables or config keys referenced in docs but missing from code.' },
              { icon: '📦', title: 'Install command errors', desc: 'pip install or npm install commands don\'t match the actual package name.' },
              { icon: '⚡', title: 'Conflicting docs', desc: 'Two documentation files give incompatible instructions for the same feature.' },
              { icon: '🤖', title: 'Semantic reasoning', desc: 'Gemma 4 catches subtle inconsistencies that deterministic rules miss.' },
            ].map(f => (
              <div key={f.title} className="card">
                <div style={{ fontSize: '1.5rem', marginBottom: '0.5rem' }}>{f.icon}</div>
                <h3 style={{ marginBottom: '0.4rem' }}>{f.title}</h3>
                <p className="text-secondary text-sm">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  )
}
