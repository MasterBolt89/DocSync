"""
DocSync — GitHub REST API client.
Fetches repository metadata and files without requiring authentication
(public repos). Uses token if provided to raise rate limits.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

import httpx

from app.core.config import get_settings
from app.models.schemas import RepoFile

# Directories to always skip
SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "env",
    "dist", "build", ".next", ".nuxt", "coverage", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "site-packages", "eggs", ".eggs",
    "htmlcov", "target", ".gradle", "vendor", ".terraform",
}

# Extensions we care about
WANTED_EXTENSIONS = {
    ".md", ".rst", ".txt",          # docs
    ".py",                           # Python
    ".js", ".ts", ".jsx", ".tsx",   # JS/TS
    ".json", ".toml", ".yaml", ".yml", ".cfg", ".ini",  # config
}

GITHUB_API = "https://api.github.com"


def parse_github_url(url: str) -> Tuple[str, str]:
    """Extract (owner, repo) from a GitHub URL or owner/repo shorthand. Raises ValueError on failure."""
    url = url.strip().rstrip("/")
    # handle git clone URLs
    url = re.sub(r"\.git$", "", url)
    # strip /tree/branch or /blob/branch if user pasted a subpath
    url = re.sub(r"/(?:tree|blob)/.*$", "", url)

    # Standard github.com URL
    m = re.search(r"github\.com[:/]([^/]+)/([^/]+)", url)
    if m:
        return m.group(1), m.group(2)

    # Shorthand: owner/repo
    m2 = re.match(r"^([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)$", url)
    if m2:
        return m2.group(1), m2.group(2)

    raise ValueError(f"Cannot parse GitHub URL: {url!r}. Expected https://github.com/owner/repo or owner/repo")


def _headers() -> Dict[str, str]:
    settings = get_settings()
    h: Dict[str, str] = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if settings.github_token:
        h["Authorization"] = f"Bearer {settings.github_token}"
    return h


async def fetch_repo_meta(owner: str, repo: str, client: httpx.AsyncClient) -> dict:
    """Return repository metadata dict from GitHub API."""
    r = await client.get(f"{GITHUB_API}/repos/{owner}/{repo}", headers=_headers())
    if r.status_code == 404:
        raise ValueError(f"Repository {owner}/{repo} not found or is private.")
    if r.status_code == 403:
        raise PermissionError(
            "GitHub API rate limit exceeded (60 req/hr unauthenticated). "
            "Set GITHUB_TOKEN in backend/.env to increase limit to 5,000 req/hr."
        )
    r.raise_for_status()
    return r.json()


async def _fetch_tree(owner: str, repo: str, sha: str, client: httpx.AsyncClient) -> List[dict]:
    """Fetch the flat recursive tree for a commit/branch."""
    r = await client.get(
        f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{sha}",
        params={"recursive": "1"},
        headers=_headers(),
    )
    r.raise_for_status()
    data = r.json()
    return data.get("tree", [])


def _should_include(path: str) -> bool:
    """Return True if the file path should be downloaded."""
    parts = path.split("/")
    # skip if any segment is a blacklisted dir
    for part in parts[:-1]:
        if part in SKIP_DIRS or part.startswith("."):
            return False
    ext = "." + path.rsplit(".", 1)[-1] if "." in path.split("/")[-1] else ""
    return ext.lower() in WANTED_EXTENSIONS


async def _fetch_file(
    owner: str,
    repo: str,
    branch: str,
    path: str,
    sha: Optional[str],
    client: httpx.AsyncClient,
) -> Optional[bytes]:
    """Fetch raw file content with fast direct access and GitHub API fallback."""
    # 1. Fast direct raw fetch
    url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
    try:
        r = await client.get(url, timeout=15.0)
        if r.status_code == 200:
            return r.content
    except Exception:
        pass

    # 2. Fallback via git blobs API
    if sha:
        try:
            h = _headers()
            h["Accept"] = "application/vnd.github.raw"
            r2 = await client.get(f"{GITHUB_API}/repos/{owner}/{repo}/git/blobs/{sha}", headers=h, timeout=15.0)
            if r2.status_code == 200:
                return r2.content
        except Exception:
            pass

    return None


async def fetch_repository_files(
    owner: str,
    repo: str,
    default_branch: str,
    client: httpx.AsyncClient,
) -> List[RepoFile]:
    """Download relevant repository files and return as RepoFile objects."""
    settings = get_settings()
    tree = await _fetch_tree(owner, repo, default_branch, client)

    # filter and sort: docs first, then config, then code
    candidates = [item for item in tree if item.get("type") == "blob" and _should_include(item["path"])]

    def sort_key(item: dict) -> int:
        p = item["path"].lower()
        if p.endswith(".md") or p.endswith(".rst"):
            return 0
        if any(p.endswith(e) for e in (".toml", ".json", ".yaml", ".yml", ".cfg", ".ini")):
            return 1
        return 2

    candidates.sort(key=sort_key)

    # apply size pre-filter using tree blob size
    candidates = [c for c in candidates if int(c.get("size", 0)) <= settings.max_file_size_bytes]
    candidates = candidates[: settings.max_files]

    files: List[RepoFile] = []
    total_bytes = 0

    for item in candidates:
        if total_bytes >= settings.max_total_bytes:
            break
        content_bytes = await _fetch_file(
            owner=owner,
            repo=repo,
            branch=default_branch,
            path=item["path"],
            sha=item.get("sha"),
            client=client,
        )
        if content_bytes is None:
            continue
        if len(content_bytes) + total_bytes > settings.max_total_bytes:
            continue
        try:
            text = content_bytes.decode("utf-8", errors="replace")
        except Exception:
            continue
        lines = text.splitlines()
        total_bytes += len(content_bytes)
        files.append(RepoFile(
            path=item["path"],
            content=text,
            lines=lines,
            size_bytes=len(content_bytes),
            sha=item.get("sha"),
        ))

    return files


def make_github_file_url(owner: str, repo: str, path: str, branch: str, line: Optional[int] = None) -> str:
    url = f"https://github.com/{owner}/{repo}/blob/{branch}/{path}"
    if line:
        url += f"#L{line}"
    return url
