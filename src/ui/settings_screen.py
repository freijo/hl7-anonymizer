"""Step 3 — Settings screen — placeholder."""

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
from src.ui.theme import COLORS_LIGHT


class SettingsScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 16, 28, 16)
        label = QLabel("Step 3: Settings (coming in WI-007)")
        label.setStyleSheet(f"color: {COLORS_LIGHT['text_muted']}; font-size: 14px;")
        layout.addWidget(label)
        layout.addStretch()
