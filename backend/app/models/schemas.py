"""
DocSync — Pydantic data models.
"""
from __future__ import annotations

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


# ── Enumerations ──────────────────────────────────────────────────────────────

class Severity(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"
    info = "info"


class Category(str, Enum):
    outdated_signature = "outdated_signature"
    removed_symbol = "removed_symbol"
    config_drift = "config_drift"
    conflicting_docs = "conflicting_docs"
    outdated_install = "outdated_install"
    unverified_claim = "unverified_claim"


class VerificationStatus(str, Enum):
    verified = "verified"           # cross-referenced against real code/files
    plausible = "plausible"         # AI determined likely issue but not byte-exact
    hypothesis = "hypothesis"       # flagged by AI, evidence indirect
    demo = "demo"                   # demo-mode fixture
    invalid = "invalid"             # references could not be validated


class FindingSource(str, Enum):
    deterministic = "deterministic"
    ai = "ai"
    demo = "demo"


# ── Core finding ─────────────────────────────────────────────────────────────

class Finding(BaseModel):
    id: str
    title: str
    category: Category
    severity: Severity
    source: FindingSource = FindingSource.deterministic

    documentation_file: str
    documentation_line: Optional[int] = None
    documented_claim: str

    evidence_file: Optional[str] = None
    evidence_line: Optional[int] = None
    evidence_excerpt: Optional[str] = None

    explanation: str
    suggested_fix: Optional[str] = None

    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    verification_status: VerificationStatus = VerificationStatus.hypothesis

    github_doc_url: Optional[str] = None
    github_evidence_url: Optional[str] = None


# ── Repository file ───────────────────────────────────────────────────────────

class RepoFile(BaseModel):
    path: str
    content: str
    lines: List[str]
    size_bytes: int
    sha: Optional[str] = None


# ── Extracted facts ───────────────────────────────────────────────────────────

class CodeFact(BaseModel):
    kind: str            # "function", "class", "config_key", "import", "command", etc.
    name: str
    file: str
    line: int
    signature: Optional[str] = None
    params: Optional[List[str]] = None
    extra: Optional[str] = None


class DocClaim(BaseModel):
    file: str
    line: int
    text: str
    kind: str            # "function_call", "config_key", "command", "package_name", "general"
    symbol: Optional[str] = None   # extracted symbol name if detected


# ── Analysis request/response ─────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    repo_url: str
    demo_mode: bool = False


class ScanStatus(str, Enum):
    fetching = "fetching"
    parsing = "parsing"
    analyzing = "analyzing"
    complete = "complete"
    error = "error"


class AnalysisResult(BaseModel):
    repo_owner: str
    repo_name: str
    repo_url: str
    default_branch: str

    files_fetched: int
    doc_files: int
    code_files: int

    findings: List[Finding]
    total_findings: int
    severity_counts: dict

    gemma_used: bool
    demo_mode: bool
    scan_duration_seconds: float

    error: Optional[str] = None


# ── AI structured output ──────────────────────────────────────────────────────

class AIFinding(BaseModel):
    """Raw finding as returned by Gemma; validated before promoting to Finding."""
    title: str
    category: str
    severity: str
    documented_claim: str
    evidence_excerpt: Optional[str] = None
    explanation: str
    suggested_fix: Optional[str] = None
    confidence: float = 0.5
    is_genuine_issue: bool = True


class AIAnalysisResponse(BaseModel):
    findings: List[AIFinding] = []
    summary: Optional[str] = None
