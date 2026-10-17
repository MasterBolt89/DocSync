"""
DocSync — Main analysis orchestrator.
Coordinates GitHub fetching, parsing, deterministic checks, and AI analysis.
"""
from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional

import httpx

from app.core.config import get_settings
from app.models.schemas import (
    AnalysisResult, CodeFact, DocClaim, Finding, FindingSource,
    RepoFile, Severity, VerificationStatus,
)
from app.services.ai_analyzer import run_ai_analysis
from app.services.checker import run_deterministic_checks
from app.services.demo import (
    DEMO_BRANCH, DEMO_FILES, DEMO_REPO_NAME, DEMO_REPO_OWNER,
    DEMO_REPO_URL, get_demo_findings,
)
from app.services.github_client import (
    fetch_repo_meta, fetch_repository_files, make_github_file_url, parse_github_url,
)
from app.services.parser import extract_claims_from_file, extract_facts_from_file

logger = logging.getLogger(__name__)


def _count_by_severity(findings: List[Finding]) -> Dict[str, int]:
    counts: Dict[str, int] = {s.value: 0 for s in Severity}
    for f in findings:
        counts[f.severity.value] = counts.get(f.severity.value, 0) + 1
    return counts


async def run_demo_analysis() -> AnalysisResult:
    """Return demo results without network access."""
    start = time.time()
    all_files = DEMO_FILES
    findings = get_demo_findings()
    duration = time.time() - start

    return AnalysisResult(
        repo_owner=DEMO_REPO_OWNER,
        repo_name=DEMO_REPO_NAME,
        repo_url=DEMO_REPO_URL,
        default_branch=DEMO_BRANCH,
        files_fetched=len(all_files),
        doc_files=sum(1 for f in all_files if f.path.endswith((".md", ".rst", ".txt"))),
        code_files=sum(1 for f in all_files if f.path.endswith((".py", ".js", ".ts"))),
        findings=findings,
        total_findings=len(findings),
        severity_counts=_count_by_severity(findings),
        gemma_used=False,
        demo_mode=True,
        scan_duration_seconds=round(duration, 2),
    )


async def run_full_analysis(repo_url: str) -> AnalysisResult:
    """Full analysis pipeline for a real GitHub repository."""
    settings = get_settings()
    start = time.time()

    try:
        owner, repo_name = parse_github_url(repo_url)
    except ValueError as e:
        return AnalysisResult(
            repo_owner="", repo_name="", repo_url=repo_url, default_branch="main",
            files_fetched=0, doc_files=0, code_files=0,
            findings=[], total_findings=0, severity_counts={},
            gemma_used=False, demo_mode=False,
            scan_duration_seconds=0,
            error=str(e),
        )

    async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
        try:
            meta = await fetch_repo_meta(owner, repo_name, client)
        except (ValueError, PermissionError) as e:
            return AnalysisResult(
                repo_owner=owner, repo_name=repo_name, repo_url=repo_url, default_branch="main",
                files_fetched=0, doc_files=0, code_files=0,
                findings=[], total_findings=0, severity_counts={},
                gemma_used=False, demo_mode=False,
                scan_duration_seconds=round(time.time() - start, 2),
                error=str(e),
            )

        default_branch = meta.get("default_branch", "main")
        canonical_url = meta.get("html_url", repo_url)

        # Fetch files
        try:
            all_files = await fetch_repository_files(owner, repo_name, default_branch, client)
        except Exception as e:
            logger.error("Failed to fetch repository files: %s", e)
            return AnalysisResult(
                repo_owner=owner, repo_name=repo_name, repo_url=canonical_url, default_branch=default_branch,
                files_fetched=0, doc_files=0, code_files=0,
                findings=[], total_findings=0, severity_counts={},
                gemma_used=False, demo_mode=False,
                scan_duration_seconds=round(time.time() - start, 2),
                error=f"Failed to fetch repository files: {e}",
            )

        doc_files = [f for f in all_files if f.path.lower().endswith((".md", ".rst", ".txt"))]
        code_files = [f for f in all_files if f.path.lower().endswith((".py", ".js", ".ts", ".jsx", ".tsx"))]
        config_files = [f for f in all_files if f.path.lower().endswith((".toml", ".json", ".yaml", ".yml", ".cfg"))]

        # Extract facts and claims
        all_facts: List[CodeFact] = []
        for f in code_files + config_files:
            all_facts.extend(extract_facts_from_file(f))

        all_claims: List[DocClaim] = []
        for f in doc_files:
            all_claims.extend(extract_claims_from_file(f))

        logger.info("Extracted %d facts and %d claims", len(all_facts), len(all_claims))

        # Deterministic checks
        deterministic_findings = run_deterministic_checks(
            doc_files=doc_files,
            all_files=all_files,
            claims=all_claims,
            facts=all_facts,
            owner=owner,
            repo=repo_name,
            branch=default_branch,
        )

        # AI analysis
        gemma_used = False
        ai_findings: List[Finding] = []

        if settings.gemma_configured and all_claims and all_facts:
            repo_files_dict = {f.path: f for f in all_files}
            ai_findings = await run_ai_analysis(
                all_claims, all_facts, repo_files_dict, client,
                owner=owner, repo=repo_name, branch=default_branch,
            )
            if ai_findings:
                gemma_used = True
                logger.info("Gemma returned %d findings", len(ai_findings))

        # Merge, deduplicate, and validate against repository files
        all_findings = deterministic_findings + ai_findings
        all_findings = _deduplicate_cross_source(all_findings)
        repo_files_dict = {f.path: f for f in all_files}
        all_findings = _validate_and_sanitize_findings(
            all_findings, repo_files_dict, owner, repo_name, default_branch
        )

        duration = time.time() - start

        return AnalysisResult(
            repo_owner=owner,
            repo_name=repo_name,
            repo_url=canonical_url,
            default_branch=default_branch,
            files_fetched=len(all_files),
            doc_files=len(doc_files),
            code_files=len(code_files),
            findings=all_findings,
            total_findings=len(all_findings),
            severity_counts=_count_by_severity(all_findings),
            gemma_used=gemma_used,
            demo_mode=False,
            scan_duration_seconds=round(duration, 2),
        )


