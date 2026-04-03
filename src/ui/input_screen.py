"""WI-002: Step 1 — Input screen.

Textarea for pasting HL7 messages, message counter, non-HL7 warning.
DoD: Works with 0, 1, and 10+ messages.
"""

from pathlib import Path

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.parser.hl7_parser import ParseResult, parse
from src.ui.theme import COLORS_LIGHT, WARNINGS, theme_manager


MONO_FONT = QFont("Cascadia Code", 11)
MONO_FONT.setStyleHint(QFont.StyleHint.Monospace)


class InputScreen(QWidget):
    """Step 1: Paste HL7 messages, see parsing status."""

    navigate_next = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._parse_result = ParseResult()
        self._parse_timer = QTimer(self)
        self._parse_timer.setSingleShot(True)
        self._parse_timer.setInterval(300)
        self._parse_timer.timeout.connect(self._do_parse)

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 16, 28, 16)
        layout.setSpacing(12)

        # --- Textarea ---
        self.text_edit = QTextEdit()
        self.text_edit.setFont(MONO_FONT)
        self.text_edit.setPlaceholderText("Paste HL7 messages here...")
        self.text_edit.setStyleSheet(f"""
            QTextEdit {{
                background: {COLORS_LIGHT['surface']};
                color: {COLORS_LIGHT['text']};
                border: 1px solid {COLORS_LIGHT['border']};
                border-radius: 6px;
                padding: 12px;
                font-size: 12px;
                line-height: 1.6;
            }}
            QTextEdit:focus {{
                border-color: {COLORS_LIGHT['accent']};
            }}
        """)
        self.text_edit.setMinimumHeight(220)
        self.text_edit.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.text_edit, 1)

        # WI-043: Enable drag & drop on parent, disable on QTextEdit so drops fall through
        self.setAcceptDrops(True)
        self.text_edit.setAcceptDrops(False)

        # --- Warning banner (hidden by default) ---
        self.warn_banner = QWidget()
        warn_bg = WARNINGS["non_hl7"]["background"]
        warn_border = WARNINGS["non_hl7"]["border"]
        warn_text = WARNINGS["non_hl7"]["text"]
        self.warn_banner.setStyleSheet(f"""
            QWidget {{
                background: {warn_bg};
                border: 1px solid {warn_border};
                border-radius: 6px;
            }}
        """)
        warn_outer = QVBoxLayout(self.warn_banner)
        warn_outer.setContentsMargins(14, 10, 14, 10)
        warn_outer.setSpacing(6)

        # Top row: icon + summary + toggle button
        warn_top = QWidget()
        warn_top.setStyleSheet("border: none; background: none;")
        warn_top_layout = QHBoxLayout(warn_top)
        warn_top_layout.setContentsMargins(0, 0, 0, 0)
        warn_top_layout.setSpacing(8)

        warn_icon = QLabel("\u26A0")
        warn_icon.setStyleSheet(f"font-size: 16px; border: none; color: {warn_text};")
        warn_top_layout.addWidget(warn_icon)

        self.warn_label = QLabel("")
        self.warn_label.setWordWrap(True)
        self.warn_label.setStyleSheet(f"color: {warn_text}; font-size: 12px; border: none;")
        warn_top_layout.addWidget(self.warn_label, 1)

        self.warn_toggle_btn = QPushButton("Show all")
        self.warn_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.warn_toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background: none; border: 1px solid {warn_border}; border-radius: 4px;
                color: {warn_text}; font-size: 11px; font-weight: 600;
                padding: 3px 10px;
            }}
            QPushButton:hover {{
                background: {warn_border}; color: white;
            }}
        """)
        self.warn_toggle_btn.setVisible(False)
        self.warn_toggle_btn.clicked.connect(self._toggle_warn_details)
        warn_top_layout.addWidget(self.warn_toggle_btn)

        warn_outer.addWidget(warn_top)

        # Detail list (hidden by default)
        self.warn_detail_list = QLabel("")
        self.warn_detail_list.setWordWrap(True)
        self.warn_detail_list.setStyleSheet(
            f"color: {warn_text}; font-size: 11px; border: none; "
            f"font-family: 'Cascadia Code', 'Consolas', monospace; padding: 6px 0 0 24px;"
        )
        self.warn_detail_list.setVisible(False)
        warn_outer.addWidget(self.warn_detail_list)

        self._warn_expanded = False
        self.warn_banner.setVisible(False)
        layout.addWidget(self.warn_banner)

        # --- Status bar ---
        status_bar = QWidget()
        status_bar.setStyleSheet("background: none;")
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(12)

        self.msg_count_badge = self._make_badge("0 messages", "info")
        status_layout.addWidget(self.msg_count_badge)

        self.segments_badge = self._make_badge("", "info")
        self.segments_badge.setVisible(False)
        status_layout.addWidget(self.segments_badge)

        self.non_hl7_badge = self._make_badge("", "warn")
        self.non_hl7_badge.setVisible(False)
        status_layout.addWidget(self.non_hl7_badge)

        self.hl7_status_badge = self._make_badge("", "info")
        self.hl7_status_badge.setVisible(False)
        status_layout.addWidget(self.hl7_status_badge)

        status_layout.addStretch()

        self.next_btn = QPushButton("Parse && Continue \u2192")
        self.next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS_LIGHT['accent']};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {COLORS_LIGHT['accent_hover']};
            }}
            QPushButton:disabled {{
                background: {COLORS_LIGHT['border']};
                color: {COLORS_LIGHT['text_muted']};
            }}
        """)
        self.next_btn.setEnabled(False)
        self.next_btn.clicked.connect(self.navigate_next.emit)
        status_layout.addWidget(self.next_btn)

        layout.addWidget(status_bar)

    def _make_badge(self, text: str, style: str) -> QLabel:
        if style == "info":
            bg = COLORS_LIGHT["accent_light"]
            color = COLORS_LIGHT["accent"]
        elif style == "warn":
            bg = WARNINGS["non_hl7"]["background"]
            color = WARNINGS["non_hl7"]["text"]
        else:
            bg = COLORS_LIGHT["panel"]
            color = COLORS_LIGHT["text"]

        label = QLabel(text)
        label.setStyleSheet(
            f"background: {bg}; color: {color}; "
            f"padding: 4px 12px; border-radius: 4px; font-weight: 600; font-size: 11px;"
        )
        return label

    def _on_text_changed(self):
        self._parse_timer.start()

    def _do_parse(self):
        text = self.text_edit.toPlainText()
        self._parse_result = parse(text)
        self._update_status()

    def _update_status(self):
        r = self._parse_result
        msg_count = len(r.messages)
        non_hl7_count = len(r.non_hl7_lines)

        # Message count badge
        word = "message" if msg_count == 1 else "messages"
        self.msg_count_badge.setText(f"{msg_count} {word} detected")

        # Segments badge
        if msg_count > 0:
            all_segments = set()
            for msg in r.messages:
                for seg in msg.segments:
                    all_segments.add(seg.name)
            sorted_segs = sorted(all_segments)
            self.segments_badge.setText(", ".join(sorted_segs))
            self.segments_badge.setVisible(True)
        else:
            self.segments_badge.setVisible(False)

        # Non-HL7 badge
        if non_hl7_count > 0:
            word = "line" if non_hl7_count == 1 else "lines"
            self.non_hl7_badge.setText(f"{non_hl7_count} non-HL7 {word}")
            self.non_hl7_badge.setVisible(True)
        else:
            self.non_hl7_badge.setVisible(False)

        # HL7 status badge
        text = self.text_edit.toPlainText().strip()
        if text:
            if r.is_valid_hl7:
                self.hl7_status_badge.setText("HL7 detected")
                self.hl7_status_badge.setStyleSheet(
                    f"background: {WARNINGS['success']['background']}; "
                    f"color: {WARNINGS['success']['text']}; "
                    f"padding: 4px 12px; border-radius: 4px; font-weight: 600; font-size: 11px;"
                )
            else:
                self.hl7_status_badge.setText("No valid HL7")
                self.hl7_status_badge.setStyleSheet(
                    f"background: {WARNINGS['non_hl7']['background']}; "
                    f"color: {WARNINGS['non_hl7']['text']}; "
                    f"padding: 4px 12px; border-radius: 4px; font-weight: 600; font-size: 11px;"
                )
            self.hl7_status_badge.setVisible(True)
        else:
            self.hl7_status_badge.setVisible(False)

        # Warning banner
        _MAX_PREVIEW = 3
        if non_hl7_count > 0:
            # Summary line (always visible): show first few lines inline
            lines_info = []
            for line_num, content in r.non_hl7_lines[:_MAX_PREVIEW]:
                preview = content[:50] + ("..." if len(content) > 50 else "")
                lines_info.append(f"Line {line_num}: <code>{preview}</code>")
            suffix = ""
            if non_hl7_count > _MAX_PREVIEW:
                suffix = f" (+{non_hl7_count - _MAX_PREVIEW} more)"
            self.warn_label.setText(
                f"<b>Non-HL7 content detected:</b> {'; '.join(lines_info)}{suffix} "
                f"— will be <b>ignored</b> during processing."
            )

            # Show toggle button only when there are more lines than the preview
            self.warn_toggle_btn.setVisible(non_hl7_count > _MAX_PREVIEW)
            if non_hl7_count <= _MAX_PREVIEW:
                self.warn_detail_list.setVisible(False)
                self._warn_expanded = False

            # Build full detail list
            detail_lines = []
            for line_num, content in r.non_hl7_lines:
                escaped = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                detail_lines.append(f"Line {line_num}: {escaped}")
            self._warn_detail_html = "<br>".join(detail_lines)
            self.warn_detail_list.setText(self._warn_detail_html)

            self.warn_banner.setVisible(True)
        else:
            self.warn_banner.setVisible(False)
            self.warn_detail_list.setVisible(False)
            self._warn_expanded = False

        # Next button enabled only if there's content
        self.next_btn.setEnabled(bool(text))

    def _toggle_warn_details(self):
        self._warn_expanded = not self._warn_expanded
        self.warn_detail_list.setVisible(self._warn_expanded)
        self.warn_toggle_btn.setText("Show less" if self._warn_expanded else "Show all")

    # WI-043: Drag & Drop file support
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        texts = []
        for f in files:
            p = Path(f)
            if p.suffix.lower() in (".hl7", ".txt", ".msg", ""):
                try:
                    texts.append(p.read_text(encoding="utf-8", errors="replace"))
                except OSError:
                    pass
        if texts:
            combined = "\n\n".join(texts)
            existing = self.text_edit.toPlainText()
            if existing.strip():
                self.text_edit.setPlainText(existing + "\n\n" + combined)
            else:
                self.text_edit.setPlainText(combined)

    def refresh_theme(self):
        """WI-040: Re-apply styles with current theme colors."""
        c = theme_manager.current_colors()
        self.text_edit.setStyleSheet(f"""
            QTextEdit {{
                background: {c['surface']}; color: {c['text']};
                border: 1px solid {c['border']}; border-radius: 6px;
                padding: 12px; font-size: 12px; line-height: 1.6;
            }}
            QTextEdit:focus {{ border-color: {c['accent']}; }}
        """)
        self.next_btn.setStyleSheet(f"""
            QPushButton {{
                background: {c['accent']}; color: white; border: none;
                border-radius: 4px; padding: 8px 16px; font-size: 12px; font-weight: 600;
            }}
            QPushButton:hover {{ background: {c['accent_hover']}; }}
            QPushButton:disabled {{ background: {c['border']}; color: {c['text_muted']}; }}
        """)
        for label in self.findChildren(QLabel):
            if label.styleSheet() and "font-weight: 600" in label.styleSheet():
                continue  # badge — skip
            ss = label.styleSheet()
            if ss and ("text_muted" in ss or "#718096" in ss):
                label.setStyleSheet(f"color: {c['text_muted']}; font-size: 11px;")

    def get_parse_result(self) -> ParseResult:
        return self._parse_result
