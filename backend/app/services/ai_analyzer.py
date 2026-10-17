"""
DocSync — AI-powered analysis orchestrator.
Builds context-efficient prompts and promotes AI findings to validated Finding objects.
"""
from __future__ import annotations

import uuid
from typing import Dict, List, Optional

import httpx

from app.models.schemas import (
    AIFinding, Category, CodeFact, DocClaim, Finding, FindingSource,
    RepoFile, Severity, VerificationStatus,
)
from app.services.gemma_client import call_gemma

# Maximum prompt size (chars) per batch sent to Gemma
MAX_PROMPT_CHARS = 12_000


def _uid() -> str:
    return str(uuid.uuid4())[:8]


def _severity_from_str(s: str) -> Severity:
    try:
        return Severity(s.lower())
    except ValueError:
        return Severity.medium


def _category_from_str(s: str) -> Category:
    try:
        return Category(s.lower())
    except ValueError:
        return Category.unverified_claim


def _validate_ai_finding(
    ai: AIFinding,
    doc_claims: List[DocClaim],
    facts: List[CodeFact],
    repo_files: Dict[str, RepoFile],
    owner: str = "",
    repo: str = "",
    branch: str = "main",
) -> Optional[Finding]:
    """Promote an AIFinding to a validated Finding, or return None if invalid."""
    if not ai.is_genuine_issue:
        return None
    if not ai.title or not ai.explanation:
        return None
    if ai.confidence < 0.3:
        return None

    # Try to locate the claim in our doc files
    doc_file = None
    doc_line = None
    for claim in doc_claims:
        if ai.documented_claim and (ai.documented_claim[:40] in claim.text or claim.text in ai.documented_claim):
            doc_file = claim.file
            doc_line = claim.line
            break

    # If we can't locate the exact claim, check if documented_claim matches any line in doc files
    if doc_file is None:
        for path, rf in repo_files.items():
            if path.endswith((".md", ".rst", ".txt")):
                for idx, line in enumerate(rf.lines, 1):
                    if ai.documented_claim and ai.documented_claim.strip() in line:
                        doc_file = path
                        doc_line = idx
                        break
            if doc_file:
                break

    # If still not found, use first doc file if available
    if doc_file is None and doc_claims:
        doc_file = doc_claims[0].file
        doc_line = doc_claims[0].line

    if doc_file is None or doc_file not in repo_files:
        return None

    # Validate doc line bounds
    rf_doc = repo_files[doc_file]
    if doc_line is not None and (doc_line < 1 or doc_line > len(rf_doc.lines)):
        doc_line = None

    # Try to locate evidence in code facts or repository files
    ev_file = None
    ev_line = None
    ev_excerpt = None
    status = VerificationStatus.hypothesis

    if ai.evidence_excerpt:
        for fact in facts:
            if ai.evidence_excerpt[:30] in (fact.signature or fact.name):
                ev_file = fact.file
                ev_line = fact.line
                rf = repo_files.get(fact.file)
                if rf and fact.line and 1 <= fact.line <= len(rf.lines):
                    idx = fact.line - 1
                    ev_excerpt = "\n".join(rf.lines[max(0, idx - 1):min(len(rf.lines), idx + 3)])
                    status = VerificationStatus.verified
                break

        # Check if excerpt matches code lines directly
        if ev_file is None:
            for path, rf in repo_files.items():
                if path.endswith((".py", ".js", ".ts", ".toml", ".json")):
                    for idx, line in enumerate(rf.lines, 1):
                        if ai.evidence_excerpt[:30] in line:
                            ev_file = path
                            ev_line = idx
                            ev_excerpt = "\n".join(rf.lines[max(0, idx - 2):min(len(rf.lines), idx + 2)])
                            status = VerificationStatus.plausible
                            break
                if ev_file:
                    break

    # Build GitHub URLs if owner/repo provided
    github_doc_url = None
    github_evidence_url = None
    if owner and repo:
        github_doc_url = f"https://github.com/{owner}/{repo}/blob/{branch}/{doc_file}"
        if doc_line:
            github_doc_url += f"#L{doc_line}"
        if ev_file:
            github_evidence_url = f"https://github.com/{owner}/{repo}/blob/{branch}/{ev_file}"
            if ev_line:
                github_evidence_url += f"#L{ev_line}"

    return Finding(
        id=_uid(),
        title=ai.title,
        category=_category_from_str(ai.category),
        severity=_severity_from_str(ai.severity),
        source=FindingSource.ai,
        documentation_file=doc_file,
        documentation_line=doc_line,
        documented_claim=ai.documented_claim or "",
        evidence_file=ev_file,
        evidence_line=ev_line,
        evidence_excerpt=ev_excerpt or ai.evidence_excerpt,
        explanation=ai.explanation,
        suggested_fix=ai.suggested_fix,
        confidence=min(max(ai.confidence, 0.0), 1.0),
        verification_status=status,
        github_doc_url=github_doc_url,
        github_evidence_url=github_evidence_url,
    )


