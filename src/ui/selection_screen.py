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
from PySide6.QtGui import QCursor, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.config.field_definitions import DEFAULT_PII_FIELDS
from src.config.field_descriptions import get_field_tooltip
from src.parser.hl7_parser import HL7Field, HL7Message, HL7Segment, ParseResult, tokenize_field_value
from src.ui.theme import COLORS_LIGHT, FIELD_STATES, WARNINGS


MONO_FONT = QFont("Cascadia Code", 11)
MONO_FONT.setStyleHint(QFont.StyleHint.Monospace)

MONO_FONT_SMALL = QFont("Cascadia Code", 10)
MONO_FONT_SMALL.setStyleHint(QFont.StyleHint.Monospace)

# Selection states
STATE_NEUTRAL = "neutral"
STATE_AUTO = "auto_detected"
STATE_MANUAL = "manually_selected"
STATE_LLM = "llm_suggestion"


class ValueWidget(QLabel):
    """Smallest clickable unit — a single component/subcomponent/repetition value."""

    clicked = Signal()

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
        self._apply_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle()
            self.clicked.emit()
        super().mousePressEvent(event)

    def set_state(self, state: str):
        self.state = state
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
        s = FIELD_STATES[self.state]
        bg = s["background"]
        border = s["border"]
        text_color = s["text"] or COLORS_LIGHT["text"]
        self.setStyleSheet(
            f"QLabel {{ background: {bg}; border: 1px solid {border}; "
            f"color: {text_color}; padding: 1px 3px; border-radius: 2px; }}"
        )


def _make_separator_label(char: str) -> QLabel:
    """Create a styled separator label (^, ~, &, |)."""
    label = QLabel(char)
    label.setFont(MONO_FONT)
    label.setStyleSheet(
        f"color: {COLORS_LIGHT['border']}; padding: 1px 0; background: none;"
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
        self._all_value_widgets: list[ValueWidget] = []
        self._segment_lines: list[SegmentLineWidget] = []
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # --- Legend bar ---
        legend = QWidget()
        legend.setStyleSheet(
            f"background: {COLORS_LIGHT['surface']}; "
            f"border-bottom: 1px solid {COLORS_LIGHT['border']};"
        )
        legend_layout = QHBoxLayout(legend)
        legend_layout.setContentsMargins(28, 8, 28, 8)
        legend_layout.setSpacing(18)

        bold_label = QLabel("<b>Legend:</b>")
        bold_label.setStyleSheet(f"color: {COLORS_LIGHT['text']}; font-size: 12px;")
        legend_layout.addWidget(bold_label)

        for state_key, label_text in [
            ("auto_detected", "Auto-detected"),
            ("manually_selected", "Manually selected"),
            ("llm_suggestion", "LLM suggestion"),
            ("neutral", "Not selected"),
        ]:
            s = FIELD_STATES[state_key]
            swatch = QLabel("  ")
            swatch.setFixedSize(14, 14)
            swatch.setStyleSheet(
                f"background: {s['background']}; border: 1px solid {s['border']}; border-radius: 2px;"
            )
            legend_layout.addWidget(swatch)
            lbl = QLabel(label_text)
            lbl.setStyleSheet(f"color: {COLORS_LIGHT['text_muted']}; font-size: 11px;")
            legend_layout.addWidget(lbl)

        legend_layout.addStretch()
        outer.addWidget(legend)

        # --- Main content: two-column layout ---
        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(28, 12, 28, 12)
        content_layout.setSpacing(16)

        # LEFT: HL7 inline view (scrollable)
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

        content_layout.addWidget(self.scroll_area, 3)

        # RIGHT: Sidebar
        sidebar = QWidget()
        sidebar.setFixedWidth(240)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(12)

        # Selection counter card
        counter_card = self._make_card("Selection Summary")
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
        self.sync_checkbox = QCheckBox("Auswahl auf alle\nMeldungen übertragen")
        self.sync_checkbox.setStyleSheet(
            f"QCheckBox {{ color: {COLORS_LIGHT['text']}; font-size: 11px; border: none; }}"
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

        # Parse status card
        status_card = self._make_card("Parse Status")
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
            f"color: {COLORS_LIGHT['text']}; font-size: 12px; font-weight: 700; "
            f"border: none; border-bottom: 1px solid {COLORS_LIGHT['border']}; "
            f"padding-bottom: 6px;"
        )
        card_layout.addWidget(hdr)
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
        siblings = self._path_index.get(source.path, [])
        for vw in siblings:
            if vw is not source:
                vw.set_state(source.state)

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
        self._render()
        self._build_path_index()
        if result.is_valid_hl7:
            self._apply_auto_preselection()
        self._update_counter()
        self._update_sync_status()

    def _render(self):
        """Render the HL7 inline view with clickable fields."""
        # Clear existing content
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

        # Render each message
        for msg_idx, msg in enumerate(r.messages):
            if msg_idx > 0:
                sep = QFrame()
                sep.setFrameShape(QFrame.Shape.HLine)
                sep.setStyleSheet(f"color: {COLORS_LIGHT['border']}; margin: 8px 0;")
                self.hl7_layout.addWidget(sep)

                # Show non-HL7 lines between messages
                for ln, content in r.non_hl7_lines:
                    w = NonHL7LineWidget(ln, content)
                    self.hl7_layout.addWidget(w)

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
                    self._all_value_widgets.append(vw)

        # Show non-HL7 lines at the end for single-message case
        if len(r.messages) == 1 and r.non_hl7_lines:
            for ln, content in r.non_hl7_lines:
                w = NonHL7LineWidget(ln, content)
                self.hl7_layout.addWidget(w)

        self.hl7_layout.addStretch()
        self._update_parse_status()

    def _on_value_clicked(self, vw: ValueWidget):
        """Handle a single value widget click — sync + update counter."""
        self._sync_to_others(vw)
        self._update_counter()

    def _on_segment_toggled(self, segment_line: SegmentLineWidget):
        """Handle segment-level toggle — sync + update counter."""
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

    def _apply_auto_preselection(self):
        """WI-004: Auto-preselect PII fields from Section 4.1 (Amber state).
        Only applied when valid HL7 is detected. Does not preselect on invalid input.
        """
        for vw in self._all_value_widgets:
            key = (vw.field.segment_name, vw.field.field_index)
            if key in DEFAULT_PII_FIELDS:
                vw.set_state(STATE_AUTO)

    def _update_counter(self):
        total = len(self._all_value_widgets)
        selected = sum(1 for vw in self._all_value_widgets if vw.is_selected())
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

    def get_selections(self) -> list[tuple[int, str, int, str, str]]:
        """Return list of (msg_index, segment_name, field_index, path, state) for selected values."""
        return [
            (vw.msg_index, vw.field.segment_name, vw.field.field_index, vw.path, vw.state)
            for vw in self._all_value_widgets
            if vw.is_selected()
        ]

    def get_all_value_widgets(self) -> list[ValueWidget]:
        """Return all value widgets for external access (e.g. auto-preselection)."""
        return self._all_value_widgets
