"""
Cheap, best-effort post-generation validation & formatting for generated code.

Goals:
  - Catch the obvious "looks right but won't run" cases (syntax errors).
  - Auto-format with whatever formatter is already installed (black / prettier /
    google-java-format) so output matches common conventions.

Principles:
  - NEVER raise and never block generation — every check degrades to "skipped".
  - Only run external tools that are actually on PATH.
  - Validation is per-file, keyed off the file extension, so no language needs
    to be passed in.
"""

import os
import re
import shutil
import subprocess
from typing import Dict, List, Tuple, Optional

from quality_engineering_agentic_framework.utils.logger import get_logger

logger = get_logger(__name__)

_TIMEOUT = 20  # seconds per external formatter call


def _have(binary: str) -> bool:
    return shutil.which(binary) is not None


def _run_stdin_formatter(cmd: List[str], code: str) -> Tuple[Optional[str], str]:
    """Run a formatter that reads source on stdin and writes formatted source to
    stdout. Returns (formatted_code_or_None, message)."""
    try:
        proc = subprocess.run(
            cmd, input=code, capture_output=True, text=True, timeout=_TIMEOUT
        )
    except Exception as e:
        return None, f"formatter error: {e}"
    if proc.returncode == 0 and proc.stdout:
        return proc.stdout, "formatted"
    # Non-zero usually means a parse error — surface the first stderr line.
    err = (proc.stderr or "").strip().splitlines()
    return None, f"format/parse failed: {err[0] if err else 'unknown error'}"


def _check_balanced(code: str) -> Optional[str]:
    """Naive bracket-balance heuristic (ignores strings/comments). Returns an
    issue message or None. Only a hint, never authoritative."""
    pairs = {")": "(", "]": "[", "}": "{"}
    opens = set(pairs.values())
    stack = []
    for ch in code:
        if ch in opens:
            stack.append(ch)
        elif ch in pairs:
            if not stack or stack[-1] != pairs[ch]:
                return f"unbalanced '{ch}'"
            stack.pop()
    if stack:
        return f"unclosed '{stack[-1]}'"
    return None


def _validate_python(code: str, path: str) -> Tuple[str, List[str]]:
    checks = []
    # In-process syntax check — no dependency required.
    try:
        compile(code, path, "exec")
        checks.append("syntax: ok")
    except SyntaxError as e:
        return code, [f"syntax: ERROR (line {e.lineno}: {e.msg})"]
    # Optional auto-format with black if installed.
    if _have("black"):
        formatted, msg = _run_stdin_formatter(["black", "-q", "-"], code)
        if formatted is not None:
            code = formatted
            checks.append("black: formatted")
        else:
            checks.append(f"black: {msg}")
    else:
        checks.append("black: skipped (not installed)")
    return code, checks


def _validate_js_ts(code: str, path: str) -> Tuple[str, List[str]]:
    checks = []
    if _have("prettier"):
        # prettier parses AND formats; a parse error makes it exit non-zero.
        formatted, msg = _run_stdin_formatter(
            ["prettier", "--stdin-filepath", os.path.basename(path)], code
        )
        if formatted is not None:
            code = formatted
            checks.append("prettier: formatted (syntax ok)")
        else:
            checks.append(f"prettier: {msg}")
    else:
        checks.append("prettier: skipped (not installed)")
        bal = _check_balanced(code)
        checks.append(f"brackets: {bal}" if bal else "brackets: ok")
    return code, checks


def _validate_java(code: str, path: str) -> Tuple[str, List[str]]:
    checks = []
    if _have("google-java-format"):
        formatted, msg = _run_stdin_formatter(["google-java-format", "-"], code)
        if formatted is not None:
            code = formatted
            checks.append("google-java-format: formatted")
        else:
            checks.append(f"google-java-format: {msg}")
    else:
        checks.append("google-java-format: skipped (not installed)")
    bal = _check_balanced(code)
    checks.append(f"brackets: {bal}" if bal else "brackets: ok")
    return code, checks


