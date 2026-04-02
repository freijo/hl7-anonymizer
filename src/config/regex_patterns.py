"""WI-020/WI-021: Default and custom regex patterns for auto-detection.

Provides built-in regex patterns that match common PII formats
(dates, phone numbers, SSN/AHV, email, etc.) and a registry
that allows users to add/remove custom patterns at runtime.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class RegexPattern:
    """A named regex pattern for PII detection."""
    name: str
    pattern: str
    enabled: bool = True

    def compiled(self) -> re.Pattern | None:
        try:
            return re.compile(self.pattern)
        except re.error:
            return None


# WI-020: Built-in default patterns
DEFAULT_PATTERNS: list[RegexPattern] = [
    RegexPattern("Date/Time (HL7)", r"\b\d{8}(\d{2,6})?\b"),
    RegexPattern("Date (YYYY-MM-DD)", r"\b\d{4}-\d{2}-\d{2}\b"),
    RegexPattern("Date (DD.MM.YYYY)", r"\b\d{2}\.\d{2}\.\d{4}\b"),
    RegexPattern("Phone (intl)", r"\+\d[\d\s\-]{7,}"),
    RegexPattern("Phone (local)", r"\b0\d{2}[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}\b"),
    RegexPattern("SSN/AHV (756.xxxx.xxxx.xx)", r"\b756\.\d{4}\.\d{4}\.\d{2}\b"),
    RegexPattern("Email", r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    RegexPattern("IPv4", r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
]


class PatternRegistry:
    """Manages default + custom regex patterns."""

    def __init__(self):
        self._defaults = [RegexPattern(p.name, p.pattern, p.enabled) for p in DEFAULT_PATTERNS]
        self._custom: list[RegexPattern] = []

    @property
    def all_patterns(self) -> list[RegexPattern]:
        return self._defaults + self._custom

    @property
    def enabled_patterns(self) -> list[RegexPattern]:
        return [p for p in self.all_patterns if p.enabled]

    def add_custom(self, name: str, pattern: str) -> RegexPattern | None:
        """Add a custom pattern. Returns None if regex is invalid."""
        rp = RegexPattern(name, pattern)
        if rp.compiled() is None:
            return None
        self._custom.append(rp)
        return rp

    def remove_custom(self, index: int):
        """Remove a custom pattern by index (relative to custom list)."""
        if 0 <= index < len(self._custom):
            self._custom.pop(index)

    @property
    def custom_patterns(self) -> list[RegexPattern]:
        return list(self._custom)

    @property
    def default_patterns(self) -> list[RegexPattern]:
        return self._defaults

    def matches_any(self, text: str) -> bool:
        """Check if text matches any enabled pattern."""
        for p in self.enabled_patterns:
            compiled = p.compiled()
            if compiled and compiled.search(text):
                return True
        return False

    def to_dict_list(self) -> list[dict]:
        """Serialize custom patterns for config file."""
        return [{"name": p.name, "pattern": p.pattern, "enabled": p.enabled}
                for p in self._custom]

    def load_custom(self, items: list[dict]):
        """Load custom patterns from config dict list."""
        self._custom.clear()
        for item in items:
            rp = RegexPattern(
                name=item.get("name", "Custom"),
                pattern=item.get("pattern", ""),
                enabled=item.get("enabled", True),
            )
            if rp.compiled() is not None:
                self._custom.append(rp)
