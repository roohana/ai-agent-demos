"""Small data-leak-prevention guard applied to prompts BEFORE they leave the app.

It is a safety net, not a replacement for policy: it catches obvious secrets and personal data patterns.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

PATTERNS = {
    "email": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    "credit_card": re.compile(r"\b(?:\d[ -]?){13,19}\b"),
    "cnic": re.compile(r"\b\d{5}-\d{7}-\d\b"),
    "iban": re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b"),
    "api_key": re.compile(r"\b(?:sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{30,}|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})\b"),
    "password_assignment": re.compile(r"(?i)\b(?:password|passwd|pwd|secret)\s*[:=]\s*\S+"),
}


def _luhn(number: str) -> bool:
    digits = [int(c) for c in re.sub(r"\D", "", number)]
    if not 13 <= len(digits) <= 19:
        return False
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d = d * 2 - 9 if d * 2 > 9 else d * 2
        total += d
    return total % 10 == 0


@dataclass
class Scan:
    findings: list[str]
    redacted: str


def scan(text: str) -> Scan:
    findings: list[str] = []
    redacted = text
    for name, rx in PATTERNS.items():
        def repl(m, name=name):
            if name == "credit_card" and not _luhn(m.group(0)):
                return m.group(0)
            if name not in findings:
                findings.append(name)
            return f"[REDACTED:{name}]"
        redacted = rx.sub(repl, redacted)
    return Scan(findings, redacted)
