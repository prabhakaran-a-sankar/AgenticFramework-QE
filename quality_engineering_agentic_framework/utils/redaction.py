"""
Best-effort secret redaction for text that is about to be sent to a model
(project source in a brief, example tests, DOM snapshots, test bodies).

ON by default. Set QEAF_REDACT_SECRETS=false to disable.

This is a safety net, not a guarantee: it catches well-known token formats and
quoted/`.env`-style credential assignments. It deliberately does NOT rewrite
unquoted code such as `password = getPassword()`.
"""

import os
import re
from typing import Tuple

REDACTED = "<REDACTED>"

# (pattern, replacement). Order matters: specific formats first.
_PATTERNS = [
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
     REDACTED),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), REDACTED),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"), REDACTED),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"), REDACTED),
    (re.compile(r"\bsk-(?:ant-)?[A-Za-z0-9_\-]{20,}\b"), REDACTED),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{10,}\b"), REDACTED),
    (re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"), REDACTED),
    (re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\b"), REDACTED),
    # Authorization: Bearer <token>
    (re.compile(r"(?i)(\bbearer\s+)[A-Za-z0-9._~+/\-]{16,}=*"), r"\1" + REDACTED),
    # scheme://user:password@host
    (re.compile(r"(?i)(\b[a-z][a-z0-9+.\-]*://[^\s/:@]+:)[^\s/@]+(@)"), r"\1" + REDACTED + r"\2"),
]

_KEY_WORDS = (r"(?:password|passwd|pwd|secret|token|api[_\-]?key|access[_\-]?key|"
              r"private[_\-]?key|client[_\-]?secret|auth[_\-]?key)")

# key = "value" / key: 'value'  (quoted values, any language)
_QUOTED_ASSIGN = re.compile(
    r"(?i)(\b[\w.\-]*" + _KEY_WORDS + r"[\w.\-]*[\"']?\s*[:=]\s*)(\"[^\"\n]{4,}\"|'[^'\n]{4,}')")

# KEY=value on its own line (.env / properties / yaml) — unquoted
_ENV_LINE = re.compile(
    r"(?im)^(\s*[\w.\-]*" + _KEY_WORDS + r"[\w.\-]*\s*[:=]\s*)([^\s\"'(){}<>$][^\s\"'()]{5,})\s*$")


def redaction_enabled() -> bool:
    return os.environ.get("QEAF_REDACT_SECRETS", "true").strip().lower() not in (
        "0", "false", "no", "off")


def redact_secrets(text: str) -> Tuple[str, int]:
    """Return (redacted_text, number_of_values_redacted)."""
    if not text:
        return text, 0
    count = 0

    def sub(pattern, repl, s):
        nonlocal count
        out, n = pattern.subn(repl, s)
        count += n
        return out

    for pattern, repl in _PATTERNS:
        text = sub(pattern, repl, text)
    text = sub(_QUOTED_ASSIGN, lambda m: m.group(1) + '"' + REDACTED + '"', text)
    # Unquoted .env-style values: leave obvious non-secrets (numbers, booleans) alone.
    def _env(m):
        nonlocal count
        value = m.group(2)
        if value.isdigit() or value.lower() in ("true", "false", "null", "none"):
            return m.group(0)
        count += 1
        return m.group(1) + REDACTED

    text = _ENV_LINE.sub(_env, text)
    return text, count


def maybe_redact(text: str) -> str:
    """Redact only if enabled; drop the count. For call sites that don't report it."""
    return redact_secrets(text)[0] if redaction_enabled() else text