def _validate_and_sanitize_findings(
    findings: List[Finding],
    repo_files: Dict[str, RepoFile],
    owner: str,
    repo: str,
    branch: str,
) -> List[Finding]:
    """Validate all finding file references and line numbers against the repository."""
    valid: List[Finding] = []
    for f in findings:
        # 1. Must reference an existing documentation file in the repository
        doc_file = repo_files.get(f.documentation_file)
        if not doc_file:
            continue

        # 2. Check documentation line bounds
        if f.documentation_line is not None:
            if f.documentation_line < 1 or f.documentation_line > len(doc_file.lines):
                f.documentation_line = None

        # 3. Check evidence file bounds
        if f.evidence_file:
            ev_file = repo_files.get(f.evidence_file)
            if not ev_file:
                f.evidence_file = None
                f.evidence_line = None
                f.evidence_excerpt = None
            elif f.evidence_line is not None:
                if f.evidence_line < 1 or f.evidence_line > len(ev_file.lines):
                    f.evidence_line = None

        # 4. Generate GitHub URLs
        if not f.github_doc_url and f.documentation_file:
            f.github_doc_url = make_github_file_url(owner, repo, f.documentation_file, branch, f.documentation_line)
        if not f.github_evidence_url and f.evidence_file:
            f.github_evidence_url = make_github_file_url(owner, repo, f.evidence_file, branch, f.evidence_line)

        # 5. Determine verification status
        if f.evidence_file and f.evidence_excerpt and f.evidence_line:
            f.verification_status = VerificationStatus.verified
        elif f.source == FindingSource.deterministic:
            f.verification_status = VerificationStatus.plausible

        valid.append(f)

    return valid


def _deduplicate_cross_source(findings: List[Finding]) -> List[Finding]:
    """Remove AI findings that duplicate deterministic ones."""
    det_keys = {
        (f.category, f.documentation_file, (f.documentation_line or 0))
        for f in findings
        if f.source == FindingSource.deterministic
    }
    result = []
    for f in findings:
        if f.source == FindingSource.ai:
            key = (f.category, f.documentation_file, (f.documentation_line or 0))
            if key in det_keys:
                continue
        result.append(f)
    return result
