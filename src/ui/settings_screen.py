"""WI-007: Step 3 — Settings screen.

Mask character setting with live preview.
DoD: Änderung wird sofort bei nächster Anonymisierung angewendet.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from src.ui.theme import COLORS_LIGHT

DEFAULT_MASK = "***"


class SettingsScreen(QWidget):
    """Step 3: Anonymization settings."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 16, 28, 16)
        outer.setSpacing(16)

        heading = QLabel("Anonymization Settings")
        heading.setStyleSheet(
            f"color: {COLORS_LIGHT['text']}; font-size: 16px; font-weight: 700;"
        )
        outer.addWidget(heading)

        # --- Mask character card ---
        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background: {COLORS_LIGHT['surface']}; "
            f"border: 1px solid {COLORS_LIGHT['border']}; border-radius: 6px; }}"
        )
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 12, 16, 14)
        card_layout.setSpacing(8)

        title = QLabel("Mask Pattern")
        title.setStyleSheet(
            f"color: {COLORS_LIGHT['text']}; font-size: 13px; font-weight: 700; "
            f"border: none; border-bottom: 1px solid {COLORS_LIGHT['border']}; "
            f"padding-bottom: 6px;"
        )
        card_layout.addWidget(title)

        desc = QLabel(
            "The pattern that replaces selected field values. "
            "All selected fields will be replaced with this exact string."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(
            f"color: {COLORS_LIGHT['text_muted']}; font-size: 11px; border: none;"
        )
        card_layout.addWidget(desc)

        # Input row
        input_row = QWidget()
        input_row.setStyleSheet("border: none;")
        row_layout = QHBoxLayout(input_row)
        row_layout.setContentsMargins(0, 4, 0, 0)
        row_layout.setSpacing(10)

        label = QLabel("Mask:")
        label.setStyleSheet(
            f"color: {COLORS_LIGHT['text']}; font-size: 12px; font-weight: 600;"
        )
        row_layout.addWidget(label)

        self.mask_input = QLineEdit(DEFAULT_MASK)
        self.mask_input.setFont(QFont("Cascadia Code", 12))
        self.mask_input.setFixedWidth(160)
        self.mask_input.setFixedHeight(32)
        self.mask_input.setStyleSheet(f"""
            QLineEdit {{
                background: {COLORS_LIGHT['bg']};
                border: 1px solid {COLORS_LIGHT['border']};
                border-radius: 4px;
                padding: 0 8px;
                color: {COLORS_LIGHT['text']};
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border-color: {COLORS_LIGHT['accent']};
            }}
        """)
        self.mask_input.textChanged.connect(self._on_mask_changed)
        row_layout.addWidget(self.mask_input)

        # Preview
        self.preview_label = QLabel()
        self.preview_label.setStyleSheet(
            f"color: {COLORS_LIGHT['text_muted']}; font-size: 11px;"
        )
        row_layout.addWidget(self.preview_label)

        row_layout.addStretch()
        card_layout.addWidget(input_row)

        outer.addWidget(card)
        outer.addStretch()

        self._on_mask_changed()

    def _on_mask_changed(self):
        mask = self.mask_input.text()
        if mask:
            self.preview_label.setText(f'Preview: Müller^Hans → {mask}^{mask}')
        else:
            self.preview_label.setText('Preview: Müller^Hans → ^  (empty mask)')

    def get_mask(self) -> str:
        """Return the current mask pattern. Falls back to default if empty."""
        return self.mask_input.text() or DEFAULT_MASK
