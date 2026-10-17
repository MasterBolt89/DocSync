// DocSync — API client (calls proxied /api/* -> backend)
import type { AnalysisResult, ConfigStatus } from '../types';

const BASE = '/api';

export async function analyzeRepo(repoUrl: string, demoMode = false): Promise<AnalysisResult> {
  const res = await fetch(`${BASE}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ repo_url: repoUrl, demo_mode: demoMode }),
  });

  if (!res.ok) {
    const data = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(data.detail || `HTTP ${res.status}`);
  }

  return res.json();
}

export async function fetchConfigStatus(): Promise<ConfigStatus> {
  const res = await fetch(`${BASE}/config-status`);
  if (!res.ok) throw new Error('Failed to fetch config status');
  return res.json();
}

export async function checkHealth(): Promise<{ status: string }> {
  const res = await fetch(`${BASE}/health`);
  if (!res.ok) throw new Error('Backend unreachable');
  return res.json();
}