def _build_analysis_prompt(
    doc_claims: List[DocClaim],
    facts: List[CodeFact],
    repo_files: Dict[str, RepoFile],
) -> str:
    """Build a focused, size-bounded prompt for Gemma."""
    lines = [
        "## Documentation Claims\n",
        "These are claims extracted from the project's documentation:\n",
    ]

    for claim in doc_claims[:40]:
        lines.append(f"- [{claim.file}:{claim.line}] ({claim.kind}): {claim.text[:200]}")

    lines.append("\n## Code Facts\n")
    lines.append("These are facts extracted from the project's source code:\n")

    for fact in facts[:60]:
        if fact.kind == "function":
            lines.append(f"- FUNCTION: `{fact.signature or fact.name}` in {fact.file}:{fact.line}")
        elif fact.kind == "config_key":
            lines.append(f"- CONFIG_KEY: `{fact.name}` in {fact.file}:{fact.line}")
        elif fact.kind == "package_name":
            lines.append(f"- PACKAGE: `{fact.name}` (version: {fact.extra or 'unknown'})")
        elif fact.kind == "script":
            lines.append(f"- SCRIPT: `{fact.name}`: {fact.extra or ''}")
        elif fact.kind == "class":
            lines.append(f"- CLASS: `{fact.name}` in {fact.file}:{fact.line}")

    lines.append("\n## Relevant Source Excerpts\n")

    # Add relevant source file content (truncated)
    added_chars = sum(len(l) for l in lines)
    for path, rf in repo_files.items():
        if not path.endswith(".py") and not path.endswith((".ts", ".js")):
            continue
        if added_chars >= MAX_PROMPT_CHARS:
            break
        excerpt = "\n".join(rf.lines[:50])
        if added_chars + len(excerpt) < MAX_PROMPT_CHARS:
            lines.append(f"\n### {path}\n```\n{excerpt}\n```")
            added_chars += len(excerpt)

    lines.append("\n## Task\n")
    lines.append(
        "Analyze the documentation claims against the code facts and excerpts. "
        "Identify genuine inconsistencies where documentation appears outdated, incorrect, or misleading. "
        "Focus on: renamed functions/parameters, removed config keys, incorrect installation commands, and impossible code examples."
    )

    return "\n".join(lines)


async def run_ai_analysis(
    doc_claims: List[DocClaim],
    facts: List[CodeFact],
    repo_files: Dict[str, RepoFile],
    client: httpx.AsyncClient,
    owner: str = "",
    repo: str = "",
    branch: str = "main",
) -> List[Finding]:
    """Run Gemma analysis and return validated findings."""
    if not doc_claims or not facts:
        return []

    prompt = _build_analysis_prompt(doc_claims, facts, repo_files)
    response = await call_gemma(prompt, client)

    if response is None:
        return []

    findings: List[Finding] = []
    for ai_finding in response.findings:
        validated = _validate_ai_finding(
            ai_finding, doc_claims, facts, repo_files,
            owner=owner, repo=repo, branch=branch,
        )
        if validated:
            findings.append(validated)

    return findings
