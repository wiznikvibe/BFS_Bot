from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any


PII_FIELD_PLACEHOLDERS = {
    "business_name": "[BUSINESS_NAME]",
    "contact_name": "[CONTACT_NAME]",
    "owner_name": "[CONTACT_NAME]",
    "email": "[EMAIL]",
    "phone": "[PHONE]",
    "mobile": "[PHONE]",
    "pan": "[PAN]",
    "gstin": "[GSTIN]",
    "registered_address": "[ADDRESS]",
    "address": "[ADDRESS]",
}

PII_PATTERNS = {
    "email": (re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I), "[EMAIL]"),
    "phone": (re.compile(r"(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}\b"), "[PHONE]"),
    "pan": (re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"), "[PAN]"),
    "gstin": (re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b"), "[GSTIN]"),
}


@dataclass(frozen=True)
class RedactionReport:
    status: str
    redacted_fields: list[str] = field(default_factory=list)
    pattern_replacements: dict[str, int] = field(default_factory=dict)
    residual_findings: list[str] = field(default_factory=list)


def redact_customer_record(record: dict[str, Any]) -> tuple[dict[str, Any], RedactionReport]:
    """Redact known PII fields and PII-looking substrings from a customer record."""
    redacted: dict[str, Any] = {}
    redacted_fields: list[str] = []
    pattern_replacements = {name: 0 for name in PII_PATTERNS}

    for field_name, value in record.items():
        normalized = field_name.lower()
        if normalized in PII_FIELD_PLACEHOLDERS and value not in (None, ""):
            redacted[field_name] = PII_FIELD_PLACEHOLDERS[normalized]
            redacted_fields.append(field_name)
            continue

        if isinstance(value, str):
            redacted_value = value
            for pattern_name, (pattern, placeholder) in PII_PATTERNS.items():
                redacted_value, count = pattern.subn(placeholder, redacted_value)
                pattern_replacements[pattern_name] += count
            redacted[field_name] = redacted_value
        else:
            redacted[field_name] = value

    residual_findings = find_pii_like_values(redacted)
    status = "passed" if not residual_findings else "failed"
    return redacted, RedactionReport(
        status=status,
        redacted_fields=redacted_fields,
        pattern_replacements={key: count for key, count in pattern_replacements.items() if count},
        residual_findings=residual_findings,
    )


def find_pii_like_values(record: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    for field_name, value in record.items():
        if not isinstance(value, str):
            continue
        for pattern_name, (pattern, _placeholder) in PII_PATTERNS.items():
            if pattern.search(value):
                findings.append(f"{field_name}:{pattern_name}")
    return findings

