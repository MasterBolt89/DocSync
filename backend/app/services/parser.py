"""
DocSync — File parsing and fact extraction.
Deterministic extraction of code facts and documentation claims.
"""
from __future__ import annotations

import ast
import json
import re
import tomllib
from pathlib import Path
from typing import List, Optional

from app.models.schemas import CodeFact, DocClaim, RepoFile


# ── Regex patterns ────────────────────────────────────────────────────────────

# Markdown / RST: code fences containing function calls
_FUNC_CALL_RE = re.compile(
    r"`{1,3}([a-zA-Z_][a-zA-Z0-9_.]*\([^`\n]{0,200}\))`{0,3}"
)
# Config key references: `KEY=value` or `KEY: value` in backticks
_CONFIG_KEY_RE = re.compile(
    r"`([A-Z][A-Z0-9_]{2,})\s*[=:]"
)
# Shell commands: $ or >>> prefix in code blocks
_COMMAND_RE = re.compile(
    r"(?:^|\n)\s*(?:\$|>>>|pip install|npm install|yarn add|python|node|npx)\s+([^\n]{4,80})"
)
# Package name from pip install
_PIP_INSTALL_RE = re.compile(r"pip\s+install\s+([a-zA-Z0-9_\-\[\],>=<!\s]+?)(?:\n|$)")
# npm/yarn install
_NPM_INSTALL_RE = re.compile(r"(?:npm install|yarn add|npx)\s+([a-zA-Z0-9_@/\-]+)")
# function name in docs
_DOC_FUNC_NAME_RE = re.compile(r"\b([a-z_][a-zA-Z0-9_]*)\s*\(")


# ── Python AST fact extraction ─────────────────────────────────────────────────

def extract_python_facts(repo_file: RepoFile) -> List[CodeFact]:
    facts: List[CodeFact] = []
    try:
        tree = ast.parse(repo_file.content, filename=repo_file.path)
    except SyntaxError:
        return facts

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            params = _extract_params(node)
            docstring = ast.get_docstring(node)
            facts.append(CodeFact(
                kind="function",
                name=node.name,
                file=repo_file.path,
                line=node.lineno,
                signature=f"{node.name}({', '.join(params)})",
                params=params,
                extra=docstring,
            ))
        elif isinstance(node, ast.ClassDef):
            init_params = None
            init_sig = None
            cls_doc = ast.get_docstring(node)
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    m_params = _extract_params(item)
                    m_doc = ast.get_docstring(item)
                    # Also register methods
                    facts.append(CodeFact(
                        kind="function",
                        name=item.name,
                        file=repo_file.path,
                        line=item.lineno,
                        signature=f"{node.name}.{item.name}({', '.join(m_params)})",
                        params=m_params,
                        extra=m_doc,
                    ))
                    if item.name == "__init__":
                        init_params = [p for p in m_params if p not in ("self", "cls")]
                        init_sig = f"{node.name}({', '.join(init_params)})"

            facts.append(CodeFact(
                kind="class",
                name=node.name,
                file=repo_file.path,
                line=node.lineno,
                signature=init_sig or f"{node.name}()",
                params=init_params,
                extra=cls_doc,
            ))
        elif isinstance(node, ast.Assign):
            # top-level string assignments that look like config keys
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    facts.append(CodeFact(
                        kind="config_key",
                        name=target.id,
                        file=repo_file.path,
                        line=node.lineno,
                    ))
        elif isinstance(node, ast.Call):
            # Detect os.getenv("KEY") or os.environ.get("KEY")
            func_name = ""
            if isinstance(node.func, ast.Attribute):
                func_name = node.func.attr
            elif isinstance(node.func, ast.Name):
                func_name = node.func.id
            if func_name in ("getenv", "get") and node.args:
                first_arg = node.args[0]
                if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                    if first_arg.value.isupper():
                        facts.append(CodeFact(
                            kind="config_key",
                            name=first_arg.value,
                            file=repo_file.path,
                            line=node.lineno,
                        ))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                facts.append(CodeFact(
                    kind="import",
                    name=alias.name,
                    file=repo_file.path,
                    line=node.lineno,
                ))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                for alias in node.names:
                    facts.append(CodeFact(
                        kind="import",
                        name=f"{node.module}.{alias.name}",
                        file=repo_file.path,
                        line=node.lineno,
                    ))

    return facts


def _extract_params(node: ast.FunctionDef) -> List[str]:
    params = []
    args = node.args
    for arg in args.posonlyargs + args.args:
        params.append(arg.arg)
    if args.vararg:
        params.append(f"*{args.vararg.arg}")
    for arg in args.kwonlyargs:
        params.append(arg.arg)
    if args.kwarg:
        params.append(f"**{args.kwarg.arg}")
    return params


