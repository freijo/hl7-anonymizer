"""WI-007: Step 3 — Settings screen.

Mask character setting with live preview.
DoD: Änderung wird sofort bei nächster Anonymisierung angewendet.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.config.config_file import load_config, save_config
from src.config.regex_patterns import PatternRegistry
from src.engine.llm_client import LLMConfig, test_connection
from src.ui.theme import COLORS_LIGHT, theme_manager

DEFAULT_MASK = "***"


class SettingsScreen(QWidget):
    """Step 3: Anonymization settings."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pattern_registry = PatternRegistry()
        self.llm_config = LLMConfig()
        self._build_ui()
        self._load_from_config()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        scroll_content = QWidget()
        outer = QVBoxLayout(scroll_content)
        outer.setContentsMargins(28, 16, 28, 16)
        outer.setSpacing(16)
        scroll.setWidget(scroll_content)
        root.addWidget(scroll)

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

        # WI-028: Reset button
        self.reset_btn = QPushButton("Reset to Default")
        self.reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_btn.setFixedHeight(32)
        self.reset_btn.setStyleSheet(f"""
            QPushButton {{
                background: none; color: {COLORS_LIGHT['text_muted']};
                border: 1px solid {COLORS_LIGHT['border']}; border-radius: 4px;
                padding: 0 16px; font-size: 12px;
            }}
            QPushButton:hover {{
                color: {COLORS_LIGHT['text']}; border-color: {COLORS_LIGHT['accent']};
            }}
        """)
        self.reset_btn.clicked.connect(self._reset_to_default)
        row_layout.addWidget(self.reset_btn)

        # WI-045: Export/Import config buttons
        btn_style = f"""
            QPushButton {{
                background: none; color: {COLORS_LIGHT['text_muted']};
                border: 1px solid {COLORS_LIGHT['border']}; border-radius: 4px;
                padding: 0 12px; font-size: 11px;
            }}
            QPushButton:hover {{
                color: {COLORS_LIGHT['text']}; border-color: {COLORS_LIGHT['accent']};
            }}
        """
        self.export_cfg_btn = QPushButton("Export Config")
        self.export_cfg_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_cfg_btn.setFixedHeight(32)
        self.export_cfg_btn.setStyleSheet(btn_style)
        self.export_cfg_btn.clicked.connect(self._export_config)
        row_layout.addWidget(self.export_cfg_btn)

        self.import_cfg_btn = QPushButton("Import Config")
        self.import_cfg_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.import_cfg_btn.setFixedHeight(32)
        self.import_cfg_btn.setStyleSheet(btn_style)
        self.import_cfg_btn.clicked.connect(self._import_config)
        row_layout.addWidget(self.import_cfg_btn)

        row_layout.addStretch()
        card_layout.addWidget(input_row)

        outer.addWidget(card)

        # --- WI-023: Length strategy card ---
        len_card = QFrame()
        len_card.setStyleSheet(
            f"QFrame {{ background: {COLORS_LIGHT['surface']}; "
            f"border: 1px solid {COLORS_LIGHT['border']}; border-radius: 6px; }}"
        )
        len_layout = QVBoxLayout(len_card)
        len_layout.setContentsMargins(16, 12, 16, 14)
        len_layout.setSpacing(8)

        len_title = QLabel("Length Strategy")
        len_title.setStyleSheet(
            f"color: {COLORS_LIGHT['text']}; font-size: 13px; font-weight: 700; "
            f"border: none; border-bottom: 1px solid {COLORS_LIGHT['border']}; "
            f"padding-bottom: 6px;"
        )
        len_layout.addWidget(len_title)

        self.length_preserve_cb = QCheckBox("Preserve original value length")
        self.length_preserve_cb.setStyleSheet(
            f"color: {COLORS_LIGHT['text']}; font-size: 12px; border: none;"
        )
        self.length_preserve_cb.setToolTip(
            "When enabled, the mask character is repeated to match the\n"
            "length of each original value. e.g. 'Müller' → '******'"
        )
        self.length_preserve_cb.toggled.connect(self._on_mask_changed)
        len_layout.addWidget(self.length_preserve_cb)

        len_desc = QLabel(
            "Repeats the first character of the mask pattern to match "
            "each value's original length."
        )
        len_desc.setWordWrap(True)
        len_desc.setStyleSheet(
            f"color: {COLORS_LIGHT['text_muted']}; font-size: 11px; border: none;"
        )
        len_layout.addWidget(len_desc)
        outer.addWidget(len_card)

        # --- WI-024: Consistent pseudonymization card ---
        pseudo_card = QFrame()
        pseudo_card.setStyleSheet(
            f"QFrame {{ background: {COLORS_LIGHT['surface']}; "
            f"border: 1px solid {COLORS_LIGHT['border']}; border-radius: 6px; }}"
        )
        pseudo_layout = QVBoxLayout(pseudo_card)
        pseudo_layout.setContentsMargins(16, 12, 16, 14)
        pseudo_layout.setSpacing(8)

        pseudo_title = QLabel("Consistent Pseudonymization")
        pseudo_title.setStyleSheet(
            f"color: {COLORS_LIGHT['text']}; font-size: 13px; font-weight: 700; "
            f"border: none; border-bottom: 1px solid {COLORS_LIGHT['border']}; "
            f"padding-bottom: 6px;"
        )
        pseudo_layout.addWidget(pseudo_title)

        self.consistent_cb = QCheckBox("Same value → same pseudonym")
        self.consistent_cb.setStyleSheet(
            f"color: {COLORS_LIGHT['text']}; font-size: 12px; border: none;"
        )
        self.consistent_cb.setToolTip(
            "When enabled, identical original values receive the same\n"
            "pseudonym across all messages (e.g. 'Müller' → 'ANON-1' everywhere)."
        )
        pseudo_layout.addWidget(self.consistent_cb)

        pseudo_desc = QLabel(
            "Generates numbered pseudonyms (ANON-1, ANON-2, ...) so that "
            "the same original value always maps to the same replacement."
        )
        pseudo_desc.setWordWrap(True)
        pseudo_desc.setStyleSheet(
            f"color: {COLORS_LIGHT['text_muted']}; font-size: 11px; border: none;"
        )
        pseudo_layout.addWidget(pseudo_desc)
        outer.addWidget(pseudo_card)

        # --- Auto-Detection card (PII + Regex) ---
        regex_card = QFrame()
        regex_card.setStyleSheet(
            f"QFrame {{ background: {COLORS_LIGHT['surface']}; "
            f"border: 1px solid {COLORS_LIGHT['border']}; border-radius: 6px; }}"
        )
        regex_layout = QVBoxLayout(regex_card)
        regex_layout.setContentsMargins(16, 12, 16, 14)
        regex_layout.setSpacing(8)

        regex_title = QLabel("Auto-Detection")
        regex_title.setStyleSheet(
            f"color: {COLORS_LIGHT['text']}; font-size: 13px; font-weight: 700; "
            f"border: none; border-bottom: 1px solid {COLORS_LIGHT['border']}; "
            f"padding-bottom: 6px;"
        )
        regex_layout.addWidget(regex_title)

        regex_desc = QLabel(
            "Controls which fields are auto-selected (amber) in Step 2. "
            "PII field definitions select by segment/field position. "
            "Regex patterns select by matching the field value."
        )
        regex_desc.setWordWrap(True)
        regex_desc.setStyleSheet(
            f"color: {COLORS_LIGHT['text_muted']}; font-size: 11px; border: none;"
        )
        regex_layout.addWidget(regex_desc)

        # PII field definitions toggle
        self.pii_fields_cb = QCheckBox("PII field definitions (PID, NK1, PV1, IN1, GT1, ...)")
        self.pii_fields_cb.setChecked(True)
        self.pii_fields_cb.setStyleSheet(
            f"color: {COLORS_LIGHT['text']}; font-size: 12px; font-weight: 600; border: none;"
        )
        self.pii_fields_cb.setToolTip(
            "Auto-select known PII fields by segment and field position\n"
            "(e.g. PID.5 Patient Name, NK1.2 Name, NK1.5 Phone, ...)."
        )
        regex_layout.addWidget(self.pii_fields_cb)

        sep = QLabel("Regex Patterns:")
        sep.setStyleSheet(
            f"color: {COLORS_LIGHT['text']}; font-size: 12px; font-weight: 600; "
            f"border: none; margin-top: 4px;"
        )
        regex_layout.addWidget(sep)

        # Default pattern checkboxes
        self._pattern_checkboxes: list[QCheckBox] = []
        for pat in self.pattern_registry.default_patterns:
            cb = QCheckBox(f"{pat.name}  ({pat.pattern})")
            cb.setChecked(pat.enabled)
            cb.setStyleSheet(
                f"color: {COLORS_LIGHT['text']}; font-size: 11px; border: none;"
            )
            cb.setFont(QFont("Cascadia Code", 9))
            cb.toggled.connect(lambda checked, p=pat: setattr(p, 'enabled', checked))
            regex_layout.addWidget(cb)
            self._pattern_checkboxes.append(cb)

        # Custom patterns area
        self._custom_patterns_container = QVBoxLayout()
        self._custom_patterns_container.setSpacing(4)
        regex_layout.addLayout(self._custom_patterns_container)

        # Add custom pattern row
        add_row = QWidget()
        add_row.setStyleSheet("border: none;")
        add_row_layout = QHBoxLayout(add_row)
        add_row_layout.setContentsMargins(0, 4, 0, 0)
        add_row_layout.setSpacing(6)

        self._custom_name_input = QLineEdit()
        self._custom_name_input.setPlaceholderText("Name")
        self._custom_name_input.setFixedWidth(120)
        self._custom_name_input.setFixedHeight(28)
        self._custom_name_input.setStyleSheet(f"""
            QLineEdit {{
                background: {COLORS_LIGHT['bg']}; border: 1px solid {COLORS_LIGHT['border']};
                border-radius: 3px; padding: 0 6px; color: {COLORS_LIGHT['text']}; font-size: 11px;
            }}
        """)
        add_row_layout.addWidget(self._custom_name_input)

        self._custom_regex_input = QLineEdit()
        self._custom_regex_input.setPlaceholderText("Regex pattern")
        self._custom_regex_input.setFixedHeight(28)
        self._custom_regex_input.setFont(QFont("Cascadia Code", 10))
        self._custom_regex_input.setStyleSheet(f"""
            QLineEdit {{
                background: {COLORS_LIGHT['bg']}; border: 1px solid {COLORS_LIGHT['border']};
                border-radius: 3px; padding: 0 6px; color: {COLORS_LIGHT['text']}; font-size: 11px;
            }}
        """)
        add_row_layout.addWidget(self._custom_regex_input)

        add_btn = QPushButton("+ Add")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setFixedHeight(28)
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS_LIGHT['accent']}; color: white;
                border: none; border-radius: 3px; padding: 0 12px; font-size: 11px; font-weight: 700;
            }}
            QPushButton:hover {{ background: {COLORS_LIGHT['accent_hover']}; }}
        """)
        add_btn.clicked.connect(self._add_custom_pattern)
        add_row_layout.addWidget(add_btn)

        regex_layout.addWidget(add_row)

        self._regex_error_label = QLabel("")
        self._regex_error_label.setStyleSheet(
            "color: #c0392b; font-size: 11px; border: none;"
        )
        self._regex_error_label.hide()
        regex_layout.addWidget(self._regex_error_label)

        outer.addWidget(regex_card)

        # --- WI-030/WI-032: LLM Settings card ---
        llm_card = QFrame()
        llm_card.setStyleSheet(
            f"QFrame {{ background: {COLORS_LIGHT['surface']}; "
            f"border: 1px solid {COLORS_LIGHT['border']}; border-radius: 6px; }}"
        )
        llm_layout = QVBoxLayout(llm_card)
        llm_layout.setContentsMargins(16, 12, 16, 14)
        llm_layout.setSpacing(8)

        llm_title = QLabel("LLM Analysis")
        llm_title.setStyleSheet(
            f"color: {COLORS_LIGHT['text']}; font-size: 13px; font-weight: 700; "
            f"border: none; border-bottom: 1px solid {COLORS_LIGHT['border']}; "
            f"padding-bottom: 6px;"
        )
        llm_layout.addWidget(llm_title)

        llm_desc = QLabel(
            "Use a local LLM to detect PII in free-text fields. "
            "Results appear as purple suggestions in Step 2."
        )
        llm_desc.setWordWrap(True)
        llm_desc.setStyleSheet(
            f"color: {COLORS_LIGHT['text_muted']}; font-size: 11px; border: none;"
        )
        llm_layout.addWidget(llm_desc)

        # Mode selector
        mode_row = QWidget()
        mode_row.setStyleSheet("border: none;")
        mode_row_layout = QHBoxLayout(mode_row)
        mode_row_layout.setContentsMargins(0, 4, 0, 0)
        mode_row_layout.setSpacing(8)

        mode_label = QLabel("Mode:")
        mode_label.setStyleSheet(
            f"color: {COLORS_LIGHT['text']}; font-size: 12px; font-weight: 600;"
        )
        mode_row_layout.addWidget(mode_label)

        self.llm_mode_combo = QComboBox()
        self.llm_mode_combo.addItems(["None", "Local API"])
        self.llm_mode_combo.setFixedHeight(30)
        self.llm_mode_combo.setFixedWidth(160)
        self.llm_mode_combo.setStyleSheet(f"""
            QComboBox {{
                background: {COLORS_LIGHT['bg']}; border: 1px solid {COLORS_LIGHT['border']};
                border-radius: 4px; padding: 0 8px; color: {COLORS_LIGHT['text']}; font-size: 12px;
            }}
            QComboBox:focus {{ border-color: {COLORS_LIGHT['accent']}; }}
            QComboBox::drop-down {{ border: none; }}
            QComboBox QAbstractItemView {{
                background: {COLORS_LIGHT['surface']}; border: 1px solid {COLORS_LIGHT['border']};
                color: {COLORS_LIGHT['text']}; selection-background-color: {COLORS_LIGHT['accent_light']};
            }}
        """)
        self.llm_mode_combo.currentTextChanged.connect(self._on_llm_mode_changed)
        mode_row_layout.addWidget(self.llm_mode_combo)
        mode_row_layout.addStretch()
        llm_layout.addWidget(mode_row)

        # API settings container (shown only for Local API)
        self._llm_api_container = QWidget()
        self._llm_api_container.setStyleSheet("border: none;")
        api_layout = QVBoxLayout(self._llm_api_container)
        api_layout.setContentsMargins(0, 4, 0, 0)
        api_layout.setSpacing(6)

        # Host + Port row
        hp_row = QWidget()
        hp_layout = QHBoxLayout(hp_row)
        hp_layout.setContentsMargins(0, 0, 0, 0)
        hp_layout.setSpacing(8)

        hp_layout.addWidget(self._setting_label("Host:"))
        self.llm_host_input = self._setting_input("http://localhost", 200)
        hp_layout.addWidget(self.llm_host_input)

        hp_layout.addWidget(self._setting_label("Port:"))
        self.llm_port_input = self._setting_input("11434", 70)
        hp_layout.addWidget(self.llm_port_input)
        hp_layout.addStretch()
        api_layout.addWidget(hp_row)

        # Model + API Key row
        mk_row = QWidget()
        mk_layout = QHBoxLayout(mk_row)
        mk_layout.setContentsMargins(0, 0, 0, 0)
        mk_layout.setSpacing(8)

        mk_layout.addWidget(self._setting_label("Model:"))
        self.llm_model_input = self._setting_input("", 200)
        self.llm_model_input.setPlaceholderText("e.g. llama3, mistral")
        mk_layout.addWidget(self.llm_model_input)

        mk_layout.addWidget(self._setting_label("API Key:"))
        self.llm_apikey_input = self._setting_input("", 160)
        self.llm_apikey_input.setPlaceholderText("optional")
        self.llm_apikey_input.setEchoMode(QLineEdit.EchoMode.Password)
        mk_layout.addWidget(self.llm_apikey_input)
        mk_layout.addStretch()
        api_layout.addWidget(mk_row)

        # Connection test button + status
        test_row = QWidget()
        test_row_layout = QHBoxLayout(test_row)
        test_row_layout.setContentsMargins(0, 4, 0, 0)
        test_row_layout.setSpacing(8)

        self.llm_test_btn = QPushButton("Test Connection")
        self.llm_test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.llm_test_btn.setFixedHeight(30)
        self.llm_test_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS_LIGHT['accent']}; color: white;
                border: none; border-radius: 4px; padding: 0 16px;
                font-size: 12px; font-weight: 700;
            }}
            QPushButton:hover {{ background: {COLORS_LIGHT['accent_hover']}; }}
        """)
        self.llm_test_btn.clicked.connect(self._test_llm_connection)
        test_row_layout.addWidget(self.llm_test_btn)

        self.llm_status_label = QLabel("")
        self.llm_status_label.setWordWrap(True)
        self.llm_status_label.setStyleSheet(
            f"color: {COLORS_LIGHT['text_muted']}; font-size: 11px;"
        )
        test_row_layout.addWidget(self.llm_status_label, 1)
        api_layout.addWidget(test_row)

        # WI-036: Prompt template
        prompt_label = QLabel("Prompt Template:")
        prompt_label.setStyleSheet(
            f"color: {COLORS_LIGHT['text']}; font-size: 12px; font-weight: 600;"
        )
        api_layout.addWidget(prompt_label)

        self.llm_prompt_edit = QPlainTextEdit()
        self.llm_prompt_edit.setFont(QFont("Cascadia Code", 9))
        self.llm_prompt_edit.setFixedHeight(80)
        self.llm_prompt_edit.setStyleSheet(f"""
            QPlainTextEdit {{
                background: {COLORS_LIGHT['bg']}; border: 1px solid {COLORS_LIGHT['border']};
                border-radius: 4px; padding: 6px; color: {COLORS_LIGHT['text']}; font-size: 11px;
            }}
            QPlainTextEdit:focus {{ border-color: {COLORS_LIGHT['accent']}; }}
        """)
        from src.engine.llm_client import DEFAULT_PROMPT
        self.llm_prompt_edit.setPlainText(DEFAULT_PROMPT)
        api_layout.addWidget(self.llm_prompt_edit)

        llm_layout.addWidget(self._llm_api_container)
        self._llm_api_container.hide()

        outer.addWidget(llm_card)

        outer.addStretch()

        self._on_mask_changed()

    def _setting_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {COLORS_LIGHT['text']}; font-size: 12px; font-weight: 600;"
        )
        return lbl

    def _setting_input(self, default: str, width: int) -> QLineEdit:
        inp = QLineEdit(default)
        inp.setFixedHeight(28)
        inp.setFixedWidth(width)
        inp.setStyleSheet(f"""
            QLineEdit {{
                background: {COLORS_LIGHT['bg']}; border: 1px solid {COLORS_LIGHT['border']};
                border-radius: 3px; padding: 0 6px; color: {COLORS_LIGHT['text']}; font-size: 12px;
            }}
            QLineEdit:focus {{ border-color: {COLORS_LIGHT['accent']}; }}
        """)
        return inp

    def _on_llm_mode_changed(self, text: str):
        is_api = text == "Local API"
        self._llm_api_container.setVisible(is_api)
        self.llm_config.mode = "local_api" if is_api else "none"

    def _test_llm_connection(self):
        self._sync_llm_config()
        self.llm_status_label.setText("Testing...")
        self.llm_status_label.setStyleSheet(
            f"color: {COLORS_LIGHT['text_muted']}; font-size: 11px;"
        )
        # Run synchronously (short timeout)
        ok, msg = test_connection(self.llm_config)
        if ok:
            self.llm_status_label.setText(msg)
            self.llm_status_label.setStyleSheet(
                "color: #276749; font-size: 11px; font-weight: 600;"
            )
        else:
            self.llm_status_label.setText(msg)
            self.llm_status_label.setStyleSheet(
                "color: #c0392b; font-size: 11px;"
            )

    def _sync_llm_config(self):
        """Sync UI inputs to LLMConfig object."""
        self.llm_config.host = self.llm_host_input.text().strip() or "http://localhost"
        try:
            self.llm_config.port = int(self.llm_port_input.text().strip())
        except ValueError:
            self.llm_config.port = 11434
        self.llm_config.model_name = self.llm_model_input.text().strip()
        self.llm_config.api_key = self.llm_apikey_input.text().strip()
        self.llm_config.prompt_template = self.llm_prompt_edit.toPlainText().strip()
        mode_text = self.llm_mode_combo.currentText()
        self.llm_config.mode = "local_api" if mode_text == "Local API" else "none"

    def get_llm_config(self) -> LLMConfig:
        """Return current LLM config, synced from UI."""
        self._sync_llm_config()
        return self.llm_config

    def _on_mask_changed(self):
        mask = self.mask_input.text() or DEFAULT_MASK
        if self.length_preserve_cb.isChecked():
            ch = mask[0] if mask else "*"
            self.preview_label.setText(
                f'Preview: Müller^Hans → {ch * 6}^{ch * 4}'
            )
        else:
            self.preview_label.setText(f'Preview: Müller^Hans → {mask}^{mask}')

    def _add_custom_pattern(self):
        """WI-021: Add a user-defined regex pattern."""
        name = self._custom_name_input.text().strip() or "Custom"
        pattern = self._custom_regex_input.text().strip()
        if not pattern:
            return
        result = self.pattern_registry.add_custom(name, pattern)
        if result is None:
            self._regex_error_label.setText(f"Invalid regex: {pattern}")
            self._regex_error_label.show()
            return
        self._regex_error_label.hide()
        self._custom_name_input.clear()
        self._custom_regex_input.clear()
        self._rebuild_custom_list()

    def _rebuild_custom_list(self):
        """Rebuild the custom patterns UI from registry."""
        while self._custom_patterns_container.count():
            item = self._custom_patterns_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for idx, pat in enumerate(self.pattern_registry.custom_patterns):
            row = QWidget()
            row.setStyleSheet("border: none;")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(6)

            cb = QCheckBox(f"{pat.name}  ({pat.pattern})")
            cb.setChecked(pat.enabled)
            cb.setFont(QFont("Cascadia Code", 9))
            cb.setStyleSheet(
                f"color: {COLORS_LIGHT['accent']}; font-size: 11px; border: none;"
            )
            cb.toggled.connect(lambda checked, p=pat: setattr(p, 'enabled', checked))
            row_layout.addWidget(cb)

            del_btn = QPushButton("x")
            del_btn.setFixedSize(20, 20)
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            del_btn.setStyleSheet(f"""
                QPushButton {{
                    background: none; color: {COLORS_LIGHT['text_muted']};
                    border: 1px solid {COLORS_LIGHT['border']}; border-radius: 3px;
                    font-size: 10px;
                }}
                QPushButton:hover {{ color: #c0392b; }}
            """)
            del_btn.clicked.connect(lambda _, i=idx: self._remove_custom_pattern(i))
            row_layout.addWidget(del_btn)
            row_layout.addStretch()

            self._custom_patterns_container.addWidget(row)

    def _remove_custom_pattern(self, index: int):
        self.pattern_registry.remove_custom(index)
        self._rebuild_custom_list()

    def _reset_to_default(self):
        """WI-028: Reset all settings to defaults."""
        self.mask_input.setText(DEFAULT_MASK)
        self.length_preserve_cb.setChecked(False)
        self.consistent_cb.setChecked(False)
        self.pii_fields_cb.setChecked(True)
        # Reset regex patterns
        for pat, cb in zip(self.pattern_registry.default_patterns, self._pattern_checkboxes):
            pat.enabled = True
            cb.setChecked(True)
        self.pattern_registry._custom.clear()
        self._rebuild_custom_list()
        # Reset LLM
        self.llm_mode_combo.setCurrentIndex(0)
        self.llm_host_input.setText("http://localhost")
        self.llm_port_input.setText("11434")
        self.llm_model_input.clear()
        self.llm_apikey_input.clear()
        from src.engine.llm_client import DEFAULT_PROMPT
        self.llm_prompt_edit.setPlainText(DEFAULT_PROMPT)
        self.llm_config = LLMConfig()

    def _export_config(self):
        """WI-045: Export config to user-chosen JSON file."""
        import json
        self._sync_llm_config()
        data = {
            "mask": self.mask_input.text(),
            "length_preserve": self.length_preserve_cb.isChecked(),
            "consistent": self.consistent_cb.isChecked(),
            "pii_fields_enabled": self.pii_fields_cb.isChecked(),
            "custom_regex_patterns": self.pattern_registry.to_dict_list(),
            "llm": self.llm_config.to_dict(),
        }
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Configuration", "hl7anon_config.json",
            "JSON files (*.json);;All files (*)",
        )
        if path:
            from pathlib import Path
            Path(path).write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
            )

    def _import_config(self):
        """WI-045: Import config from user-chosen JSON file."""
        import json
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Configuration", "",
            "JSON files (*.json);;All files (*)",
        )
        if not path:
            return
        try:
            from pathlib import Path
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        if not isinstance(data, dict):
            return
        # Apply imported settings
        self.mask_input.setText(data.get("mask", DEFAULT_MASK))
        self.length_preserve_cb.setChecked(data.get("length_preserve", False))
        self.consistent_cb.setChecked(data.get("consistent", False))
        self.pii_fields_cb.setChecked(data.get("pii_fields_enabled", True))
        self.pattern_registry.load_custom(data.get("custom_regex_patterns", []))
        self._rebuild_custom_list()
        llm_data = data.get("llm", {})
        if llm_data:
            self.llm_config = LLMConfig.from_dict(llm_data)
            idx = 1 if self.llm_config.mode == "local_api" else 0
            self.llm_mode_combo.setCurrentIndex(idx)
            self.llm_host_input.setText(self.llm_config.host)
            self.llm_port_input.setText(str(self.llm_config.port))
            self.llm_model_input.setText(self.llm_config.model_name)
            self.llm_apikey_input.setText(self.llm_config.api_key)
            self.llm_prompt_edit.setPlainText(self.llm_config.prompt_template)

    def get_mask(self) -> str:
        """Return the current mask pattern. Falls back to default if empty."""
        return self.mask_input.text() or DEFAULT_MASK

    def get_length_preserve(self) -> bool:
        """WI-023: Whether to preserve original value length."""
        return self.length_preserve_cb.isChecked()

    def get_consistent(self) -> bool:
        """WI-024: Whether to use consistent pseudonymization."""
        return self.consistent_cb.isChecked()

    def get_pii_fields_enabled(self) -> bool:
        """Whether PII field definitions are active for auto-detection."""
        return self.pii_fields_cb.isChecked()

    def _load_from_config(self):
        """WI-022: Load settings from config file."""
        cfg = load_config()
        self.mask_input.setText(cfg.get("mask", DEFAULT_MASK))
        self.length_preserve_cb.setChecked(cfg.get("length_preserve", False))
        self.consistent_cb.setChecked(cfg.get("consistent", False))
        self.pii_fields_cb.setChecked(cfg.get("pii_fields_enabled", True))
        self.pattern_registry.load_custom(cfg.get("custom_regex_patterns", []))
        self._rebuild_custom_list()
        # LLM config
        llm_data = cfg.get("llm", {})
        if llm_data:
            self.llm_config = LLMConfig.from_dict(llm_data)
            idx = 1 if self.llm_config.mode == "local_api" else 0
            self.llm_mode_combo.setCurrentIndex(idx)
            self.llm_host_input.setText(self.llm_config.host)
            self.llm_port_input.setText(str(self.llm_config.port))
            self.llm_model_input.setText(self.llm_config.model_name)
            self.llm_apikey_input.setText(self.llm_config.api_key)
            self.llm_prompt_edit.setPlainText(self.llm_config.prompt_template)

    def refresh_theme(self):
        """WI-040: Re-apply all inline stylesheets with current theme colors."""
        c = theme_manager.current_colors()

        # Cards (QFrame children)
        for frame in self.findChildren(QFrame):
            frame.setStyleSheet(
                f"QFrame {{ background: {c['surface']}; "
                f"border: 1px solid {c['border']}; border-radius: 6px; }}"
            )

        # All QLabels
        for label in self.findChildren(QLabel):
            text = label.text()
            # Card titles (bold, border-bottom)
            if label.font().weight() >= QFont.Weight.Bold or label.font().bold():
                label.setStyleSheet(
                    f"color: {c['text']}; font-size: 13px; font-weight: 700; "
                    f"border: none; border-bottom: 1px solid {c['border']}; "
                    f"padding-bottom: 6px;"
                )
            elif "Preview:" in text:
                label.setStyleSheet(f"color: {c['text_muted']}; font-size: 11px;")
            elif label.wordWrap() or label.styleSheet() and "11px" in label.styleSheet():
                label.setStyleSheet(
                    f"color: {c['text_muted']}; font-size: 11px; border: none;"
                )
            else:
                label.setStyleSheet(f"color: {c['text']}; border: none;")

        # QLineEdit inputs
        for inp in self.findChildren(QLineEdit):
            inp.setStyleSheet(f"""
                QLineEdit {{
                    background: {c['bg']}; border: 1px solid {c['border']};
                    border-radius: 3px; padding: 0 6px; color: {c['text']}; font-size: 12px;
                }}
                QLineEdit:focus {{ border-color: {c['accent']}; }}
            """)

        # QCheckBox
        for cb in self.findChildren(QCheckBox):
            cb.setStyleSheet(f"color: {c['text']}; font-size: 12px; border: none;")

        # QComboBox
        for combo in self.findChildren(QComboBox):
            combo.setStyleSheet(f"""
                QComboBox {{
                    background: {c['bg']}; border: 1px solid {c['border']};
                    border-radius: 4px; padding: 0 8px; color: {c['text']}; font-size: 12px;
                }}
                QComboBox:focus {{ border-color: {c['accent']}; }}
                QComboBox::drop-down {{ border: none; }}
                QComboBox QAbstractItemView {{
                    background: {c['surface']}; border: 1px solid {c['border']};
                    color: {c['text']}; selection-background-color: {c['accent_light']};
                }}
            """)

        # QPlainTextEdit (prompt)
        for pte in self.findChildren(QPlainTextEdit):
            pte.setStyleSheet(f"""
                QPlainTextEdit {{
                    background: {c['bg']}; border: 1px solid {c['border']};
                    border-radius: 4px; padding: 6px; color: {c['text']}; font-size: 11px;
                }}
                QPlainTextEdit:focus {{ border-color: {c['accent']}; }}
            """)

        # QPushButtons — keep accent-colored buttons, update plain ones
        btn_style_plain = f"""
            QPushButton {{
                background: none; color: {c['text_muted']};
                border: 1px solid {c['border']}; border-radius: 4px;
                padding: 0 12px; font-size: 11px;
            }}
            QPushButton:hover {{
                color: {c['text']}; border-color: {c['accent']};
            }}
        """
        for btn in self.findChildren(QPushButton):
            ss = btn.styleSheet()
            # Only restyle non-accent buttons (plain/border-only)
            if "background: none" in ss or "background:none" in ss:
                btn.setStyleSheet(btn_style_plain)

        # Scroll area
        for sa in self.findChildren(QScrollArea):
            sa.setStyleSheet(f"QScrollArea {{ border: none; background: {c['bg']}; }}")

    def save_to_config(self):
        """WI-022: Save current settings to config file."""
        self._sync_llm_config()
        save_config({
            "mask": self.mask_input.text(),
            "length_preserve": self.length_preserve_cb.isChecked(),
            "consistent": self.consistent_cb.isChecked(),
            "pii_fields_enabled": self.pii_fields_cb.isChecked(),
            "custom_regex_patterns": self.pattern_registry.to_dict_list(),
            "llm": self.llm_config.to_dict(),
        })
