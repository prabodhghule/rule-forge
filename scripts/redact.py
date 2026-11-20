#!/usr/bin/env python3
"""Mask client and sensitive information in text before it is stored or published.

Pattern-based masking for: URLs, emails, IPv4/IPv6 addresses, hostnames/domains,
UUIDs, long tokens/keys, phone numbers, card-like numbers and Aadhaar/PAN-like IDs.
Client or company names can't be detected by pattern, so callers pass them as
`extra_terms` (they are used for this run only and never written to disk).

    from redact import redact
    clean, found = redact(text, extra_terms=["Acme Corp"])
"""
from __future__ import annotations

import re
import sys

TLDS = (
    "com|in|net|org|io|co|ai|gov|edu|mil|cloud|app|dev|biz|info|us|uk|eu|au|sg|ae|de|fr|jp|"
    "local|internal|corp|lan|intra|xyz|site|online|tech|bank|insurance|finance"
)

# Order matters: URLs before hosts, emails before hosts.
PATTERNS: list[tuple[str, str, re.Pattern]] = [
    ("url", "[REDACTED_URL]", re.compile(r"\b(?:https?|ftp)://[^\s\"'<>)\]]+", re.I)),
    ("email", "[REDACTED_EMAIL]", re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")),
    ("uuid", "[REDACTED_ID]", re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)),
    ("ipv6", "[REDACTED_IP]", re.compile(r"(?<![\w:])(?:[0-9a-f]{1,4}:){3,7}(?::?[0-9a-f]{1,4})+(?![\w:])", re.I)),
    ("ipv4", "[REDACTED_IP]", re.compile(r"(?<![/\w.])(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}(?:/\d{1,2})?\b")),
    ("host", "[REDACTED_HOST]", re.compile(rf"\b(?:[a-z0-9](?:[a-z0-9-]{{0,61}}[a-z0-9])?\.)+(?:{TLDS})\b", re.I)),
    ("card", "[REDACTED_NUMBER]", re.compile(r"\b(?:\d{4}[ -]){3}\d{4}\b")),
    ("aadhaar", "[REDACTED_NUMBER]", re.compile(r"\b\d{4} \d{4} \d{4}\b")),
    ("pan", "[REDACTED_ID]", re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")),
    ("phone", "[REDACTED_PHONE]", re.compile(r"(?<![\w.])\+\d{1,3}[ -]?\d{4,5}[ -]?\d{4,6}\b|\b[6-9]\d{9}\b")),
    ("token", "[REDACTED_TOKEN]", re.compile(r"\b(?=[A-Za-z0-9+/_=-]*\d)(?=[A-Za-z0-9+/_=-]*[A-Za-z])[A-Za-z0-9+/_=-]{32,}\b")),
    ("secret", r"\1[REDACTED_SECRET]", re.compile(r"((?:password|passwd|pwd|secret|api[_-]?key|token|authorization|bearer)\"?\s*[:=]\s*\"?)[^\s\",}]+", re.I)),
]


def redact(text: str, extra_terms: list[str] | None = None) -> tuple[str, dict[str, int]]:
    """Return (masked_text, counts_by_kind)."""
    if not text:
        return text, {}
    found: dict[str, int] = {}
    for kind, repl, pat in PATTERNS:
        text, n = pat.subn(repl, text)
        if n:
            found[kind] = found.get(kind, 0) + n
    # Client names last, so they don't break URL/host masking.
    for term in sorted({t.strip() for t in (extra_terms or []) if t and t.strip()}, key=len, reverse=True):
        pat = re.compile(re.escape(term), re.I)
        text, n = pat.subn("[REDACTED_CLIENT]", text)
        if n:
            found["client"] = found.get("client", 0) + n
    return text, found


def redact_obj(obj, extra_terms=None, found=None):
    """Redact every string inside a dict/list structure. Keys are left as they are."""
    found = {} if found is None else found
    if isinstance(obj, str):
        out, f = redact(obj, extra_terms)
        for k, v in f.items():
            found[k] = found.get(k, 0) + v
        return out
    if isinstance(obj, dict):
        return {k: redact_obj(v, extra_terms, found) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact_obj(v, extra_terms, found) for v in obj]
    return obj


if __name__ == "__main__":
    # Usage: python redact.py [--term NAME ...] < input.txt
    terms, args = [], sys.argv[1:]
    while args:
        if args[0] == "--term" and len(args) > 1:
            terms.append(args[1]); args = args[2:]
        else:
            args = args[1:]
    out, found = redact(sys.stdin.read(), terms)
    sys.stdout.write(out)
    print(f"\n[redacted: {found or 'nothing'}]", file=sys.stderr)
