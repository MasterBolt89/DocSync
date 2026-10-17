import { useState, useMemo } from 'react'
import type { AnalysisResult, Finding, FilterSeverity, FilterCategory, FilterSource, Severity } from '../types'
import {
  categoryIcon, categoryLabel, severityClass, severityColor,
  shortPath, sourceBadgeClass, sourceLabel, verificationIcon
} from '../utils/ui'

interface DashboardProps {
  result: AnalysisResult
  onBack: () => void
}

export default function Dashboard({ result, onBack }: DashboardProps) {
  const [selected, setSelected] = useState<Finding | null>(result.findings[0] ?? null)
  const [filterSeverity, setFilterSeverity] = useState<FilterSeverity>('all')
  const [filterCategory, setFilterCategory] = useState<FilterCategory>('all')
  const [filterSource, setFilterSource] = useState<FilterSource>('all')
  const [search, setSearch] = useState('')

  const severities: Severity[] = ['critical', 'high', 'medium', 'low', 'info']

  const filtered = useMemo(() => {
    return result.findings.filter(f => {
      if (filterSeverity !== 'all' && f.severity !== filterSeverity) return false
      if (filterCategory !== 'all' && f.category !== filterCategory) return false
      if (filterSource !== 'all' && f.source !== filterSource) return false
      if (search) {
        const q = search.toLowerCase()
        return (
          f.title.toLowerCase().includes(q) ||
          f.documentation_file.toLowerCase().includes(q) ||
          f.documented_claim.toLowerCase().includes(q) ||
          f.explanation.toLowerCase().includes(q)
        )
      }
      return true
    })
  }, [result.findings, filterSeverity, filterCategory, filterSource, search])

  return (
    <div className="dashboard fade-in">
      {/* Banners */}
      {result.demo_mode && (
        <div className="demo-banner">
          🎭 <strong>Demo Mode</strong> — Results are from a bundled fixture, not a real repository.
          Enter a GitHub URL on the landing page to analyze a real repo.
        </div>
      )}
      {result.gemma_used && (
        <div className="flex items-center gap-2" style={{ fontSize: '0.82rem', color: 'var(--ai-color)' }}>
          <div className="gemma-badge"><div className="gemma-pulse" /> Gemma 4 AI</div>
          Semantic analysis was performed by Gemma 4.
        </div>
      )}
      {!result.gemma_used && !result.demo_mode && (
        <div className="config-banner config-banner-info">
          ℹ Gemma 4 not configured — only deterministic checks ran. Configure <code>GEMMA_API_URL</code> and <code>GEMMA_API_KEY</code> for AI analysis.
        </div>
      )}

      {/* Repo header */}
      <div className="repo-header">
        <div className="repo-avatar">⚡</div>
        <div className="repo-info">
          <div className="repo-name">
            <a href={result.repo_url} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--text-primary)' }}>
              {result.repo_owner}/{result.repo_name}
            </a>
          </div>
          <div className="repo-meta">
            Branch: {result.default_branch} ·
            Scanned in {result.scan_duration_seconds}s ·
            {result.error && <span style={{ color: 'var(--medium)' }}> Partial results (some errors occurred)</span>}
          </div>
        </div>
        <div className="repo-stats">
          <div className="repo-stat">
            <div className="repo-stat-value">{result.files_fetched}</div>
            <div className="repo-stat-label">Files</div>
          </div>
          <div className="repo-stat">
            <div className="repo-stat-value">{result.doc_files}</div>
            <div className="repo-stat-label">Docs</div>
          </div>
          <div className="repo-stat">
            <div className="repo-stat-value">{result.code_files}</div>
            <div className="repo-stat-label">Code</div>
          </div>
          <div className="repo-stat">
            <div className="repo-stat-value" style={{ color: result.total_findings > 0 ? severityColor('high') : 'var(--det-color)' }}>
              {result.total_findings}
            </div>
            <div className="repo-stat-label">Findings</div>
          </div>
        </div>
        <button className="btn btn-ghost btn-sm ml-auto" onClick={onBack}>← New scan</button>
      </div>

      {/* Severity summary */}
      <div className="severity-bar">
        {severities.map(s => {
          const count = result.severity_counts[s] || 0
          if (count === 0) return null
          return (
            <button
              key={s}
              className={`severity-pill ${filterSeverity === s ? 'active' : filterSeverity !== 'all' ? 'inactive' : ''}`}
              style={{ borderColor: severityColor(s), color: severityColor(s) }}
              onClick={() => setFilterSeverity(prev => prev === s ? 'all' : s)}
              id={`filter-sev-${s}`}
            >
              <span className="severity-pill-count">{count}</span>
              <span className="severity-pill-label">{s}</span>
            </button>
          )
        })}
        {filterSeverity !== 'all' && (
          <button className="btn btn-ghost btn-sm" onClick={() => setFilterSeverity('all')}>Clear</button>
        )}
      </div>

      {/* Main findings layout */}
      {result.findings.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">✅</div>
          <h3>No issues detected</h3>
          <p className="text-secondary">
            No documentation inconsistencies were found in the analyzed files.
            {!result.gemma_used && ' Enable Gemma 4 for deeper semantic analysis.'}
          </p>
        </div>
      ) : (
        <div className="findings-layout">
          {/* Left: list */}
          <div className="findings-panel">
            <div className="findings-toolbar">
              <input
                className="search-input"
                placeholder="Search findings…"
                value={search}
                onChange={e => setSearch(e.target.value)}
                id="findings-search"
              />
              <select
                className="filter-select"
                value={filterCategory}
                onChange={e => setFilterCategory(e.target.value as FilterCategory)}
                id="filter-category"
              >
                <option value="all">All categories</option>
                <option value="outdated_signature">Outdated signature</option>
                <option value="removed_symbol">Removed symbol</option>
                <option value="config_drift">Config drift</option>
                <option value="conflicting_docs">Conflicting docs</option>
                <option value="outdated_install">Outdated install</option>
                <option value="unverified_claim">Unverified claim</option>
              </select>
              <select
                className="filter-select"
                value={filterSource}
                onChange={e => setFilterSource(e.target.value as FilterSource)}
                id="filter-source"
              >
                <option value="all">All sources</option>
                <option value="deterministic">Deterministic</option>
                <option value="ai">Gemma 4 AI</option>
                <option value="demo">Demo</option>
              </select>
              <span className="findings-count">{filtered.length} / {result.findings.length}</span>
            </div>

            {filtered.length === 0 ? (
              <div className="empty-state" style={{ padding: '2rem' }}>
                <div className="empty-icon">🔍</div>
                <p className="text-secondary text-sm">No findings match your filters.</p>
              </div>
            ) : (
              filtered.map(f => (
                <FindingCard
                  key={f.id}
                  finding={f}
                  selected={selected?.id === f.id}
                  onClick={() => setSelected(f)}
                />
              ))
            )}
          </div>

          {/* Right: detail */}
          <div>
            {selected ? (
              <FindingDetail finding={selected} repoUrl={result.repo_url} branch={result.default_branch} />
            ) : (
              <div className="empty-state card" style={{ padding: '3rem' }}>
                <div className="empty-icon">👈</div>
                <p className="text-secondary text-sm">Select a finding to see details</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Finding card ──────────────────────────────────────────────────────────────

interface FindingCardProps {
  finding: Finding
  selected: boolean
  onClick: () => void
}

function FindingCard({ finding: f, selected, onClick }: FindingCardProps) {
  return (
    <div
      className={`finding-card ${f.severity} ${selected ? 'selected' : ''}`}
      onClick={onClick}
      id={`finding-${f.id}`}
    >
      <div className="finding-card-header">
        <span className="cat-icon">{categoryIcon(f.category)}</span>
        <span className="finding-card-title">{f.title}</span>
        <span className={`badge ${severityClass(f.severity)}`}>{f.severity}</span>
      </div>
      <div className="finding-card-meta">
        <span className="finding-file">{shortPath(f.documentation_file)}{f.documentation_line ? `:${f.documentation_line}` : ''}</span>
        <span className={`badge ${sourceBadgeClass(f.source)}`}>{sourceLabel(f.source)}</span>
        <span className="finding-confidence">{verificationIcon(f.verification_status)} {Math.round(f.confidence * 100)}%</span>
      </div>
    </div>
  )
}

// ── Finding detail ────────────────────────────────────────────────────────────

interface FindingDetailProps {
  finding: Finding
  repoUrl: string
  branch: string
}

function FindingDetail({ finding: f }: FindingDetailProps) {
  return (
    <div className="finding-detail slide-in">
      <div className="finding-detail-header">
        <span style={{ fontSize: '1.4rem' }}>{categoryIcon(f.category)}</span>
        <div>
          <div className="finding-detail-title">{f.title}</div>
          <div className="finding-detail-badges">
            <span className={`badge ${severityClass(f.severity)}`}>{f.severity}</span>
            <span className={`badge ${sourceBadgeClass(f.source)}`}>{sourceLabel(f.source)}</span>
            <span className="badge" style={{ background: 'var(--bg-base)', color: 'var(--text-muted)', border: '1px solid var(--border)' }}>
              {categoryLabel(f.category)}
            </span>
          </div>
        </div>
      </div>

      {/* Documentation claim */}
      <div className="detail-section">
        <div className="detail-label">
          📄 Documentation claim
          {f.documentation_line && <span style={{ float: 'right', fontWeight: 400, textTransform: 'none', letterSpacing: 0 }}>{shortPath(f.documentation_file)}:{f.documentation_line}</span>}
        </div>
        <div className="detail-code">{f.documented_claim}</div>
        {f.github_doc_url && (
          <a href={f.github_doc_url} target="_blank" rel="noopener noreferrer" className="detail-link">
            🔗 View in GitHub
          </a>
        )}
      </div>

      {/* Evidence */}
      {f.evidence_excerpt && (
        <div className="detail-section">
          <div className="detail-label">
            💻 Code evidence
            {f.evidence_line && <span style={{ float: 'right', fontWeight: 400, textTransform: 'none', letterSpacing: 0 }}>{f.evidence_file && shortPath(f.evidence_file)}:{f.evidence_line}</span>}
          </div>
          <div className="detail-code">{f.evidence_excerpt}</div>
          {f.github_evidence_url && (
            <a href={f.github_evidence_url} target="_blank" rel="noopener noreferrer" className="detail-link">
              🔗 View in GitHub
            </a>
          )}
        </div>
      )}

      {/* Explanation */}
      <div className="detail-section">
        <div className="detail-label">🔍 Explanation</div>
        <div className="detail-text">{f.explanation}</div>
      </div>

      {/* Suggested fix */}
      {f.suggested_fix && (
        <div className="detail-section">
          <div className="detail-label">💡 Suggested fix</div>
          <div className="detail-fix">{f.suggested_fix}</div>
        </div>
      )}

      {/* Confidence */}
      <div className="detail-section">
        <div className="detail-label">Confidence · {verificationIcon(f.verification_status)} {f.verification_status}</div>
        <div className="confidence-bar">
          <div className="confidence-track">
            <div className="confidence-fill" style={{ width: `${f.confidence * 100}%` }} />
          </div>
          <div className="confidence-value">{Math.round(f.confidence * 100)}%</div>
        </div>
      </div>
    </div>
  )
}
