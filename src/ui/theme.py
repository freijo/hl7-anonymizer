"""Design System & Color Scheme from Requirements Section 2."""

from __future__ import annotations


# WI-040: Theme manager — singleton that tracks current mode
class _ThemeManager:
    """Global theme state. Screens read `current_colors()` at build time."""

    def __init__(self):
        self.mode: str = "light"  # "light" | "dark"

    def current_colors(self) -> dict[str, str]:
        return COLORS_DARK if self.mode == "dark" else COLORS_LIGHT

    def toggle(self):
        self.mode = "dark" if self.mode == "light" else "light"

    def is_dark(self) -> bool:
        return self.mode == "dark"


theme_manager = _ThemeManager()


# 2.1 Base colors (from HL7_ADT_Doku)
COLORS_LIGHT = {
    "accent": "#0066A1",
    "accent_hover": "#004d7a",
    "accent_light": "#e8f2fa",
    "text": "#2d3748",
    "text_muted": "#718096",
    "bg": "#f7f8fc",
    "surface": "#ffffff",
    "panel": "#edf0f5",
    "border": "#d2d8e2",
    "gray_dark": "#4a5568",
    "action_bg": "#38a169",
    "action_hover": "#2f855a",
}

COLORS_DARK = {
    "accent": "#5bafde",
    "accent_hover": "#7cc4ea",
    "accent_light": "#1e3347",
    "text": "#dce4ec",
    "text_muted": "#8fa3b8",
    "bg": "#1a1d27",
    "surface": "#232735",
    "panel": "#2a2f3e",
    "border": "#3b4255",
    "gray_dark": "#3b4255",
    "action_bg": "#2e7d56",
    "action_hover": "#28684a",
}

# 2.2 Field selection states
FIELD_STATES_LIGHT = {
    "auto_detected": {
        "background": "#fef9e7",
        "border": "#e6c84d",
        "text": "#92600a",
    },
    "manually_selected": {
        "background": "#fee2e2",
        "border": "#f87171",
        "text": "#991b1b",
    },
    "llm_suggestion": {
        "background": "#f5f0fc",
        "border": "#c4b5e0",
        "text": "#553c8b",
    },
    "neutral": {
        "background": "#ffffff",
        "border": "#e8ecf1",
        "text": None,
    },
}

FIELD_STATES_DARK = {
    "auto_detected": {
        "background": "#3a3420",
        "border": "#c9a830",
        "text": "#f0d060",
    },
    "manually_selected": {
        "background": "#3a2020",
        "border": "#e05555",
        "text": "#f09090",
    },
    "llm_suggestion": {
        "background": "#2e2540",
        "border": "#9a85c8",
        "text": "#c8b0f0",
    },
    "neutral": {
        "background": "#232735",
        "border": "#3b4255",
        "text": None,
    },
}


def current_field_states() -> dict:
    """Return the field states matching the current theme."""
    return FIELD_STATES_DARK if theme_manager.is_dark() else FIELD_STATES_LIGHT


# Backwards compat alias — existing code that reads FIELD_STATES at import time
FIELD_STATES = FIELD_STATES_LIGHT

# 2.3 Warning colors
WARNINGS = {
    "non_hl7": {
        "background": "#fff1f0",
        "border": "#e53e3e",
        "text": "#c53030",
    },
    "success": {
        "background": "#c6f6d5",
        "border": "#38a169",
        "text": "#276749",
    },
}
