// DocSync — TypeScript type definitions

export type Severity = 'critical' | 'high' | 'medium' | 'low' | 'info';
export type Category =
  | 'outdated_signature'
  | 'removed_symbol'
  | 'config_drift'
  | 'conflicting_docs'
  | 'outdated_install'
  | 'unverified_claim';
export type VerificationStatus = 'verified' | 'plausible' | 'hypothesis' | 'demo' | 'invalid';
export type FindingSource = 'deterministic' | 'ai' | 'demo';

export interface Finding {
  id: string;
  title: string;
  category: Category;
  severity: Severity;
  source: FindingSource;

  documentation_file: string;
  documentation_line: number | null;
  documented_claim: string;

  evidence_file: string | null;
  evidence_line: number | null;
  evidence_excerpt: string | null;

  explanation: string;
  suggested_fix: string | null;

  confidence: number;
  verification_status: VerificationStatus;

  github_doc_url: string | null;
  github_evidence_url: string | null;
}

export interface AnalysisResult {
  repo_owner: string;
  repo_name: string;
  repo_url: string;
  default_branch: string;

  files_fetched: number;
  doc_files: number;
  code_files: number;

  findings: Finding[];
  total_findings: number;
  severity_counts: Record<Severity, number>;

  gemma_used: boolean;
  demo_mode: boolean;
  scan_duration_seconds: number;

  error?: string | null;
}

export interface ConfigStatus {
  gemma_configured: boolean;
  gemma_model: string | null;
  github_token_set: boolean;
  message: string;
}

export type FilterSeverity = Severity | 'all';
export type FilterCategory = Category | 'all';
export type FilterSource = FindingSource | 'all';
