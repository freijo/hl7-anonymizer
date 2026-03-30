"""Design System & Color Scheme from Requirements Section 2."""

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
    "accent": "#4da6d9",
    "accent_hover": "#6dbde6",
    "accent_light": "#1a2d3d",
    "text": "#e2e8f0",
    "text_muted": "#a0aec0",
    "bg": "#0f1117",
    "surface": "#171923",
    "panel": "#1e2130",
    "border": "#2d3748",
    "gray_dark": "#2d3748",
    "action_bg": "#276749",
    "action_hover": "#22543d",
}

# 2.2 Field selection states
FIELD_STATES = {
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
        "text": None,  # uses COLORS_LIGHT["text"] / COLORS_DARK["text"]
    },
}

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
