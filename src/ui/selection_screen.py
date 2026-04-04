"""WI-003: Step 2 — Field selection screen.

HL7 raw text displayed inline with clickable fields at component level.
- Each component (^), repetition (~), and subcomponent (&) is individually selectable
- Click toggles between Neutral and Manually Selected
- Click on segment name selects/deselects all fields in that segment
- Selection counter shows "X of Y selected"
- Works with raw text (no HL7 parsing) — shows plain text, no field interaction

DoD: Click toggles reliably. Counter updates in real-time.
     Works also with raw text without HL7 parsing.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QCursor, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QMenu,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.engine.llm_client import LLMConfig
from src.engine.llm_worker import LLMWorker

import json

from src.config.config_file import load_config, save_config
from src.config.field_definitions import DEFAULT_PII_FIELDS
from src.config.field_descriptions import get_field_tooltip
from src.parser.hl7_parser import HL7Field, HL7Message, HL7Segment, ParseResult, tokenize_field_value
from src.ui.theme import COLORS_LIGHT, FIELD_STATES, TOOLTIP_CSS, WARNINGS, theme_manager, current_field_states


MONO_FONT = QFont("Cascadia Code", 11)
MONO_FONT.setStyleHint(QFont.StyleHint.Monospace)

MONO_FONT_SMALL = QFont("Cascadia Code", 10)
MONO_FONT_SMALL.setStyleHint(QFont.StyleHint.Monospace)

# Selection states
STATE_NEUTRAL = "neutral"
STATE_AUTO = "auto_detected"
STATE_MANUAL = "manually_selected"
STATE_LLM = "llm_suggestion"

# WI-058: Pagination
PAGE_SIZE = 50  # messages per page


class _FieldInfo:
    """Lightweight field data for all messages — no Qt dependency."""
    __slots__ = ('msg_index', 'segment_name', 'field_index', 'path', 'value_text', 'state')

    def __init__(self, msg_index: int, segment_name: str, field_index: int, path: str, value_text: str):
        self.msg_index = msg_index
        self.segment_name = segment_name
        self.field_index = field_index
        self.path = path
        self.value_text = value_text
        self.state: str = STATE_NEUTRAL

    def is_selected(self) -> bool:
        return self.state in (STATE_AUTO, STATE_MANUAL, STATE_LLM)

# WI-047: Accessibility — symbols alongside colors for colorblind users
STATE_SYMBOLS = {
    STATE_AUTO: "\u25C9 ",      # ◉ auto-detected
    STATE_MANUAL: "\u2713 ",    # ✓ manually selected
    STATE_LLM: "\u2606 ",       # ☆ LLM suggestion
    STATE_NEUTRAL: "",           # no symbol
}


class ValueWidget(QLabel):
    """Smallest clickable unit — a single component/subcomponent/repetition value."""

    clicked = Signal()
    shift_clicked = Signal()  # WI-046: range selection
    double_clicked = Signal()
    context_menu_requested = Signal(object)  # emits self

    def __init__(self, text: str, path: str, field: HL7Field, msg_index: int, parent=None):
        super().__init__(parent)
        self.value_text = text
        self.path = path
        self.field = field
        self.msg_index = msg_index
        self.state = STATE_NEUTRAL

        self.setText(text if text else " ")
        self.setFont(MONO_FONT)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setToolTip(get_field_tooltip(field.segment_name, field.field_index))
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(lambda _: self.context_menu_requested.emit(self))
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._apply_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # WI-046: Shift+click emits range signal instead of simple toggle
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.shift_clicked.emit()
            else:
                # Don't toggle here — let _on_value_clicked handle it after undo snapshot
                self.clicked.emit()
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        """WI-026: Keyboard navigation — Space toggles, arrows move focus."""
        if event.key() == Qt.Key.Key_Space:
            self.clicked.emit()
        else:
            super().keyPressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit()
        super().mouseDoubleClickEvent(event)

    def set_state(self, state: str):
        self.state = state
        # WI-047: Update display text with accessibility symbol
        symbol = STATE_SYMBOLS.get(state, "")
        self.setText(f"{symbol}{self.value_text}" if self.value_text else " ")
        self._apply_style()

    def toggle(self):
        """Toggle selection state."""
        if self.state == STATE_NEUTRAL:
            self.set_state(STATE_MANUAL)
        elif self.state == STATE_MANUAL:
            self.set_state(STATE_NEUTRAL)
        elif self.state == STATE_AUTO:
            self.set_state(STATE_NEUTRAL)
        elif self.state == STATE_LLM:
            self.set_state(STATE_MANUAL)

    def is_selected(self) -> bool:
        return self.state in (STATE_AUTO, STATE_MANUAL, STATE_LLM)

    def _apply_style(self):
        c = theme_manager.current_colors()
        s = current_field_states()[self.state]
        bg = s["background"]
        border = s["border"]
        text_color = s["text"] or c["text"]
        self.setStyleSheet(
            f"QLabel {{ background: {bg}; border: 1px solid {border}; "
            f"color: {text_color}; padding: 1px 3px; border-radius: 2px; }}"
            + TOOLTIP_CSS
        )


def _make_separator_label(char: str) -> QLabel:
    """Create a styled separator label (^, ~, &, |)."""
    label = QLabel(char)
    label.setFont(MONO_FONT)
    c = theme_manager.current_colors()
    label.setStyleSheet(
        f"color: {c['border']}; padding: 1px 0; background: none;"
    )
    return label


class FieldGroupWidget(QWidget):
    """One pipe-separated field, rendered as ValueWidgets + separator labels.
    Components (^), repetitions (~), and subcomponents (&) are individually clickable.
    """

    def __init__(self, field: HL7Field, msg_index: int, encoding_chars: dict, parent=None):
        super().__init__(parent)
        self.value_widgets: list[ValueWidget] = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if field.is_empty:
            return

        # Special case: MSH.1 (field separator) and MSH.2 (encoding chars)
        # Show as single selectable unit without further tokenization
        is_msh_special = field.segment_name == "MSH" and field.field_index in (1, 2)

        if is_msh_special:
            vw = ValueWidget(field.raw_value, field.path, field, msg_index)
            self.value_widgets.append(vw)
            layout.addWidget(vw)
            return

        # Tokenize for component-level display
        tokens = tokenize_field_value(field.raw_value, encoding_chars)

        # Check what levels of nesting exist
        has_reps = any(t[1] == "repetition_sep" for t in tokens)
        has_comps = any(t[1] == "component_sep" for t in tokens)
        has_subs = any(t[1] == "subcomponent_sep" for t in tokens)
        is_simple = not has_reps and not has_comps and not has_subs

        # Track position for path building
        rep = 1
        comp = 1
        sub = 1

        for text, token_type in tokens:
            if token_type == "repetition_sep":
                layout.addWidget(_make_separator_label(text))
                rep += 1
                comp = 1
                sub = 1
            elif token_type == "component_sep":
                layout.addWidget(_make_separator_label(text))
                comp += 1
                sub = 1
            elif token_type == "subcomponent_sep":
                layout.addWidget(_make_separator_label(text))
                sub += 1
            else:
                # Build path
                if is_simple:
                    path = field.path
                else:
                    path = f"{field.segment_name}.{field.field_index}"
                    if has_reps:
                        path += f"({rep})"
                    if has_comps or has_subs:
                        path += f".{comp}"
                    if has_subs:
                        path += f".{sub}"

                # Skip creating a clickable widget for empty values between separators
                if text == "":
                    continue

                vw = ValueWidget(text, path, field, msg_index)
                self.value_widgets.append(vw)
                layout.addWidget(vw)


class SegmentLineWidget(QWidget):
    """A single segment line: clickable segment name + pipes + field groups."""

    selection_changed = Signal()

    def __init__(self, segment: HL7Segment, msg_index: int, encoding_chars: dict, parent=None):
        super().__init__(parent)
        self.value_widgets: list[ValueWidget] = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 1, 0, 1)
        layout.setSpacing(0)

        # Clickable segment name
        self.seg_label = QLabel(segment.name)
        self.seg_label.setFont(MONO_FONT)
        self.seg_label.setStyleSheet(
            f"color: {COLORS_LIGHT['accent']}; font-weight: 700; "
            f"padding: 1px 2px; background: none;"
            + TOOLTIP_CSS
        )
        self.seg_label.setFixedWidth(38)
        self.seg_label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.seg_label.setToolTip(f"Click to select/deselect all {segment.name} fields")
        self.seg_label.mousePressEvent = lambda e: self._toggle_all_fields()
        layout.addWidget(self.seg_label)

        fs = encoding_chars.get("field_sep", "|")

        # Build fields by index, filling gaps with pipes
        fields_by_idx = {f.field_index: f for f in segment.fields}
        if not fields_by_idx:
            layout.addStretch()
            return

        max_idx = max(fields_by_idx.keys())
        is_msh = segment.name == "MSH"
        start_idx = 1 if is_msh else 1

        for idx in range(start_idx, max_idx + 1):
            # MSH.1 is the separator itself — don't show an extra pipe before it
            if is_msh and idx == 1:
                layout.addWidget(_make_separator_label(fs))
                if idx in fields_by_idx:
                    fg = FieldGroupWidget(fields_by_idx[idx], msg_index, encoding_chars)
                    self.value_widgets.extend(fg.value_widgets)
                    layout.addWidget(fg)
                continue

            layout.addWidget(_make_separator_label(fs))
            if idx in fields_by_idx:
                f = fields_by_idx[idx]
                if f.is_empty:
                    continue
                fg = FieldGroupWidget(f, msg_index, encoding_chars)
                self.value_widgets.extend(fg.value_widgets)
                layout.addWidget(fg)

        layout.addStretch()

    def _toggle_all_fields(self):
        """Click on segment name: if any neutral → select all, else deselect all."""
        if not self.value_widgets:
            return
        any_neutral = any(not vw.is_selected() for vw in self.value_widgets)
        new_state = STATE_MANUAL if any_neutral else STATE_NEUTRAL
        for vw in self.value_widgets:
            vw.set_state(new_state)
        self.selection_changed.emit()


class NonHL7LineWidget(QWidget):
    """Display a non-HL7 line with warning styling."""

    def __init__(self, line_num: int, content: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 1, 0, 1)
        layout.setSpacing(6)

        warn = WARNINGS["non_hl7"]
        icon = QLabel("\u26A0")
        icon.setStyleSheet(f"color: {warn['text']}; font-size: 12px; background: none;")
        layout.addWidget(icon)

        text = QLabel(f"{content}")
        text.setFont(MONO_FONT_SMALL)
        text.setStyleSheet(
            f"color: {warn['text']}; background: {warn['background']}; "
            f"border: 1px solid {warn['border']}; border-radius: 2px; padding: 1px 4px;"
        )
        layout.addWidget(text)

        ignored = QLabel("ignored")
        ignored.setStyleSheet(
            f"color: {COLORS_LIGHT['text_muted']}; font-size: 10px; "
            f"font-style: italic; background: none;"
        )
        layout.addWidget(ignored)

        layout.addStretch()


class SelectionScreen(QWidget):
    """Step 2: Field selection with inline clickable HL7 fields at component level."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._parse_result: ParseResult | None = None
        self._all_value_widgets: list[ValueWidget] = []  # widgets on current page only
        self._segment_lines: list[SegmentLineWidget] = []
        self._last_clicked_widget: ValueWidget | None = None  # WI-046: for range selection
        self._sidebar_cards: list[QFrame] = []  # for theme refresh
        self._undo_stack: list[dict[str, str]] = []  # WI-044: {(msg_idx,path)->state}
        self._redo_stack: list[dict[str, str]] = []
        # WI-058: Data model for ALL fields + pagination
        self._all_fields: list[_FieldInfo] = []
        self._field_index: dict[tuple[int, str], _FieldInfo] = {}  # (msg_idx, path) -> info
        self._path_groups: dict[str, list[_FieldInfo]] = {}  # path -> fields across msgs
        self._current_page: int = 0
        self._total_pages: int = 1
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # --- Legend bar ---
        self.legend = QWidget()
        self.legend.setStyleSheet(
            f"background: {COLORS_LIGHT['surface']}; "
            f"border-bottom: 1px solid {COLORS_LIGHT['border']};"
        )
        legend_layout = QHBoxLayout(self.legend)
        legend_layout.setContentsMargins(28, 8, 28, 8)
        legend_layout.setSpacing(18)

        self.legend_title = QLabel("<b>Legend:</b>")
        self.legend_title.setStyleSheet(f"color: {COLORS_LIGHT['text']}; font-size: 12px;")
        legend_layout.addWidget(self.legend_title)

        self._legend_labels: list[QLabel] = []
        self._legend_swatches: list[tuple[QLabel, str]] = []  # (swatch, state_key)

        for state_key, label_text in [
            ("auto_detected", "\u25C9 Auto-detected"),
            ("manually_selected", "\u2713 Manually selected"),
            ("llm_suggestion", "\u2606 LLM suggestion"),
            ("neutral", "Not selected"),
        ]:
            s = current_field_states()[state_key]
            swatch = QLabel("  ")
            swatch.setFixedSize(14, 14)
            swatch.setStyleSheet(
                f"QLabel {{ background: {s['background']}; border: 1px solid {s['border']}; border-radius: 2px; }}"
            )
            legend_layout.addWidget(swatch)
            self._legend_swatches.append((swatch, state_key))
            lbl = QLabel(label_text)
            lbl.setStyleSheet(f"color: {COLORS_LIGHT['text_muted']}; font-size: 11px;")
            legend_layout.addWidget(lbl)
            self._legend_labels.append(lbl)

        legend_layout.addStretch()
        outer.addWidget(self.legend)

        # --- Main content: two-column layout ---
        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(28, 12, 28, 12)
        content_layout.setSpacing(16)

        # LEFT column
        left_column = QWidget()
        left_layout = QVBoxLayout(left_column)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        # WI-013: Search bar
        search_row = QWidget()
        search_layout = QHBoxLayout(search_row)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(6)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search field values...")
        self.search_input.setFixedHeight(30)
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background: {COLORS_LIGHT['surface']};
                border: 1px solid {COLORS_LIGHT['border']};
                border-radius: 4px; padding: 0 8px;
                color: {COLORS_LIGHT['text']}; font-size: 12px;
            }}
            QLineEdit:focus {{ border-color: {COLORS_LIGHT['accent']}; }}
        """)
        self.search_input.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self.search_input)

        self.search_count_label = QLabel("")
        self.search_count_label.setStyleSheet(
            f"color: {COLORS_LIGHT['text_muted']}; font-size: 10px;"
        )
        self.search_count_label.setFixedWidth(70)
        search_layout.addWidget(self.search_count_label)

        self.select_matches_btn = QPushButton("Select matches")
        self.select_matches_btn.setFixedHeight(30)
        self.select_matches_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.select_matches_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS_LIGHT['accent_light']}; color: {COLORS_LIGHT['accent']};
                border: 1px solid {COLORS_LIGHT['border']}; border-radius: 4px;
                font-size: 11px; font-weight: 600; padding: 0 10px;
            }}
            QPushButton:hover {{
                background: {COLORS_LIGHT['accent']}; color: white;
            }}
            QPushButton:disabled {{
                background: {COLORS_LIGHT['bg']}; color: {COLORS_LIGHT['text_muted']};
            }}
        """)
        self.select_matches_btn.setEnabled(False)
        self.select_matches_btn.clicked.connect(self._select_search_matches)
        search_layout.addWidget(self.select_matches_btn)

        left_layout.addWidget(search_row)

        # WI-033: LLM Analyse row
        llm_row = QWidget()
        llm_row_layout = QHBoxLayout(llm_row)
        llm_row_layout.setContentsMargins(0, 0, 0, 0)
        llm_row_layout.setSpacing(6)

        self.llm_analyze_btn = QPushButton("Analyze with LLM")
        self.llm_analyze_btn.setFixedHeight(30)
        self.llm_analyze_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.llm_analyze_btn.setStyleSheet(f"""
            QPushButton {{
                background: {FIELD_STATES['llm_suggestion']['border']};
                color: white; border: none; border-radius: 4px;
                font-size: 12px; font-weight: 700; padding: 0 14px;
            }}
            QPushButton:hover {{ background: {FIELD_STATES['llm_suggestion']['text']}; }}
            QPushButton:disabled {{
                background: {COLORS_LIGHT['border']}; color: {COLORS_LIGHT['text_muted']};
            }}
        """)
        self.llm_analyze_btn.setEnabled(False)
        self.llm_analyze_btn.clicked.connect(self._run_llm_analysis)
        llm_row_layout.addWidget(self.llm_analyze_btn)

        self.llm_cancel_btn = QPushButton("Cancel")
        self.llm_cancel_btn.setFixedHeight(30)
        self.llm_cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.llm_cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: none; color: {COLORS_LIGHT['text_muted']};
                border: 1px solid {COLORS_LIGHT['border']}; border-radius: 4px;
                font-size: 11px; padding: 0 10px;
            }}
            QPushButton:hover {{ color: #c0392b; border-color: #c0392b; }}
        """)
        self.llm_cancel_btn.hide()
        self.llm_cancel_btn.clicked.connect(self._cancel_llm_analysis)
        llm_row_layout.addWidget(self.llm_cancel_btn)

        self.llm_progress = QProgressBar()
        self.llm_progress.setFixedHeight(18)
        self.llm_progress.setStyleSheet(f"""
            QProgressBar {{
                background: {COLORS_LIGHT['bg']}; border: 1px solid {COLORS_LIGHT['border']};
                border-radius: 4px; text-align: center; font-size: 10px;
                color: {COLORS_LIGHT['text_muted']};
            }}
            QProgressBar::chunk {{
                background: {FIELD_STATES['llm_suggestion']['border']};
                border-radius: 3px;
            }}
        """)
        self.llm_progress.hide()
        llm_row_layout.addWidget(self.llm_progress, 1)

        # WI-034: Accept/Dismiss all buttons
        self.llm_accept_btn = QPushButton("Accept All")
        self.llm_accept_btn.setFixedHeight(30)
        self.llm_accept_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.llm_accept_btn.setStyleSheet(f"""
            QPushButton {{
                background: #276749; color: white;
                border: none; border-radius: 4px;
                font-size: 11px; font-weight: 600; padding: 0 10px;
            }}
            QPushButton:hover {{ background: #22543d; }}
        """)
        self.llm_accept_btn.hide()
        self.llm_accept_btn.clicked.connect(self._accept_all_suggestions)
        llm_row_layout.addWidget(self.llm_accept_btn)

        self.llm_dismiss_btn = QPushButton("Dismiss All")
        self.llm_dismiss_btn.setFixedHeight(30)
        self.llm_dismiss_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.llm_dismiss_btn.setStyleSheet(f"""
            QPushButton {{
                background: none; color: {COLORS_LIGHT['text_muted']};
                border: 1px solid {COLORS_LIGHT['border']}; border-radius: 4px;
                font-size: 11px; padding: 0 10px;
            }}
            QPushButton:hover {{ color: #c0392b; border-color: #c0392b; }}
        """)
        self.llm_dismiss_btn.hide()
        self.llm_dismiss_btn.clicked.connect(self._dismiss_all_suggestions)
        llm_row_layout.addWidget(self.llm_dismiss_btn)

        llm_row_layout.addStretch()
        left_layout.addWidget(llm_row)

        self._llm_worker: LLMWorker | None = None
        self._llm_config: LLMConfig | None = None

        # WI-044: Undo/Redo shortcuts
        undo_sc = QShortcut(QKeySequence.StandardKey.Undo, self)
        undo_sc.activated.connect(self._undo)
        redo_sc = QShortcut(QKeySequence.StandardKey.Redo, self)
        redo_sc.activated.connect(self._redo)

        # HL7 inline view (scrollable)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet(
            f"QScrollArea {{ background: {COLORS_LIGHT['surface']}; "
            f"border: 1px solid {COLORS_LIGHT['border']}; border-radius: 6px; }}"
        )

        self.hl7_container = QWidget()
        self.hl7_layout = QVBoxLayout(self.hl7_container)
        self.hl7_layout.setContentsMargins(12, 12, 12, 12)
        self.hl7_layout.setSpacing(0)
        self.hl7_layout.addStretch()
        self.scroll_area.setWidget(self.hl7_container)

        left_layout.addWidget(self.scroll_area, 1)

        # WI-058: Pagination bar
        self.page_bar = QWidget()
        self.page_bar.setStyleSheet("background: none;")
        page_layout = QHBoxLayout(self.page_bar)
        page_layout.setContentsMargins(0, 4, 0, 0)
        page_layout.setSpacing(8)

        self.page_prev_btn = QPushButton("\u25C0 Prev")
        self.page_prev_btn.setFixedHeight(26)
        self.page_prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.page_prev_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS_LIGHT['accent_light']}; color: {COLORS_LIGHT['accent']};
                border: 1px solid {COLORS_LIGHT['border']}; border-radius: 3px;
                font-size: 11px; font-weight: 600; padding: 0 10px;
            }}
            QPushButton:hover {{ background: {COLORS_LIGHT['accent']}; color: white; }}
            QPushButton:disabled {{ background: {COLORS_LIGHT['bg']}; color: {COLORS_LIGHT['text_muted']}; }}
        """)
        self.page_prev_btn.clicked.connect(self._page_prev)
        page_layout.addWidget(self.page_prev_btn)

        self.page_label = QLabel("Page 1 / 1")
        self.page_label.setStyleSheet(f"color: {COLORS_LIGHT['text_muted']}; font-size: 11px; font-weight: 600;")
        page_layout.addWidget(self.page_label)

        self.page_next_btn = QPushButton("Next \u25B6")
        self.page_next_btn.setFixedHeight(26)
        self.page_next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.page_next_btn.setStyleSheet(self.page_prev_btn.styleSheet())
        self.page_next_btn.clicked.connect(self._page_next)
        page_layout.addWidget(self.page_next_btn)

        page_layout.addStretch()
        self.page_bar.setVisible(False)
        left_layout.addWidget(self.page_bar)

        content_layout.addWidget(left_column, 3)

        # RIGHT: Sidebar
        sidebar = QWidget()
        sidebar.setFixedWidth(240)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(12)

        # Selection counter card
        counter_card = self._make_card("Selection Summary")
        self._sidebar_cards.append(counter_card)
        counter_body = QVBoxLayout()
        counter_body.setSpacing(4)

        self.sel_count_label = QLabel("0")
        self.sel_count_label.setStyleSheet(
            f"color: {COLORS_LIGHT['accent']}; font-size: 28px; font-weight: 700;"
        )
        self.sel_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        counter_body.addWidget(self.sel_count_label)

        self.sel_total_label = QLabel("of 0 fields selected")
        self.sel_total_label.setStyleSheet(
            f"color: {COLORS_LIGHT['text_muted']}; font-size: 11px;"
        )
        self.sel_total_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        counter_body.addWidget(self.sel_total_label)

        counter_card.layout().addLayout(counter_body)
        sidebar_layout.addWidget(counter_card)

        # Sync across messages card
        sync_card = self._make_card("Multi-Message")
        self._sidebar_cards.append(sync_card)
        self.sync_checkbox = QCheckBox("Auswahl auf alle\nMeldungen übertragen")
        self.sync_checkbox.setStyleSheet(
            f"QCheckBox {{ color: {COLORS_LIGHT['text']}; font-size: 11px; border: none; }}"
            + TOOLTIP_CSS
        )
        self.sync_checkbox.setToolTip(
            "Wenn aktiv, wird jede Feldauswahl automatisch auf\n"
            "das gleiche Feld in allen anderen Meldungen angewendet."
        )
        self.sync_checkbox.setChecked(True)
        sync_card.layout().addWidget(self.sync_checkbox)

        self.sync_status_label = QLabel("")
        self.sync_status_label.setWordWrap(True)
        self.sync_status_label.setStyleSheet(
            f"color: {COLORS_LIGHT['text_muted']}; font-size: 10px; border: none;"
        )
        sync_card.layout().addWidget(self.sync_status_label)
        sidebar_layout.addWidget(sync_card)

        # WI-011: Segment Quick-Select card
        seg_card = self._make_card("Segments")
        self._sidebar_cards.append(seg_card)
        self.seg_buttons_layout = QHBoxLayout()
        self.seg_buttons_layout.setSpacing(4)
        self.seg_buttons_layout.setContentsMargins(0, 0, 0, 0)
        seg_btn_wrap = QWidget()
        seg_btn_wrap.setStyleSheet("border: none;")
        seg_btn_wrap.setLayout(self.seg_buttons_layout)
        seg_card.layout().addWidget(seg_btn_wrap)

        self.seg_hint_label = QLabel("No segments yet.")
        self.seg_hint_label.setStyleSheet(
            f"color: {COLORS_LIGHT['text_muted']}; font-size: 10px; border: none;"
        )
        seg_card.layout().addWidget(self.seg_hint_label)
        sidebar_layout.addWidget(seg_card)

        # WI-041: Profiles card
        profile_card = self._make_card("Profiles")
        self._sidebar_cards.append(profile_card)
        self.profile_combo = QComboBox()
        self.profile_combo.setFixedHeight(28)
        self.profile_combo.setStyleSheet(f"""
            QComboBox {{
                background: {COLORS_LIGHT['bg']}; border: 1px solid {COLORS_LIGHT['border']};
                border-radius: 4px; padding: 0 8px; color: {COLORS_LIGHT['text']}; font-size: 11px;
            }}
            QComboBox::drop-down {{ border: none; }}
            QComboBox QAbstractItemView {{
                background: {COLORS_LIGHT['surface']}; border: 1px solid {COLORS_LIGHT['border']};
                color: {COLORS_LIGHT['text']}; selection-background-color: {COLORS_LIGHT['accent_light']};
            }}
        """)
        self._load_profile_list()
        profile_card.layout().addWidget(self.profile_combo)

        profile_btn_row = QWidget()
        profile_btn_row.setStyleSheet("border: none;")
        pbtn_layout = QHBoxLayout(profile_btn_row)
        pbtn_layout.setContentsMargins(0, 2, 0, 0)
        pbtn_layout.setSpacing(4)

        prof_btn_style = f"""
            QPushButton {{
                background: {COLORS_LIGHT['accent_light']}; color: {COLORS_LIGHT['accent']};
                border: 1px solid {COLORS_LIGHT['border']}; border-radius: 3px;
                font-size: 10px; font-weight: 600; padding: 2px 8px;
            }}
            QPushButton:hover {{ background: {COLORS_LIGHT['accent']}; color: white; }}
        """
        save_prof_btn = QPushButton("Save")
        save_prof_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_prof_btn.setFixedHeight(24)
        save_prof_btn.setStyleSheet(prof_btn_style)
        save_prof_btn.clicked.connect(self._save_profile)
        pbtn_layout.addWidget(save_prof_btn)

        load_prof_btn = QPushButton("Load")
        load_prof_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        load_prof_btn.setFixedHeight(24)
        load_prof_btn.setStyleSheet(prof_btn_style)
        load_prof_btn.clicked.connect(self._load_profile)
        pbtn_layout.addWidget(load_prof_btn)

        del_prof_btn = QPushButton("Del")
        del_prof_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_prof_btn.setFixedHeight(24)
        del_prof_btn.setStyleSheet(prof_btn_style)
        del_prof_btn.clicked.connect(self._delete_profile)
        pbtn_layout.addWidget(del_prof_btn)

        self._profile_buttons = [save_prof_btn, load_prof_btn, del_prof_btn]

        pbtn_layout.addStretch()
        profile_card.layout().addWidget(profile_btn_row)

        self.profile_name_input = QLineEdit()
        self.profile_name_input.setPlaceholderText("New profile name...")
        self.profile_name_input.setFixedHeight(24)
        self.profile_name_input.setStyleSheet(f"""
            QLineEdit {{
                background: {COLORS_LIGHT['bg']}; border: 1px solid {COLORS_LIGHT['border']};
                border-radius: 3px; padding: 0 6px; color: {COLORS_LIGHT['text']}; font-size: 10px;
            }}
        """)
        profile_card.layout().addWidget(self.profile_name_input)
        sidebar_layout.addWidget(profile_card)

        # Parse status card
        status_card = self._make_card("Parse Status")
        self._sidebar_cards.append(status_card)
        self.parse_status_label = QLabel("No data")
        self.parse_status_label.setWordWrap(True)
        self.parse_status_label.setStyleSheet(
            f"color: {COLORS_LIGHT['text_muted']}; font-size: 11px;"
        )
        status_card.layout().addWidget(self.parse_status_label)
        sidebar_layout.addWidget(status_card)

        sidebar_layout.addStretch()
        content_layout.addWidget(sidebar)

        outer.addWidget(content, 1)

    _card_headers: list[QLabel] = []

    def _make_card(self, title: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background: {COLORS_LIGHT['surface']}; "
            f"border: 1px solid {COLORS_LIGHT['border']}; border-radius: 6px; }}"
        )
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 8, 12, 10)
        card_layout.setSpacing(6)

        hdr = QLabel(title)
        hdr.setStyleSheet(
            f"QLabel {{ color: {COLORS_LIGHT['text']}; font-size: 12px; font-weight: 700; "
            f"border: none; border-bottom: 1px solid {COLORS_LIGHT['border']}; "
            f"padding-bottom: 6px; }}"
        )
        card_layout.addWidget(hdr)
        if not hasattr(self, '_card_headers_list'):
            self._card_headers_list = []
        self._card_headers_list.append(hdr)
        return card

    def _build_path_index(self):
        """Build index: path → list of ValueWidgets across all messages."""
        self._path_index: dict[str, list[ValueWidget]] = {}
        for vw in self._all_value_widgets:
            self._path_index.setdefault(vw.path, []).append(vw)

    def _sync_to_others(self, source: ValueWidget):
        """Propagate source widget's state to matching widgets in other messages."""
        if not self.sync_checkbox.isChecked():
            return
        # Update rendered widgets on current page
        siblings = self._path_index.get(source.path, [])
        for vw in siblings:
            if vw is not source:
                vw.set_state(source.state)
                self._update_field_model(vw)
        # WI-058: Also update data model for non-rendered messages
        for fi in self._path_groups.get(source.path, []):
            if fi.msg_index != source.msg_index:
                fi.state = source.state

    def _sync_segment_to_others(self, segment_line: SegmentLineWidget):
        """Propagate a segment-level toggle to matching segments in other messages."""
        if not self.sync_checkbox.isChecked():
            return
        for vw in segment_line.value_widgets:
            self._sync_to_others(vw)

    def set_parse_result(self, result: ParseResult):
        """Receive parsed data from input screen and render fields."""
        self._parse_result = result
        self._all_value_widgets.clear()
        self._segment_lines.clear()
        self._undo_stack.clear()
        self._redo_stack.clear()

        # WI-058: Build lightweight data model for ALL fields
        self._all_fields.clear()
        self._field_index.clear()
        self._path_groups.clear()
        if result.is_valid_hl7:
            self._build_field_data(result)

        # Auto-preselection on data model (no widgets needed)
        if result.is_valid_hl7:
            self._apply_auto_preselection()

        # Pagination setup
        msg_count = len(result.messages) if result.is_valid_hl7 else 0
        self._total_pages = max(1, (msg_count + PAGE_SIZE - 1) // PAGE_SIZE)
        self._current_page = 0
        self.page_bar.setVisible(self._total_pages > 1)
        self._update_page_controls()

        # Render first page
        self._render_page()
        self._build_path_index()
        self._build_segment_buttons()
        self._update_counter()
        self._update_sync_status()

    def _build_field_data(self, result: ParseResult):
        """WI-058: Build lightweight data model for ALL fields without creating widgets."""
        for msg_idx, msg in enumerate(result.messages):
            for segment in msg.segments:
                for field in segment.fields:
                    if field.is_empty:
                        continue
                    is_msh_special = field.segment_name == "MSH" and field.field_index in (1, 2)
                    if is_msh_special:
                        fi = _FieldInfo(msg_idx, field.segment_name, field.field_index,
                                        field.path, field.raw_value)
                        self._all_fields.append(fi)
                        self._field_index[(msg_idx, field.path)] = fi
                        self._path_groups.setdefault(field.path, []).append(fi)
                        continue
                    tokens = tokenize_field_value(field.raw_value, msg.encoding_chars)
                    has_reps = any(t[1] == "repetition_sep" for t in tokens)
                    has_comps = any(t[1] == "component_sep" for t in tokens)
                    has_subs = any(t[1] == "subcomponent_sep" for t in tokens)
                    is_simple = not has_reps and not has_comps and not has_subs
                    rep, comp, sub = 1, 1, 1
                    for text, token_type in tokens:
                        if token_type == "repetition_sep":
                            rep += 1; comp = 1; sub = 1
                        elif token_type == "component_sep":
                            comp += 1; sub = 1
                        elif token_type == "subcomponent_sep":
                            sub += 1
                        else:
                            if text == "":
                                continue
                            if is_simple:
                                path = field.path
                            else:
                                path = f"{field.segment_name}.{field.field_index}"
                                if has_reps:
                                    path += f"({rep})"
                                if has_comps or has_subs:
                                    path += f".{comp}"
                                if has_subs:
                                    path += f".{sub}"
                            fi = _FieldInfo(msg_idx, field.segment_name, field.field_index,
                                            path, text)
                            self._all_fields.append(fi)
                            self._field_index[(msg_idx, path)] = fi
                            self._path_groups.setdefault(path, []).append(fi)

    def _render_page(self):
        """WI-058: Render only the current page of messages as widgets."""
        # Clear existing content
        self._all_value_widgets.clear()
        self._segment_lines.clear()
        while self.hl7_layout.count():
            item = self.hl7_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        r = self._parse_result
        if r is None or (not r.messages and not r.non_hl7_lines):
            placeholder = QLabel("Paste HL7 messages in Step 1, then click 'Parse & Continue'.")
            placeholder.setStyleSheet(
                f"color: {COLORS_LIGHT['text_muted']}; font-size: 13px; padding: 20px;"
            )
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.hl7_layout.addWidget(placeholder)
            self.hl7_layout.addStretch()
            self._update_parse_status()
            return

        if not r.is_valid_hl7:
            for line_num, content in r.non_hl7_lines:
                w = NonHL7LineWidget(line_num, content)
                self.hl7_layout.addWidget(w)
            self.hl7_layout.addStretch()
            self._update_parse_status()
            return

        # WI-058: Only render messages for the current page
        start = self._current_page * PAGE_SIZE
        end = min(start + PAGE_SIZE, len(r.messages))

        # Build sorted list of non-HL7 lines for correct interleaving
        non_hl7_by_line = sorted(r.non_hl7_lines, key=lambda x: x[0]) if r.non_hl7_lines else []
        non_hl7_idx = 0

        for msg_idx in range(start, end):
            msg = r.messages[msg_idx]
            if msg_idx > start:
                sep = QFrame()
                sep.setFrameShape(QFrame.Shape.HLine)
                sep.setStyleSheet(f"color: {COLORS_LIGHT['border']}; margin: 8px 0;")
                self.hl7_layout.addWidget(sep)

            # Show non-HL7 lines that belong before this message
            while non_hl7_idx < len(non_hl7_by_line):
                ln, content = non_hl7_by_line[non_hl7_idx]
                if ln < msg.start_line:
                    w = NonHL7LineWidget(ln, content)
                    self.hl7_layout.addWidget(w)
                    non_hl7_idx += 1
                else:
                    break

            # Message header
            msg_header = QLabel(f"Message {msg_idx + 1} — {msg.message_type}")
            msg_header.setStyleSheet(
                f"color: {COLORS_LIGHT['text_muted']}; font-size: 11px; "
                f"font-weight: 600; padding: 4px 0 2px 0; background: none;"
            )
            self.hl7_layout.addWidget(msg_header)

            for segment in msg.segments:
                line_w = SegmentLineWidget(segment, msg_idx, msg.encoding_chars)
                self.hl7_layout.addWidget(line_w)
                self._segment_lines.append(line_w)

                line_w.selection_changed.connect(
                    lambda sl=line_w: self._on_segment_toggled(sl)
                )
                for vw in line_w.value_widgets:
                    vw.clicked.connect(lambda v=vw: self._on_value_clicked(v))
                    vw.shift_clicked.connect(lambda v=vw: self._on_shift_click(v))
                    vw.double_clicked.connect(lambda v=vw: self._select_same_value(v))
                    vw.context_menu_requested.connect(self._show_context_menu)
                    self._all_value_widgets.append(vw)
                    # Restore state from data model
                    key = (msg_idx, vw.path)
                    fi = self._field_index.get(key)
                    if fi and fi.state != STATE_NEUTRAL:
                        vw.set_state(fi.state)

        # Show remaining non-HL7 lines after last message
        while non_hl7_idx < len(non_hl7_by_line):
            ln, content = non_hl7_by_line[non_hl7_idx]
            w = NonHL7LineWidget(ln, content)
            self.hl7_layout.addWidget(w)
            non_hl7_idx += 1

        self.hl7_layout.addStretch()
        self._update_parse_status()

    def _page_prev(self):
        if self._current_page > 0:
            self._save_page_to_model()
            self._current_page -= 1
            self._render_page()
            self._build_path_index()
            self._update_page_controls()
            self.scroll_area.verticalScrollBar().setValue(0)

    def _page_next(self):
        if self._current_page < self._total_pages - 1:
            self._save_page_to_model()
            self._current_page += 1
            self._render_page()
            self._build_path_index()
            self._update_page_controls()
            self.scroll_area.verticalScrollBar().setValue(0)

    def _update_page_controls(self):
        self.page_label.setText(f"Page {self._current_page + 1} / {self._total_pages}")
        self.page_prev_btn.setEnabled(self._current_page > 0)
        self.page_next_btn.setEnabled(self._current_page < self._total_pages - 1)

    def _save_page_to_model(self):
        """Save current page widget states back to the data model."""
        for vw in self._all_value_widgets:
            key = (vw.msg_index, vw.path)
            fi = self._field_index.get(key)
            if fi:
                fi.state = vw.state

    def _on_value_clicked(self, vw: ValueWidget):
        """Handle a single value widget click — snapshot, toggle, sync, update."""
        self._save_undo_snapshot()
        vw.toggle()
        self._update_field_model(vw)
        self._last_clicked_widget = vw
        self._sync_to_others(vw)
        self._update_counter()

    def _update_field_model(self, vw: ValueWidget):
        """Keep data model in sync with widget state."""
        fi = self._field_index.get((vw.msg_index, vw.path))
        if fi:
            fi.state = vw.state

    def _on_shift_click(self, vw: ValueWidget):
        """WI-046: Shift+click selects range from last clicked to this widget."""
        if self._last_clicked_widget is None:
            vw.toggle()
            vw.clicked.emit()
            return
        self._save_undo_snapshot()
        try:
            idx_start = self._all_value_widgets.index(self._last_clicked_widget)
            idx_end = self._all_value_widgets.index(vw)
        except ValueError:
            vw.toggle()
            vw.clicked.emit()
            return
        lo, hi = min(idx_start, idx_end), max(idx_start, idx_end)
        for i in range(lo, hi + 1):
            w = self._all_value_widgets[i]
            w.set_state(STATE_MANUAL)
            self._update_field_model(w)
            if self.sync_checkbox.isChecked():
                self._sync_to_others(w)
        self._last_clicked_widget = vw
        self._update_counter()

    def _on_segment_toggled(self, segment_line: SegmentLineWidget):
        """Handle segment-level toggle — sync + update counter."""
        self._save_undo_snapshot()
        # Update data model for toggled widgets
        for vw in segment_line.value_widgets:
            self._update_field_model(vw)
        self._sync_segment_to_others(segment_line)
        self._update_counter()

    def _update_sync_status(self):
        """Update the sync card status label with message count info."""
        r = self._parse_result
        if r is None or not r.is_valid_hl7 or len(r.messages) < 2:
            self.sync_status_label.setText("Nur bei mehreren Meldungen relevant.")
            self.sync_checkbox.setEnabled(False)
        else:
            n = len(r.messages)
            self.sync_status_label.setText(f"{n} Meldungen erkannt.")
            self.sync_checkbox.setEnabled(True)

    def set_pattern_registry(self, registry):
        """WI-020: Set the regex pattern registry for auto-detection."""
        self._pattern_registry = registry

    def set_pii_fields_enabled(self, enabled: bool):
        """Toggle PII field definition auto-detection."""
        self._pii_fields_enabled = enabled

    def _apply_auto_preselection(self):
        """WI-004/WI-058: Auto-preselect on data model (no widgets needed)."""
        pii_enabled = getattr(self, '_pii_fields_enabled', True)
        registry = getattr(self, '_pattern_registry', None)
        for fi in self._all_fields:
            is_pii = (
                pii_enabled
                and (fi.segment_name, fi.field_index) in DEFAULT_PII_FIELDS
            )
            is_regex = (
                registry is not None
                and fi.value_text.strip()
                and registry.matches_any(fi.value_text)
            )
            if is_pii or is_regex:
                fi.state = STATE_AUTO

    def _update_counter(self):
        """WI-058: Count from data model (covers all pages)."""
        total = len(self._all_fields)
        selected = sum(1 for fi in self._all_fields if fi.is_selected())
        self.sel_count_label.setText(str(selected))
        word = "field" if total == 1 else "fields"
        self.sel_total_label.setText(f"of {total} {word} selected")


    def _update_parse_status(self):
        r = self._parse_result
        if r is None:
            self.parse_status_label.setText("No data")
            return

        if r.is_valid_hl7:
            msg_count = len(r.messages)
            seg_count = sum(len(m.segments) for m in r.messages)
            word_msg = "message" if msg_count == 1 else "messages"
            word_seg = "segment" if seg_count == 1 else "segments"
            self.parse_status_label.setText(
                f"HL7 detected: {msg_count} {word_msg}, {seg_count} {word_seg}"
            )
            self.parse_status_label.setStyleSheet(
                f"color: {WARNINGS['success']['text']}; font-size: 11px; border: none;"
            )
        else:
            self.parse_status_label.setText("No valid HL7 detected — raw text mode")
            self.parse_status_label.setStyleSheet(
                f"color: {WARNINGS['non_hl7']['text']}; font-size: 11px; border: none;"
            )

    def _build_segment_buttons(self):
        """WI-011: Build quick-select buttons for each unique segment name."""
        # Clear existing buttons
        while self.seg_buttons_layout.count():
            item = self.seg_buttons_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        r = self._parse_result
        if r is None or not r.is_valid_hl7:
            self.seg_hint_label.setText("No segments yet.")
            self.seg_hint_label.show()
            return

        # Collect unique segment names in order of appearance
        seen: set[str] = set()
        seg_names: list[str] = []
        for msg in r.messages:
            for seg in msg.segments:
                if seg.name not in seen:
                    seen.add(seg.name)
                    seg_names.append(seg.name)

        if not seg_names:
            self.seg_hint_label.setText("No segments yet.")
            self.seg_hint_label.show()
            return

        self.seg_hint_label.setText("Click to toggle segment.")
        for name in seg_names:
            btn = QPushButton(name)
            btn.setFixedHeight(24)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {COLORS_LIGHT['accent_light']}; color: {COLORS_LIGHT['accent']};
                    border: 1px solid {COLORS_LIGHT['border']}; border-radius: 3px;
                    font-size: 10px; font-weight: 700; padding: 0 6px;
                }}
                QPushButton:hover {{
                    background: {COLORS_LIGHT['accent']}; color: white;
                }}
            """ + TOOLTIP_CSS)
            btn.setToolTip(f"Select/deselect all {name} fields")
            btn.clicked.connect(lambda checked, n=name: self._toggle_segment_by_name(n))
            self.seg_buttons_layout.addWidget(btn)

        self.seg_buttons_layout.addStretch()

    def _toggle_segment_by_name(self, seg_name: str):
        """Toggle all value widgets belonging to the given segment name."""
        # Check rendered widgets for current state
        widgets = [vw for vw in self._all_value_widgets if vw.field.segment_name == seg_name]
        if not widgets:
            return
        any_neutral = any(not vw.is_selected() for vw in widgets)
        new_state = STATE_MANUAL if any_neutral else STATE_NEUTRAL
        # WI-058: Update data model for ALL messages with this segment
        for fi in self._all_fields:
            if fi.segment_name == seg_name:
                fi.state = new_state
        for vw in widgets:
            vw.set_state(new_state)
            self._update_field_model(vw)
            if self.sync_checkbox.isChecked():
                self._sync_to_others(vw)
        self._update_counter()

    # --- WI-012: Value-based Selection ---

    def _select_same_value(self, source: ValueWidget):
        """Double-click: select all fields with the same value text across all messages."""
        val = source.value_text.lower()
        if not val.strip():
            return
        # WI-058: Update data model for ALL messages
        for fi in self._all_fields:
            if fi.value_text.lower() == val:
                fi.state = STATE_MANUAL
        # Update rendered widgets
        for vw in self._all_value_widgets:
            if vw.value_text.lower() == val:
                vw.set_state(STATE_MANUAL)
        self._update_counter()

    # --- WI-013: Search ---

    @staticmethod
    def _match_query(query: str, value: str) -> bool:
        """Match query against value. Supports * as wildcard."""
        if "*" in query:
            # Split by * and check parts appear in order
            parts = [p for p in query.split("*") if p]
            pos = 0
            for part in parts:
                idx = value.find(part, pos)
                if idx == -1:
                    return False
                pos = idx + len(part)
            # If query starts with *, match anywhere; otherwise must start at 0
            if not query.startswith("*") and parts:
                if not value.startswith(parts[0]):
                    return False
            # If query ends with *, allow trailing; otherwise must end with last part
            if not query.endswith("*") and parts:
                if not value.endswith(parts[-1]):
                    return False
            return True
        return query in value

    def _on_search_changed(self, text: str):
        """Highlight matching value widgets and update count. Supports * wildcard."""
        self._search_matches: list[ValueWidget] = []
        query = text.strip().lower()

        for vw in self._all_value_widgets:
            if query and self._match_query(query, vw.value_text.lower()):
                self._search_matches.append(vw)
                vw._apply_style()
                # Override border to highlight match
                clr = theme_manager.current_colors()
                s = current_field_states()[vw.state]
                bg = s["background"]
                text_color = s["text"] or clr["text"]
                vw.setStyleSheet(
                    f"QLabel {{ background: {bg}; border: 2px solid {clr['accent']}; "
                    f"color: {text_color}; padding: 1px 3px; border-radius: 2px; }}"
                )
            else:
                vw._apply_style()

        if query:
            n = len(self._search_matches)
            self.search_count_label.setText(f"{n} match{'es' if n != 1 else ''}")
            self.select_matches_btn.setEnabled(n > 0)
        else:
            self.search_count_label.setText("")
            self.select_matches_btn.setEnabled(False)

    def _select_search_matches(self):
        """WI-013: Select all fields matching the current search."""
        for vw in self._search_matches:
            vw.set_state(STATE_MANUAL)
            self._update_field_model(vw)
            if self.sync_checkbox.isChecked():
                self._sync_to_others(vw)
        self.search_input.clear()
        self._update_counter()

    # --- WI-025: Context Menu ---

    def _show_context_menu(self, vw: ValueWidget):
        """Show right-click context menu for a value widget."""
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background: {COLORS_LIGHT['surface']}; border: 1px solid {COLORS_LIGHT['border']};
                padding: 4px; font-size: 12px;
            }}
            QMenu::item {{ padding: 4px 20px; color: {COLORS_LIGHT['text']}; }}
            QMenu::item:selected {{ background: {COLORS_LIGHT['accent_light']}; color: {COLORS_LIGHT['accent']}; }}
        """)

        # Toggle this field
        if vw.is_selected():
            act_toggle = menu.addAction("Deselect this field")
        else:
            act_toggle = menu.addAction("Select this field")
        act_toggle.triggered.connect(lambda: self._ctx_toggle(vw))

        # Select all in segment
        act_seg = menu.addAction(f"Select all {vw.field.segment_name} fields")
        act_seg.triggered.connect(lambda: self._ctx_select_segment(vw.field.segment_name))

        # Select same value everywhere
        if vw.value_text.strip():
            act_val = menu.addAction(f'Select "{vw.value_text[:20]}" everywhere')
            act_val.triggered.connect(lambda: self._select_same_value(vw))

        menu.addSeparator()

        # Search for value
        if vw.value_text.strip():
            act_search = menu.addAction(f'Search for "{vw.value_text[:20]}"')
            act_search.triggered.connect(lambda: self.search_input.setText(vw.value_text))

        menu.exec(QCursor.pos())

    def _ctx_toggle(self, vw: ValueWidget):
        vw.toggle()
        self._update_field_model(vw)
        self._sync_to_others(vw)
        self._update_counter()

    def _ctx_select_segment(self, seg_name: str):
        self._toggle_segment_by_name(seg_name)

    # --- WI-033/034/035: LLM Analysis ---

    def _styled_msgbox(self, icon, title: str, text: str,
                       buttons=QMessageBox.StandardButton.Ok,
                       default=QMessageBox.StandardButton.Ok) -> QMessageBox.StandardButton:
        """Show a QMessageBox with explicit styling so text is visible."""
        c = theme_manager.current_colors()
        box = QMessageBox(icon, title, text, buttons, self)
        box.setDefaultButton(default)
        box.setStyleSheet(
            f"QMessageBox {{ background: {c['surface']}; }}"
            f"QMessageBox QLabel {{ color: {c['text']}; font-size: 13px; }}"
            f"QPushButton {{ background: {c['accent']}; color: white; border: none; "
            f"border-radius: 4px; padding: 6px 18px; font-size: 12px; font-weight: 600; }}"
            f"QPushButton:hover {{ background: {c['accent_hover']}; }}"
        )
        return box.exec()

    def set_llm_config(self, config: LLMConfig):
        """Receive LLM config from main window."""
        self._llm_config = config
        enabled = config.mode != "none" and bool(self._all_value_widgets)
        self.llm_analyze_btn.setEnabled(enabled)

    def _run_llm_analysis(self):
        """WI-033: Start LLM analysis of unselected fields in background."""
        if not self._llm_config or self._llm_config.mode == "none":
            return

        if not self._llm_config.model_name:
            self._styled_msgbox(
                QMessageBox.Icon.Warning, "LLM Configuration",
                "No model name configured.\n\n"
                "Go to Step 3 → LLM Analysis → set a model name\n"
                "(e.g. llama3, mistral, gemma).",
            )
            return

        # WI-035: Remote API warning
        if self._llm_config.is_remote:
            reply = self._styled_msgbox(
                QMessageBox.Icon.Warning,
                "Data Locality Warning",
                f"Data will be sent to {self._llm_config.base_url}\n\n"
                "This is not a local endpoint. Patient data will leave this machine.\n"
                "Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        # F-LLM-15: Only analyse unselected fields (from data model)
        self._save_page_to_model()
        seen = set()
        unique_texts = []
        for fi in self._all_fields:
            if not fi.is_selected() and fi.value_text.strip() and fi.value_text not in seen:
                seen.add(fi.value_text)
                unique_texts.append(fi.value_text)
        if not unique_texts:
            return

        self.llm_analyze_btn.setEnabled(False)
        self.llm_cancel_btn.show()
        self.llm_progress.show()
        self.llm_progress.setMaximum(len(unique_texts))
        self.llm_progress.setValue(0)

        self._llm_worker = LLMWorker(self._llm_config, unique_texts)
        self._llm_worker.progress.connect(self._on_llm_progress)
        self._llm_worker.finished_all.connect(self._on_llm_finished)
        self._llm_worker.error.connect(self._on_llm_error)
        self._llm_worker.start()

    def _cancel_llm_analysis(self):
        if self._llm_worker:
            self._llm_worker.cancel()

    def _on_llm_progress(self, current: int, total: int):
        self.llm_progress.setValue(current)
        self.llm_progress.setFormat(f"{current}/{total}")

    def _on_llm_error(self, message: str):
        self.llm_progress.hide()
        self.llm_cancel_btn.hide()
        self.llm_analyze_btn.setEnabled(True)
        self._styled_msgbox(QMessageBox.Icon.Warning, "LLM Error", message)

    def _on_llm_finished(self, results: list):
        """WI-034: Apply LLM results as purple suggestions."""
        self.llm_progress.hide()
        self.llm_cancel_btn.hide()
        self.llm_analyze_btn.setEnabled(True)

        # Collect all entity values found by LLM
        found_values: set[str] = set()
        for _text, result in results:
            if result.ok:
                for entity in result.entities:
                    found_values.add(entity.value)

        if not found_values:
            return

        # WI-058: Mark on data model + rendered widgets
        suggestion_count = 0
        for fi in self._all_fields:
            if fi.is_selected():
                continue
            if fi.value_text in found_values:
                fi.state = STATE_LLM
                suggestion_count += 1
        # Sync to rendered widgets
        for vw in self._all_value_widgets:
            fi = self._field_index.get((vw.msg_index, vw.path))
            if fi and fi.state == STATE_LLM:
                vw.set_state(STATE_LLM)

        if suggestion_count > 0:
            self.llm_accept_btn.show()
            self.llm_dismiss_btn.show()
            self._update_counter()

    def _accept_all_suggestions(self):
        """WI-034: Accept all LLM suggestions → manually selected."""
        for fi in self._all_fields:
            if fi.state == STATE_LLM:
                fi.state = STATE_MANUAL
        for vw in self._all_value_widgets:
            if vw.state == STATE_LLM:
                vw.set_state(STATE_MANUAL)
        self.llm_accept_btn.hide()
        self.llm_dismiss_btn.hide()
        self._update_counter()

    def _dismiss_all_suggestions(self):
        """WI-034: Dismiss all LLM suggestions → neutral."""
        for fi in self._all_fields:
            if fi.state == STATE_LLM:
                fi.state = STATE_NEUTRAL
        for vw in self._all_value_widgets:
            if vw.state == STATE_LLM:
                vw.set_state(STATE_NEUTRAL)
        self.llm_accept_btn.hide()
        self.llm_dismiss_btn.hide()
        self._update_counter()

    # --- WI-041: Profiles ---

    def _load_profile_list(self):
        """Populate the profile combo from config."""
        self.profile_combo.clear()
        cfg = load_config()
        profiles = cfg.get("profiles", {})
        for name in sorted(profiles.keys()):
            self.profile_combo.addItem(name)

    def _save_profile(self):
        """Save current field selections as a named profile."""
        name = self.profile_name_input.text().strip()
        if not name:
            name = self.profile_combo.currentText()
        if not name:
            return
        # WI-058: Store selected paths from data model
        self._save_page_to_model()
        selected_paths = list({fi.path for fi in self._all_fields if fi.is_selected()})
        cfg = load_config()
        profiles = cfg.get("profiles", {})
        profiles[name] = selected_paths
        cfg["profiles"] = profiles
        save_config(cfg)
        self.profile_name_input.clear()
        self._load_profile_list()
        # Select the saved profile
        idx = self.profile_combo.findText(name)
        if idx >= 0:
            self.profile_combo.setCurrentIndex(idx)

    def _load_profile(self):
        """Load a named profile and apply field selections."""
        name = self.profile_combo.currentText()
        if not name:
            return
        cfg = load_config()
        profiles = cfg.get("profiles", {})
        paths = set(profiles.get(name, []))
        if not paths:
            return
        self._save_undo_snapshot()
        # WI-058: Apply to data model + rendered widgets
        for fi in self._all_fields:
            fi.state = STATE_MANUAL if fi.path in paths else STATE_NEUTRAL
        for vw in self._all_value_widgets:
            fi = self._field_index.get((vw.msg_index, vw.path))
            if fi:
                vw.set_state(fi.state)
        self._update_counter()

    def _delete_profile(self):
        """Delete the selected profile."""
        name = self.profile_combo.currentText()
        if not name:
            return
        cfg = load_config()
        profiles = cfg.get("profiles", {})
        profiles.pop(name, None)
        cfg["profiles"] = profiles
        save_config(cfg)
        self._load_profile_list()

    # --- WI-044: Undo / Redo ---

    def _save_undo_snapshot(self):
        """WI-058: Capture state from data model for undo."""
        self._save_page_to_model()
        snapshot = {(fi.msg_index, fi.path): fi.state for fi in self._all_fields}
        self._undo_stack.append(snapshot)
        self._redo_stack.clear()
        if len(self._undo_stack) > 50:
            self._undo_stack.pop(0)

    def _restore_snapshot(self, snapshot: dict):
        """WI-058: Restore states to data model + current page widgets."""
        for fi in self._all_fields:
            key = (fi.msg_index, fi.path)
            if key in snapshot:
                fi.state = snapshot[key]
        # Sync rendered widgets on current page
        for vw in self._all_value_widgets:
            fi = self._field_index.get((vw.msg_index, vw.path))
            if fi:
                vw.set_state(fi.state)
        self._update_counter()

    def _undo(self):
        if not self._undo_stack:
            return
        self._save_page_to_model()
        current = {(fi.msg_index, fi.path): fi.state for fi in self._all_fields}
        self._redo_stack.append(current)
        snapshot = self._undo_stack.pop()
        self._restore_snapshot(snapshot)

    def _redo(self):
        if not self._redo_stack:
            return
        self._save_page_to_model()
        current = {(fi.msg_index, fi.path): fi.state for fi in self._all_fields}
        self._undo_stack.append(current)
        snapshot = self._redo_stack.pop()
        self._restore_snapshot(snapshot)

    def refresh_theme(self):
        """WI-040: Re-apply all inline stylesheets with current theme colors."""
        c = theme_manager.current_colors()

        # Legend bar
        self.legend.setStyleSheet(
            f"background: {c['surface']}; border-bottom: 1px solid {c['border']};"
        )
        self.legend_title.setStyleSheet(f"color: {c['text']}; font-size: 12px;")
        for lbl in self._legend_labels:
            lbl.setStyleSheet(f"color: {c['text_muted']}; font-size: 11px;")

        # Legend swatches
        fs = current_field_states()
        for swatch, state_key in self._legend_swatches:
            s = fs[state_key]
            swatch.setStyleSheet(
                f"QLabel {{ background: {s['background']}; border: 1px solid {s['border']}; border-radius: 2px; }}"
            )

        # Re-apply field widget styles (value widgets use current_field_states dynamically)
        for vw in self._all_value_widgets:
            vw._apply_style()

        # Search input
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background: {c['surface']}; border: 1px solid {c['border']};
                border-radius: 4px; padding: 0 8px;
                color: {c['text']}; font-size: 12px;
            }}
            QLineEdit:focus {{ border-color: {c['accent']}; }}
        """)
        self.search_count_label.setStyleSheet(f"color: {c['text_muted']}; font-size: 10px;")
        self.select_matches_btn.setStyleSheet(f"""
            QPushButton {{
                background: {c['accent_light']}; color: {c['accent']};
                border: 1px solid {c['border']}; border-radius: 4px;
                font-size: 11px; font-weight: 600; padding: 0 10px;
            }}
            QPushButton:hover {{ background: {c['accent']}; color: white; }}
            QPushButton:disabled {{ background: {c['bg']}; color: {c['text_muted']}; }}
        """)

        # Scroll area + HL7 container
        self.scroll_area.setStyleSheet(
            f"QScrollArea {{ background: {c['surface']}; "
            f"border: 1px solid {c['border']}; border-radius: 6px; }}"
        )
        self.hl7_container.setStyleSheet(f"background: {c['surface']};")

        # Separator labels in segments
        for seg_line in self._segment_lines:
            seg_line.seg_label.setStyleSheet(
                f"color: {c['accent']}; font-weight: 700; padding: 1px 2px; background: none;"
                + TOOLTIP_CSS
            )
            # Refresh pipe/separator labels within segment rows
            for child in seg_line.findChildren(QLabel):
                if child is not seg_line.seg_label and child not in self._all_value_widgets:
                    child.setStyleSheet(
                        f"color: {c['border']}; padding: 1px 0; background: none;"
                    )

        # Segment quick-select buttons
        seg_btn_style = f"""
            QPushButton {{
                background: {c['accent_light']}; color: {c['accent']};
                border: 1px solid {c['border']}; border-radius: 3px;
                font-size: 10px; font-weight: 700; padding: 0 6px;
            }}
            QPushButton:hover {{ background: {c['accent']}; color: white; }}
        """
        seg_btn_style += TOOLTIP_CSS
        for i in range(self.seg_buttons_layout.count()):
            item = self.seg_buttons_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), QPushButton):
                item.widget().setStyleSheet(seg_btn_style)

        # Profile buttons
        prof_btn_style = f"""
            QPushButton {{
                background: {c['accent_light']}; color: {c['accent']};
                border: 1px solid {c['border']}; border-radius: 3px;
                font-size: 10px; font-weight: 600; padding: 2px 8px;
            }}
            QPushButton:hover {{ background: {c['accent']}; color: white; }}
        """
        for btn in getattr(self, '_profile_buttons', []):
            btn.setStyleSheet(prof_btn_style)

        # Sidebar cards
        for card in self._sidebar_cards:
            card.setStyleSheet(
                f"QFrame {{ background: {c['surface']}; "
                f"border: 1px solid {c['border']}; border-radius: 6px; }}"
            )
        # Card headers
        for hdr in getattr(self, '_card_headers_list', []):
            hdr.setStyleSheet(
                f"QLabel {{ color: {c['text']}; font-size: 12px; font-weight: 700; "
                f"border: none; border-bottom: 1px solid {c['border']}; "
                f"padding-bottom: 6px; }}"
            )

        # Sidebar labels
        self.sel_count_label.setStyleSheet(
            f"color: {c['accent']}; font-size: 28px; font-weight: 700;"
        )
        self.sel_total_label.setStyleSheet(
            f"color: {c['text_muted']}; font-size: 11px;"
        )
        self.sync_checkbox.setStyleSheet(
            f"QCheckBox {{ color: {c['text']}; font-size: 11px; border: none; }}"
            + TOOLTIP_CSS
        )
        self.sync_status_label.setStyleSheet(
            f"color: {c['text_muted']}; font-size: 10px; border: none;"
        )
        self.seg_hint_label.setStyleSheet(
            f"color: {c['text_muted']}; font-size: 10px; border: none;"
        )
        self.parse_status_label.setStyleSheet(
            f"color: {c['text_muted']}; font-size: 11px; border: none;"
        )

        # Profile widgets
        self.profile_combo.setStyleSheet(f"""
            QComboBox {{
                background: {c['bg']}; border: 1px solid {c['border']};
                border-radius: 4px; padding: 0 8px; color: {c['text']}; font-size: 11px;
            }}
            QComboBox::drop-down {{ border: none; }}
            QComboBox QAbstractItemView {{
                background: {c['surface']}; border: 1px solid {c['border']};
                color: {c['text']}; selection-background-color: {c['accent_light']};
            }}
        """)
        self.profile_name_input.setStyleSheet(f"""
            QLineEdit {{
                background: {c['bg']}; border: 1px solid {c['border']};
                border-radius: 3px; padding: 0 6px; color: {c['text']}; font-size: 10px;
            }}
        """)

        # LLM row buttons
        llm_fs = fs.get('llm_suggestion', FIELD_STATES['llm_suggestion'])
        self.llm_analyze_btn.setStyleSheet(f"""
            QPushButton {{
                background: {llm_fs['border']};
                color: white; border: none; border-radius: 4px;
                font-size: 12px; font-weight: 700; padding: 0 14px;
            }}
            QPushButton:hover {{ background: {llm_fs['text']}; }}
            QPushButton:disabled {{ background: {c['border']}; color: {c['text_muted']}; }}
        """)
        self.llm_cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: none; color: {c['text_muted']};
                border: 1px solid {c['border']}; border-radius: 4px;
                font-size: 11px; padding: 0 10px;
            }}
            QPushButton:hover {{ color: #c0392b; border-color: #c0392b; }}
        """)
        self.llm_accept_btn.setStyleSheet(f"""
            QPushButton {{
                background: {c['action_bg']}; color: white;
                border: none; border-radius: 4px;
                font-size: 11px; font-weight: 600; padding: 0 10px;
            }}
            QPushButton:hover {{ background: {c['action_hover']}; }}
        """)
        self.llm_dismiss_btn.setStyleSheet(f"""
            QPushButton {{
                background: none; color: {c['text_muted']};
                border: 1px solid {c['border']}; border-radius: 4px;
                font-size: 11px; padding: 0 10px;
            }}
            QPushButton:hover {{ color: #c0392b; border-color: #c0392b; }}
        """)
        self.llm_progress.setStyleSheet(f"""
            QProgressBar {{
                background: {c['bg']}; border: 1px solid {c['border']};
                border-radius: 4px; text-align: center; font-size: 10px;
                color: {c['text_muted']};
            }}
            QProgressBar::chunk {{
                background: {llm_fs['border']};
                border-radius: 3px;
            }}
        """)

        # WI-058: Pagination bar
        page_btn_style = f"""
            QPushButton {{
                background: {c['accent_light']}; color: {c['accent']};
                border: 1px solid {c['border']}; border-radius: 3px;
                font-size: 11px; font-weight: 600; padding: 0 10px;
            }}
            QPushButton:hover {{ background: {c['accent']}; color: white; }}
            QPushButton:disabled {{ background: {c['bg']}; color: {c['text_muted']}; }}
        """
        self.page_prev_btn.setStyleSheet(page_btn_style)
        self.page_next_btn.setStyleSheet(page_btn_style)
        self.page_label.setStyleSheet(f"color: {c['text_muted']}; font-size: 11px; font-weight: 600;")

    def get_selections(self) -> list[tuple[int, str, int, str, str]]:
        """WI-058: Return selections from data model (covers all pages)."""
        # Save current page widget states first
        self._save_page_to_model()
        return [
            (fi.msg_index, fi.segment_name, fi.field_index, fi.path, fi.state)
            for fi in self._all_fields
            if fi.is_selected()
        ]

    def get_all_value_widgets(self) -> list[ValueWidget]:
        """Return all value widgets for external access (e.g. auto-preselection)."""
        return self._all_value_widgets