def _validate_generic(code: str, path: str) -> Tuple[str, List[str]]:
    bal = _check_balanced(code)
    return code, [f"brackets: {bal}" if bal else "brackets: ok"]


def _validate_gherkin(code: str, path: str) -> Tuple[str, List[str]]:
    """Structural checks for a .feature file. Only unambiguous problems are hard failures:
    no `Feature:`, a `Scenario Outline` without `Examples`, or a table whose rows have
    different column counts. (Free-text descriptions are legal Gherkin, so unknown lines
    are not errors.)"""
    lines = code.splitlines()
    if not any(re.match(r"\s*Feature:", ln) for ln in lines):
        return code, ["syntax: ERROR (line 1: missing a 'Feature:' line)"]

    outline_line, has_examples, in_doc = None, False, False
    table_cols, table_start = None, 0

    def close_outline(at: int):
        nonlocal outline_line, has_examples
        problem = None
        if outline_line is not None and not has_examples:
            problem = f"syntax: ERROR (line {outline_line}: 'Scenario Outline' has no 'Examples:')"
        outline_line, has_examples = None, False
        return problem

    for n, raw in enumerate(lines, 1):
        s = raw.strip()
        if s.startswith('"""') or s.startswith("```"):
            in_doc = not in_doc
            continue
        if in_doc:
            continue
        if s.startswith("|"):
            cols = len(re.findall(r"(?<!\\)\|", s)) - 1
            if table_cols is None:
                table_cols, table_start = cols, n
            elif cols != table_cols:
                return code, [f"syntax: ERROR (line {n}: table row has {cols} columns, "
                              f"the table starting at line {table_start} has {table_cols})"]
            continue
        table_cols = None
        if re.match(r"(Scenario Outline|Scenario Template)\s*:", s):
            problem = close_outline(n)
            if problem:
                return code, [problem]
            outline_line = n
        elif re.match(r"(Scenario|Example)\s*:", s) or re.match(r"(Rule|Background)\s*:", s):
            problem = close_outline(n)
            if problem:
                return code, [problem]
        elif re.match(r"(Examples|Scenarios)\s*:", s):
            has_examples = True
    problem = close_outline(len(lines))
    if problem:
        return code, [problem]
    return code, ["syntax: ok (gherkin structure)"]


_DISPATCH = {
    ".feature": _validate_gherkin,
    ".py": _validate_python,
    ".js": _validate_js_ts,
    ".jsx": _validate_js_ts,
    ".ts": _validate_js_ts,
    ".tsx": _validate_js_ts,
    ".java": _validate_java,
}


# A check string indicates a HARD failure (won't load) — used by self-heal.
_FAILURE_TOKENS = ("syntax: error", "parse failed")


def _entry_ok(checks: List[str]) -> bool:
    return not any(
        any(tok in c.lower() for tok in _FAILURE_TOKENS) for c in checks
    )


def failure_reason(entry: Dict) -> str:
    """Return the first hard-failure message for a report entry, or ''."""
    for c in entry.get("checks", []):
        if any(tok in c.lower() for tok in _FAILURE_TOKENS):
            return c
    return ""


def validate_and_format(files: Dict[str, str]) -> Tuple[Dict[str, str], List[Dict]]:
    """
    Validate & (where possible) auto-format each generated file.

    Returns (possibly_reformatted_files, report) where each report entry is
    {"file": path, "checks": [str, ...], "ok": bool}. ok=False means the file
    has a hard load-time failure (syntax/parse) the self-heal loop should fix.
    """
    out_files: Dict[str, str] = {}
    report: List[Dict] = []
    for path, code in files.items():
        ext = os.path.splitext(path)[1].lower()
        validator = _DISPATCH.get(ext, _validate_generic)
        try:
            new_code, checks = validator(code, path)
        except Exception as e:
            new_code, checks = code, [f"validation error (skipped): {e}"]
        out_files[path] = new_code
        report.append({"file": path, "checks": checks, "ok": _entry_ok(checks)})
    return out_files, report
