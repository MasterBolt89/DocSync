"""
DocSync — Demo fixture.
A bundled set of realistic findings that demonstrate detection without
requiring GitHub access or Gemma credentials.
These are clearly labeled as demo findings.
"""
from __future__ import annotations

from typing import List
from app.models.schemas import (
    Category, Finding, FindingSource, RepoFile, Severity, VerificationStatus,
)


DEMO_REPO_OWNER = "demo-org"
DEMO_REPO_NAME = "awesome-cache-lib"
DEMO_BRANCH = "main"
DEMO_REPO_URL = "https://github.com/demo-org/awesome-cache-lib"

DEMO_FILES = [
    RepoFile(
        path="README.md",
        content="""# awesome-cache-lib

A fast, lightweight caching library.

## Installation

```
pip install awesome-cachelib
```

## Quick Start

```python
from cache import CacheClient

# Initialize with config
client = CacheClient(host="localhost", port=6379, timeout=30, max_retries=3)
client.set_value("key", "value", ttl=60)
```

## Retrieving Values

```python
# Valid call matching current fetch(key) signature
val = client.fetch("my-key")
```

## Configuration

Set `CACHE_ENABLED=false` to disable caching.
Set `CACHE_MAX_SIZE=1000` to limit cache entries.

See [Configuration Guide](docs/config.md) for full options.
""",
        lines=[],
        size_bytes=480,
    ),
    RepoFile(
        path="docs/config.md",
        content="""# Configuration Guide

## Environment Variables

- `CACHE_ENABLED` — Enable or disable caching (default: true)
- `CACHE_MAX_SIZE` — Maximum number of cache entries (default: 500)
- `CACHE_TIMEOUT` — Connection timeout in seconds (default: 10)

## Advanced Settings

Set `DEBUG_CACHE=true` to enable verbose cache logging.
""",
        lines=[],
        size_bytes=300,
    ),
    RepoFile(
        path="cache/client.py",
        content="""\"\"\"Cache client implementation.\"\"\"


class CacheConnection:
    \"\"\"The main cache connection class (renamed from CacheClient).\"\"\"

    def __init__(self, host: str, port: int = 6379, timeout: int = 10):
        self.host = host
        self.port = port
        self.timeout = timeout

    def put(self, key: str, value: str, ttl: int = 300) -> bool:
        \"\"\"Store a value (renamed from set_value).\"\"\"
        pass

    def fetch(self, key: str) -> str:
        \"\"\"Retrieve a value (renamed from get_value).\"\"\"
        pass
""",
        lines=[],
        size_bytes=500,
    ),
    RepoFile(
        path="pyproject.toml",
        content="""[project]
name = "awesome-cache-library"
version = "2.0.0"

[project.scripts]
cache-cli = "cache.cli:main"
""",
        lines=[],
        size_bytes=200,
    ),
]

# Fix line data
for f in DEMO_FILES:
    f.lines = f.content.splitlines()


