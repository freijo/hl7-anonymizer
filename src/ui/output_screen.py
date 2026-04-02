"""WI-006/WI-017: Step 4 — Output screen.

Displays anonymized HL7 text with Copy-to-Clipboard and Export buttons.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.ui.theme import COLORS_LIGHT, WARNINGS


MONO_FONT = QFont("Cascadia Code", 11)
MONO_FONT.setStyleHint(QFont.StyleHint.Monospace)


class OutputScreen(QWidget):
    """Step 4: Display anonymized HL7 output with copy functionality."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._field_count = 0
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 16, 28, 16)
        outer.setSpacing(12)

        # --- Top bar: status + actions ---
        top_bar = QWidget()
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(12)

        self.status_label = QLabel("No anonymized data yet.")
        self.status_label.setStyleSheet(
            f"color: {COLORS_LIGHT['text_muted']}; font-size: 12px;"
        )
        top_layout.addWidget(self.status_label)

        top_layout.addStretch()

        # Copy button
        self.copy_btn = QPushButton("Copy to Clipboard")
        self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_btn.setFixedHeight(36)
        self.copy_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS_LIGHT['action_bg']}; color: white;
                border: none; border-radius: 4px; padding: 0 24px;
                font-size: 13px; font-weight: 700;
            }}
            QPushButton:hover {{
                background: {COLORS_LIGHT['action_hover']};
            }}
            QPushButton:disabled {{
                background: {COLORS_LIGHT['border']}; color: {COLORS_LIGHT['text_muted']};
            }}
        """)
        self.copy_btn.setEnabled(False)
        self.copy_btn.clicked.connect(self._copy_to_clipboard)
        top_layout.addWidget(self.copy_btn)

        # Export button
        self.export_btn = QPushButton("Export .txt")
        self.export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_btn.setFixedHeight(36)
        self.export_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS_LIGHT['accent']}; color: white;
                border: none; border-radius: 4px; padding: 0 24px;
                font-size: 13px; font-weight: 700;
            }}
            QPushButton:hover {{
                background: {COLORS_LIGHT['accent_hover']};
            }}
            QPushButton:disabled {{
                background: {COLORS_LIGHT['border']}; color: {COLORS_LIGHT['text_muted']};
            }}
        """)
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self._export_to_file)
        top_layout.addWidget(self.export_btn)

        outer.addWidget(top_bar)

        # --- Main textarea ---
        self.text_edit = QTextEdit()
        self.text_edit.setFont(MONO_FONT)
        self.text_edit.setReadOnly(True)
        self.text_edit.setPlaceholderText(
            "Anonymized HL7 output will appear here.\n\n"
            "Select fields in Step 2, then navigate here to anonymize."
        )
        self.text_edit.setStyleSheet(f"""
            QTextEdit {{
                background: {COLORS_LIGHT['surface']};
                border: 1px solid {COLORS_LIGHT['border']};
                border-radius: 6px;
                padding: 12px;
                color: {COLORS_LIGHT['text']};
            }}
        """)
        outer.addWidget(self.text_edit, 1)

        # --- WI-027: Anonymization log ---
        self.log_label = QLabel("")
        self.log_label.setWordWrap(True)
        self.log_label.setStyleSheet(
            f"color: {COLORS_LIGHT['text_muted']}; font-size: 11px; "
            f"background: {COLORS_LIGHT['surface']}; border: 1px solid {COLORS_LIGHT['border']}; "
            f"border-radius: 4px; padding: 8px;"
        )
        self.log_label.hide()
        outer.addWidget(self.log_label)

        # --- Feedback label (shown briefly after copy) ---
        self.feedback_label = QLabel("")
        self.feedback_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.feedback_label.setStyleSheet(
            f"color: {WARNINGS['success']['text']}; font-size: 11px;"
        )
        outer.addWidget(self.feedback_label)

    def set_anonymized_output(
        self, text: str, field_count: int,
        msg_count: int = 0, segments: set[str] | None = None, mask: str = "***",
    ):
        """Receive anonymized text and display it with log summary."""
        self._field_count = field_count
        self.text_edit.setPlainText(text)
        self.copy_btn.setEnabled(bool(text))
        self.export_btn.setEnabled(bool(text))

        if text:
            word = "field" if field_count == 1 else "fields"
            self.status_label.setText(f"Anonymized — {field_count} {word} masked")
            self.status_label.setStyleSheet(
                f"color: {WARNINGS['success']['text']}; font-size: 12px; font-weight: 600;"
            )
            # WI-027: Build log summary
            seg_list = ", ".join(sorted(segments)) if segments else "—"
            word_msg = "message" if msg_count == 1 else "messages"
            self.log_label.setText(
                f"Log: {field_count} {word} masked across {msg_count} {word_msg} "
                f"| Segments: {seg_list} | Mask: \"{mask}\""
            )
            self.log_label.show()
        else:
            self.status_label.setText("No anonymized data yet.")
            self.status_label.setStyleSheet(
                f"color: {COLORS_LIGHT['text_muted']}; font-size: 12px;"
            )
            self.log_label.hide()

    def _copy_to_clipboard(self):
        text = self.text_edit.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            self.feedback_label.setText("Copied to clipboard!")
            QTimer.singleShot(2000, lambda: self.feedback_label.setText(""))

    def _export_to_file(self):
        text = self.text_edit.toPlainText()
        if not text:
            return

        default_name = f"hl7_anonymized_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export anonymized HL7",
            default_name,
            "Text files (*.txt);;All files (*)",
        )
        if not path:
            return

        Path(path).write_text(text, encoding="utf-8")
        self.feedback_label.setText(f"Exported to {Path(path).name}")
        QTimer.singleShot(3000, lambda: self.feedback_label.setText(""))
