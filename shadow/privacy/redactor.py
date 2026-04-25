"""Privacy-preserving redaction for captured events.

Detects and redacts sensitive information like emails, phone numbers, SSNs,
credit card numbers, and IP addresses. Can be configured per-app with regex
allow/deny lists for titles and URLs.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..storage import Database, Event


@dataclass
class PrivacyPolicy:
    """Policy for which fields to redact in an app's events."""

    app_name: str  # "*" for all apps, specific app name otherwise
    redact_titles: bool = False
    redact_urls: bool = False
    allowed_title_patterns: list[str] = field(default_factory=list)
    blocked_title_patterns: list[str] = field(default_factory=list)


class Redactor:
    """Applies privacy policies to events, redacting sensitive values."""

    # Regex patterns for detecting sensitive information
    EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
    PHONE_PATTERN = re.compile(r"\b(?:\+1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b")
    SSN_PATTERN = re.compile(r"\b[0-9]{3}-[0-9]{2}-[0-9]{4}\b")
    CC_PATTERN = re.compile(r"\b[0-9]{4}[- ]?[0-9]{4}[- ]?[0-9]{4}[- ]?[0-9]{4}\b")
    IP_PATTERN = re.compile(
        r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}"
        r"(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
    )

    def __init__(self, policies: list[PrivacyPolicy]):
        """Initialize with a list of privacy policies."""
        self.policies = policies
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Pre-compile regex patterns from policy strings."""
        self.compiled_allowed: dict[str, list] = {}
        self.compiled_blocked: dict[str, list] = {}
        for policy in self.policies:
            self.compiled_allowed[policy.app_name] = [
                re.compile(p) for p in policy.allowed_title_patterns
            ]
            self.compiled_blocked[policy.app_name] = [
                re.compile(p) for p in policy.blocked_title_patterns
            ]

    def _get_policy(self, app_name: Optional[str]) -> Optional[PrivacyPolicy]:
        """Get the policy for an app, with fallback to '*' policy."""
        if app_name:
            for p in self.policies:
                if p.app_name == app_name:
                    return p
        for p in self.policies:
            if p.app_name == "*":
                return p
        return None

    def _should_redact_title(self, title: str, policy: PrivacyPolicy) -> bool:
        """Check if a title matches redaction rules."""
        if not policy.redact_titles:
            return False

        # Check blocked patterns (redact if match)
        for pattern in self.compiled_blocked.get(policy.app_name, []):
            if pattern.search(title):
                return True

        # Check allowed patterns (don't redact if match)
        if self.compiled_allowed.get(policy.app_name):
            for pattern in self.compiled_allowed[policy.app_name]:
                if pattern.search(title):
                    return False

        # If redact_titles is True and no allow patterns matched, redact
        return True

    def redact_event(self, event: Event) -> Event:
        """Apply redaction policy to an event, returning a new Event."""
        policy = self._get_policy(event.app)
        if not policy:
            return event

        # Create a copy with redacted fields
        redacted = Event(
            ts=event.ts,
            event_type=event.event_type,
            app=event.app,
            session_id=event.session_id,
            id=event.id,
            extra=event.extra.copy() if event.extra else {},
        )

        # Redact window title
        if policy.redact_titles and event.window_title:
            if self._should_redact_title(event.window_title, policy):
                redacted.window_title = "[REDACTED]"
            else:
                redacted.window_title = self._redact_text(event.window_title)
        else:
            redacted.window_title = self._redact_text(event.window_title) if event.window_title else None

        # Redact URL
        if policy.redact_urls and event.url:
            redacted.url = "[REDACTED]"
        else:
            redacted.url = self._redact_text(event.url) if event.url else None

        # Always redact sensitive patterns in other fields
        redacted.target_element = self._redact_text(event.target_element) if event.target_element else None

        return redacted

    def _detect_sensitive(self, text: str) -> list[tuple[str, str]]:
        """Detect sensitive values in text; returns list of (type, value) tuples."""
        findings = []

        if self.EMAIL_PATTERN.search(text):
            for match in self.EMAIL_PATTERN.finditer(text):
                findings.append(("email", match.group()))

        if self.PHONE_PATTERN.search(text):
            for match in self.PHONE_PATTERN.finditer(text):
                findings.append(("phone", match.group()))

        if self.SSN_PATTERN.search(text):
            for match in self.SSN_PATTERN.finditer(text):
                findings.append(("ssn", match.group()))

        if self.CC_PATTERN.search(text):
            for match in self.CC_PATTERN.finditer(text):
                findings.append(("credit_card", match.group()))

        if self.IP_PATTERN.search(text):
            for match in self.IP_PATTERN.finditer(text):
                findings.append(("ip_address", match.group()))

        return findings

    def _redact_text(self, text: Optional[str]) -> Optional[str]:
        """Replace detected sensitive values with [REDACTED]."""
        if not text:
            return text

        result = text
        # Track replacements to avoid double-replacement
        for sensitive_type, value in self._detect_sensitive(text):
            result = result.replace(value, "[REDACTED]")

        return result

    @classmethod
    def from_json_file(cls, path: Path | str) -> Redactor:
        """Load policies from a JSON file in the data directory."""
        path = Path(path)
        if not path.exists():
            # Default: no redaction policy
            return cls([])

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        policies = [
            PrivacyPolicy(
                app_name=p.get("app_name", "*"),
                redact_titles=p.get("redact_titles", False),
                redact_urls=p.get("redact_urls", False),
                allowed_title_patterns=p.get("allowed_title_patterns", []),
                blocked_title_patterns=p.get("blocked_title_patterns", []),
            )
            for p in data.get("policies", [])
        ]
        return cls(policies)

    def to_json_file(self, path: Path | str) -> None:
        """Save policies to a JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "policies": [
                {
                    "app_name": p.app_name,
                    "redact_titles": p.redact_titles,
                    "redact_urls": p.redact_urls,
                    "allowed_title_patterns": p.allowed_title_patterns,
                    "blocked_title_patterns": p.blocked_title_patterns,
                }
                for p in self.policies
            ]
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