# ── Config file fact extraction ───────────────────────────────────────────────

def extract_config_facts(repo_file: RepoFile) -> List[CodeFact]:
    facts: List[CodeFact] = []
    path = repo_file.path.lower()

    if path.endswith("pyproject.toml") or path.endswith(".toml"):
        facts.extend(_extract_toml_facts(repo_file))
    elif path.endswith("package.json"):
        facts.extend(_extract_package_json_facts(repo_file))
    elif path.endswith((".yaml", ".yml")):
        facts.extend(_extract_yaml_facts(repo_file))

    return facts


def _extract_toml_facts(repo_file: RepoFile) -> List[CodeFact]:
    facts: List[CodeFact] = []
    try:
        data = tomllib.loads(repo_file.content)
    except Exception:
        return facts

    # extract project name / version / dependencies
    proj = data.get("project", data.get("tool", {}).get("poetry", {}))
    if isinstance(proj, dict):
        name = proj.get("name")
        version = proj.get("version")
        if name:
            facts.append(CodeFact(kind="package_name", name=name, file=repo_file.path, line=1, extra=version))
        for dep in _flatten_deps(proj.get("dependencies", {})):
            facts.append(CodeFact(kind="dependency", name=dep, file=repo_file.path, line=1))

    # script entry points
    scripts = data.get("project", {}).get("scripts", {})
    for script_name in scripts:
        facts.append(CodeFact(kind="script", name=script_name, file=repo_file.path, line=1))

    return facts


def _flatten_deps(deps) -> List[str]:
    if isinstance(deps, list):
        return [d.split(">=")[0].split("==")[0].split("[")[0].strip() for d in deps if isinstance(d, str)]
    if isinstance(deps, dict):
        return list(deps.keys())
    return []


def _extract_package_json_facts(repo_file: RepoFile) -> List[CodeFact]:
    facts: List[CodeFact] = []
    try:
        data = json.loads(repo_file.content)
    except Exception:
        return facts

    name = data.get("name")
    if name:
        facts.append(CodeFact(kind="package_name", name=name, file=repo_file.path, line=1, extra=data.get("version")))

    for key, cmd in (data.get("scripts") or {}).items():
        facts.append(CodeFact(kind="script", name=key, file=repo_file.path, line=1, extra=cmd))

    for dep in list((data.get("dependencies") or {}).keys()) + list((data.get("devDependencies") or {}).keys()):
        facts.append(CodeFact(kind="dependency", name=dep, file=repo_file.path, line=1))

    return facts


def _extract_yaml_facts(repo_file: RepoFile) -> List[CodeFact]:
    """Simple key extraction from YAML without importing pyyaml."""
    facts: List[CodeFact] = []
    for i, line in enumerate(repo_file.lines, 1):
        m = re.match(r"^([A-Z][A-Z0-9_]{2,})\s*:", line)
        if m:
            facts.append(CodeFact(kind="config_key", name=m.group(1), file=repo_file.path, line=i))
    return facts


# ── Documentation claim extraction ───────────────────────────────────────────

def extract_doc_claims(repo_file: RepoFile) -> List[DocClaim]:
    claims: List[DocClaim] = []
    in_code_block = False
    code_block_content: List[str] = []
    code_block_start_line = 0

    for i, line in enumerate(repo_file.lines, 1):
        # detect fenced code blocks
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            if not in_code_block:
                in_code_block = True
                code_block_content = []
                code_block_start_line = i
            else:
                in_code_block = False
                _extract_code_block_claims(code_block_content, code_block_start_line, repo_file.path, claims)
            continue

        if in_code_block:
            code_block_content.append(line)
            continue

        # inline backtick function calls: `foo()` or `client.bar(...)`
        for m in _FUNC_CALL_RE.finditer(line):
            sym_match = _DOC_FUNC_NAME_RE.search(m.group(1))
            sym = sym_match.group(1) if sym_match else None
            claims.append(DocClaim(
                file=repo_file.path,
                line=i,
                text=m.group(0),
                kind="function_call",
                symbol=sym,
            ))

        # config key references in backticks: `CACHE_ENABLED` or `CACHE_MAX_SIZE=1000`
        config_pat = re.compile(r"`([A-Z][A-Z0-9_]{2,})`(?:\s*[=:\-—]|$)")
        for m in config_pat.finditer(line):
            claims.append(DocClaim(
                file=repo_file.path,
                line=i,
                text=line.strip(),
                kind="config_key",
                symbol=m.group(1),
            ))

        # also legacy KEY=value pattern in backtick
        for m in _CONFIG_KEY_RE.finditer(line):
            claims.append(DocClaim(
                file=repo_file.path,
                line=i,
                text=line.strip(),
                kind="config_key",
                symbol=m.group(1),
            ))

    return claims