def get_demo_findings() -> List[Finding]:
    return [
        Finding(
            id="demo-001",
            title="Class `CacheClient` renamed to `CacheConnection`",
            category=Category.removed_symbol,
            severity=Severity.critical,
            source=FindingSource.demo,
            documentation_file="README.md",
            documentation_line=14,
            documented_claim="from cache import CacheClient",
            evidence_file="cache/client.py",
            evidence_line=4,
            evidence_excerpt="class CacheConnection:\n    \"\"\"The main cache connection class (renamed from CacheClient).\"\"\"",
            explanation=(
                "The README imports and uses `CacheClient`, but the source code now defines `CacheConnection`. "
                "This will cause an `ImportError` for anyone following the README."
            ),
            suggested_fix="Update the import to `from cache import CacheConnection` and update all usages.",
            confidence=0.98,
            verification_status=VerificationStatus.verified,
            github_doc_url=f"{DEMO_REPO_URL}/blob/{DEMO_BRANCH}/README.md#L14",
            github_evidence_url=f"{DEMO_REPO_URL}/blob/{DEMO_BRANCH}/cache/client.py#L4",
        ),
        Finding(
            id="demo-002",
            title="`CacheClient()` called with unsupported parameter `max_retries`",
            category=Category.outdated_signature,
            severity=Severity.high,
            source=FindingSource.demo,
            documentation_file="README.md",
            documentation_line=17,
            documented_claim='client = CacheClient(host="localhost", port=6379, timeout=30, max_retries=3)',
            evidence_file="cache/client.py",
            evidence_line=7,
            evidence_excerpt='def __init__(self, host: str, port: int = 6379, timeout: int = 10):',
            explanation=(
                "The README initializes the client with `max_retries=3`, but `CacheConnection.__init__` "
                "does not accept a `max_retries` parameter. This will cause a `TypeError` at runtime."
            ),
            suggested_fix='Remove `max_retries=3` from the constructor call: `CacheConnection(host="localhost", port=6379, timeout=30)`',
            confidence=0.96,
            verification_status=VerificationStatus.verified,
            github_doc_url=f"{DEMO_REPO_URL}/blob/{DEMO_BRANCH}/README.md#L17",
            github_evidence_url=f"{DEMO_REPO_URL}/blob/{DEMO_BRANCH}/cache/client.py#L7",
        ),
        Finding(
            id="demo-003",
            title="Method `set_value()` renamed to `put()`",
            category=Category.removed_symbol,
            severity=Severity.high,
            source=FindingSource.demo,
            documentation_file="README.md",
            documentation_line=18,
            documented_claim='client.set_value("key", "value", ttl=60)',
            evidence_file="cache/client.py",
            evidence_line=12,
            evidence_excerpt='def put(self, key: str, value: str, ttl: int = 300) -> bool:\n    """Store a value (renamed from set_value)."""',
            explanation=(
                "The README calls `client.set_value(...)` but the current implementation uses `put()`. "
                "The docstring explicitly notes this was renamed."
            ),
            suggested_fix='Update the example to `client.put("key", "value", ttl=60)`.',
            confidence=0.98,
            verification_status=VerificationStatus.verified,
            github_doc_url=f"{DEMO_REPO_URL}/blob/{DEMO_BRANCH}/README.md#L18",
            github_evidence_url=f"{DEMO_REPO_URL}/blob/{DEMO_BRANCH}/cache/client.py#L12",
        ),
        Finding(
            id="demo-004",
            title="Config key `CACHE_ENABLED` not found in analyzed source code",
            category=Category.config_drift,
            severity=Severity.medium,
            source=FindingSource.demo,
            documentation_file="README.md",
            documentation_line=30,
            documented_claim="Set `CACHE_ENABLED=false` to disable caching.",
            evidence_file="cache/client.py",
            evidence_line=None,
            evidence_excerpt=None,
            explanation=(
                "The README and config guide both reference `CACHE_ENABLED`, but no code in the analyzed "
                "source files reads this environment variable. It may have been removed or renamed."
            ),
            suggested_fix="Search the codebase for how caching is currently toggled and update the documentation accordingly.",
            confidence=0.75,
            verification_status=VerificationStatus.hypothesis,
            github_doc_url=f"{DEMO_REPO_URL}/blob/{DEMO_BRANCH}/README.md#L30",
        ),
        Finding(
            id="demo-005",
            title="Install command uses `awesome-cachelib` but package is `awesome-cache-library`",
            category=Category.outdated_install,
            severity=Severity.medium,
            source=FindingSource.demo,
            documentation_file="README.md",
            documentation_line=8,
            documented_claim="pip install awesome-cachelib",
            evidence_file="pyproject.toml",
            evidence_line=2,
            evidence_excerpt='name = "awesome-cache-library"',
            explanation=(
                "The README installation instructions use `pip install awesome-cachelib`, "
                "but `pyproject.toml` defines the package name as `awesome-cache-library`. "
                "These do not match."
            ),
            suggested_fix='Update the README to `pip install awesome-cache-library`.',
            confidence=0.90,
            verification_status=VerificationStatus.verified,
            github_doc_url=f"{DEMO_REPO_URL}/blob/{DEMO_BRANCH}/README.md#L8",
            github_evidence_url=f"{DEMO_REPO_URL}/blob/{DEMO_BRANCH}/pyproject.toml#L2",
        ),
        Finding(
            id="demo-006",
            title="`CACHE_MAX_SIZE` default value differs between docs",
            category=Category.conflicting_docs,
            severity=Severity.low,
            source=FindingSource.demo,
            documentation_file="docs/config.md",
            documentation_line=6,
            documented_claim="`CACHE_MAX_SIZE` — Maximum number of cache entries (default: 500)",
            evidence_file="README.md",
            evidence_line=31,
            evidence_excerpt="Set `CACHE_MAX_SIZE=1000` to limit cache entries.",
            explanation=(
                "The configuration guide states `CACHE_MAX_SIZE` defaults to 500, while the README "
                "example sets it to 1000, implying a different expectation of the default."
            ),
            suggested_fix="Decide on a canonical default and update both documents to agree.",
            confidence=0.85,
            verification_status=VerificationStatus.verified,
            github_doc_url=f"{DEMO_REPO_URL}/blob/{DEMO_BRANCH}/docs/config.md#L6",
            github_evidence_url=f"{DEMO_REPO_URL}/blob/{DEMO_BRANCH}/README.md#L31",
        ),
    ]
