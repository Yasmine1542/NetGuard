"""Redact common secret shapes from evidence text before it leaves the cluster
to the (third-party) LLM.

This is a best-effort, pattern-based mitigation — a *documented* control, not a
guarantee. It covers the shapes most likely to leak from pod logs: auth headers,
bearer/API tokens, cloud keys, connection-string passwords, key=value secrets,
and email addresses. IPs are intentionally kept (they are operationally relevant
to a network-security tool and not PII on their own).
"""

import re

_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Authorization: Bearer <token>  /  bearer <token>
    (re.compile(r"(?i)(authorization\s*:\s*)(bearer\s+)?\S+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]+"), "bearer [REDACTED]"),
    # Provider token prefixes: gsk_, sk-, ghp_, github_pat_, xoxb-...
    (re.compile(r"\b(?:gsk|sk|ghp|github_pat|xox[baprs])[_\-][A-Za-z0-9_\-]{8,}"), "[REDACTED_TOKEN]"),
    # AWS access key id
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED_AWS_KEY]"),
    # scheme://user:password@host  -> hide the password
    (re.compile(r"(?i)\b([a-z][a-z0-9+.\-]*://[^:/\s]+:)[^@/\s]+(@)"), r"\1[REDACTED]\2"),
    # key = value / key: value for sensitive keys
    (re.compile(r"(?i)(password|passwd|pwd|secret|token|api[_-]?key)(\"?\s*[:=]\s*\"?)[^\s\"',;]+"),
     r"\1\2[REDACTED]"),
    # email addresses
    (re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"), "[REDACTED_EMAIL]"),
]


def redact(text: str) -> str:
    if not text:
        return text
    for pattern, repl in _PATTERNS:
        text = pattern.sub(repl, text)
    return text


def redact_lines(lines: list[str]) -> list[str]:
    return [redact(line) for line in lines]