def _extract_code_block_claims(lines: List[str], start_line: int, file_path: str, claims: List[DocClaim]):
    import_from_re = re.compile(r"^\s*from\s+([a-zA-Z0-9_.]+)\s+import\s+([a-zA-Z0-9_,\s]+)")
    import_re = re.compile(r"^\s*import\s+([a-zA-Z0-9_,\s]+)")
    call_re = re.compile(r"([a-zA-Z_][a-zA-Z0-9_.]*)\s*\(([^)\n]{0,300})\)")
    config_assign_re = re.compile(r"^\s*([A-Z][A-Z0-9_]{2,})\s*=")

    for offset, line in enumerate(lines, 1):
        line_num = start_line + offset
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("//"):
            continue

        # pip install commands
        for m in _PIP_INSTALL_RE.finditer(stripped):
            claims.append(DocClaim(file=file_path, line=line_num, text=m.group(0).strip(), kind="command", symbol=None))

        # npm/yarn commands
        for m in _NPM_INSTALL_RE.finditer(stripped):
            claims.append(DocClaim(file=file_path, line=line_num, text=m.group(0).strip(), kind="command", symbol=None))

        # Python imports
        m_from = import_from_re.match(stripped)
        if m_from:
            symbols = [s.strip() for s in m_from.group(2).split(",") if s.strip()]
            for sym in symbols:
                claims.append(DocClaim(
                    file=file_path,
                    line=line_num,
                    text=stripped,
                    kind="import",
                    symbol=sym,
                ))
            continue

        m_imp = import_re.match(stripped)
        if m_imp:
            symbols = [s.strip() for s in m_imp.group(1).split(",") if s.strip()]
            for sym in symbols:
                claims.append(DocClaim(
                    file=file_path,
                    line=line_num,
                    text=stripped,
                    kind="import",
                    symbol=sym,
                ))
            continue

        # config key assignments
        m_conf = config_assign_re.match(stripped)
        if m_conf:
            claims.append(DocClaim(
                file=file_path,
                line=line_num,
                text=stripped,
                kind="config_key",
                symbol=m_conf.group(1),
            ))

        # function and constructor calls
        for m in call_re.finditer(stripped):
            raw_sym = m.group(1).split(".")[-1]
            # Skip common builtins/keywords
            if raw_sym in {"print", "len", "range", "str", "int", "list", "dict", "set", "super", "if", "for", "while"}:
                continue
            claims.append(DocClaim(
                file=file_path,
                line=line_num,
                text=stripped,
                kind="function_call",
                symbol=raw_sym,
            ))


# ── JS/TS fact extraction (heuristic) ─────────────────────────────────────────

def extract_js_facts(repo_file: RepoFile) -> List[CodeFact]:
    facts: List[CodeFact] = []
    func_re = re.compile(
        r"(?:export\s+)?(?:async\s+)?function\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\(([^)]*)\)"
        r"|(?:export\s+)?const\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>"
        r"|(?:export\s+default\s+)?class\s+([a-zA-Z_$][a-zA-Z0-9_$]*)"
    )
    for i, line in enumerate(repo_file.lines, 1):
        for m in func_re.finditer(line):
            name = m.group(1) or m.group(3) or m.group(4)
            kind = "class" if m.group(4) else "function"
            if name:
                params_str = m.group(2) if m.group(2) is not None else ""
                params = [p.strip().split(":")[0].strip() for p in params_str.split(",") if p.strip()]
                facts.append(CodeFact(
                    kind=kind,
                    name=name,
                    file=repo_file.path,
                    line=i,
                    params=params if params else None,
                    signature=f"{name}({params_str})" if params_str else f"{name}()",
                ))
    return facts


# ── Dispatcher ────────────────────────────────────────────────────────────────

def extract_facts_from_file(repo_file: RepoFile) -> List[CodeFact]:
    path = repo_file.path.lower()
    if path.endswith(".py"):
        return extract_python_facts(repo_file)
    if path.endswith((".js", ".ts", ".jsx", ".tsx")):
        return extract_js_facts(repo_file)
    if path.endswith((".toml", ".json", ".yaml", ".yml", ".cfg", ".ini")):
        return extract_config_facts(repo_file)
    return []


def extract_claims_from_file(repo_file: RepoFile) -> List[DocClaim]:
    path = repo_file.path.lower()
    if path.endswith((".md", ".rst", ".txt")):
        return extract_doc_claims(repo_file)
    return []
