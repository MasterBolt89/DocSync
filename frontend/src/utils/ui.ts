import type { Category, FindingSource, Severity, VerificationStatus } from '../types'

export function severityClass(s: Severity): string {
  return `badge-${s}`
}

export function severityColor(s: Severity): string {
  const map: Record<Severity, string> = {
    critical: 'var(--critical)',
    high: 'var(--high)',
    medium: 'var(--medium)',
    low: 'var(--low)',
    info: 'var(--info)',
  }
  return map[s] || 'var(--text-muted)'
}

export function categoryLabel(c: Category): string {
  const map: Record<Category, string> = {
    outdated_signature: 'Outdated Signature',
    removed_symbol: 'Removed Symbol',
    config_drift: 'Config Drift',
    conflicting_docs: 'Conflicting Docs',
    outdated_install: 'Outdated Install',
    unverified_claim: 'Unverified Claim',
  }
  return map[c] || c
}

export function categoryIcon(c: Category): string {
  const map: Record<Category, string> = {
    outdated_signature: '✒️',
    removed_symbol: '🔀',
    config_drift: '⚙️',
    conflicting_docs: '⚡',
    outdated_install: '📦',
    unverified_claim: '❓',
  }
  return map[c] || '📌'
}

export function sourceLabel(s: FindingSource): string {
  const map: Record<FindingSource, string> = {
    deterministic: 'Deterministic',
    ai: 'Gemma 4 AI',
    demo: 'Demo',
  }
  return map[s] || s
}

export function sourceBadgeClass(s: FindingSource): string {
  const map: Record<FindingSource, string> = {
    deterministic: 'badge-det',
    ai: 'badge-ai',
    demo: 'badge-demo',
  }
  return map[s] || ''
}

export function verificationIcon(v: VerificationStatus): string {
  const map: Record<VerificationStatus, string> = {
    verified: '✓',
    plausible: '~',
    hypothesis: '?',
    demo: '🎭',
    invalid: '✗',
  }
  return map[v] || '?'
}

export function shortPath(path: string, maxLen = 40): string {
  if (path.length <= maxLen) return path
  const parts = path.split('/')
  if (parts.length > 2) return `…/${parts.slice(-2).join('/')}`
  return path.slice(-maxLen)
}
