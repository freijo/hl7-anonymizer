"""Main window with 3-step navigation + settings dialog."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.engine.anonymizer import anonymize
from src.ui.input_screen import InputScreen
from src.ui.selection_screen import SelectionScreen
from src.ui.settings_screen import SettingsDialog
from src.ui.output_screen import OutputScreen
from src.ui.theme import COLORS_LIGHT, COLORS_DARK, TOOLTIP_CSS, theme_manager

STEPS = [
    ("1", "Input"),
    ("2", "Select Fields"),
    ("3", "Output"),
]


class StepButton(QPushButton):
    """A single step button in the navigation bar."""

    def __init__(self, number: str, label: str, parent=None):
        super().__init__(parent)
        self.number = number
        self.label_text = label
        self.setText(f"  {number}  {label}")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(42)
        self._update_style(active=False)

    def _update_style(self, active: bool):
        accent = COLORS_LIGHT["accent"]
        text_muted = COLORS_LIGHT["text_muted"]
        text = COLORS_LIGHT["text"]
        panel = COLORS_LIGHT["panel"]
        if active:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: none; border: none; border-bottom: 3px solid {accent};
                    color: {accent}; font-weight: 700; font-size: 13px;
                    padding: 0 20px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: none; border: none; border-bottom: 3px solid transparent;
                    color: {text_muted}; font-weight: 500; font-size: 13px;
                    padding: 0 20px;
                }}
                QPushButton:hover {{
                    color: {text}; background: {panel};
                }}
            """)

    def set_active(self, active: bool):
        self.setChecked(active)
        self._update_style(active)


class MainWindow(QMainWindow):
    """Main application window with step-based navigation."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("HL7 Anonymizer")
        self.setMinimumSize(1000, 650)
        self.resize(1200, 750)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- Header ---
        self.header = self._build_header()
        layout.addWidget(self.header)

        # --- Step navigation ---
        self.nav_bar = QWidget()
        self.nav_bar.setStyleSheet(f"background: {COLORS_LIGHT['surface']}; border-bottom: 1px solid {COLORS_LIGHT['border']};")
        nav_layout = QHBoxLayout(self.nav_bar)
        nav_layout.setContentsMargins(28, 0, 28, 0)
        nav_layout.setSpacing(0)

        self.step_buttons: list[StepButton] = []
        for num, label in STEPS:
            btn = StepButton(num, label)
            btn.clicked.connect(lambda checked, n=int(num) - 1: self._go_step(n))
            nav_layout.addWidget(btn)
            self.step_buttons.append(btn)
        nav_layout.addStretch()
        layout.addWidget(self.nav_bar)

        # --- Content stack (3 screens) ---
        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"background: {COLORS_LIGHT['bg']};")

        self.input_screen = InputScreen()
        self.input_screen.navigate_next.connect(lambda: self._go_step(1))
        self.stack.addWidget(self.input_screen)

        self.selection_screen = SelectionScreen()
        self.stack.addWidget(self.selection_screen)

        self.output_screen = OutputScreen()
        self.stack.addWidget(self.output_screen)

        layout.addWidget(self.stack, 1)

        # --- WI-051: Settings dialog (not in stack) ---
        self.settings_dialog = SettingsDialog(self)
        self.settings_dialog.settings_closed.connect(self._on_settings_closed)

        # Initial state
        self._go_step(0)

    # Backwards-compat property so existing code referencing settings_screen still works
    @property
    def settings_screen(self):
        return self.settings_dialog

    def closeEvent(self, event):
        """WI-022: Save settings on close."""
        self.settings_dialog.save_to_config()
        super().closeEvent(event)

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setStyleSheet(
            f"background: {COLORS_LIGHT['surface']}; "
            f"border-bottom: 3px solid {COLORS_LIGHT['accent']};"
        )
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(28, 10, 28, 10)

        self.header_title = QLabel("HL7 Anonymizer")
        self.header_title.setFont(QFont("Segoe UI", 14, QFont.Weight.DemiBold))
        self.header_title.setStyleSheet(f"color: {COLORS_LIGHT['text']}; border: none;")
        h_layout.addWidget(self.header_title)

        self.header_subtitle = QLabel("Anonymize personal data in HL7 v2.x messages")
        self.header_subtitle.setStyleSheet(f"color: {COLORS_LIGHT['text_muted']}; font-size: 11px; border: none;")
        h_layout.addWidget(self.header_subtitle)

        h_layout.addStretch()

        version = QLabel("v0.1")
        version.setStyleSheet(
            f"background: {COLORS_LIGHT['accent']}; color: white; "
            f"padding: 4px 14px; border-radius: 4px; font-size: 11px; font-weight: 700; border: none;"
        )
        h_layout.addWidget(version)

        header_btn_ss = (
            f"QPushButton {{ background: none; border: 1px solid {COLORS_LIGHT['border']}; "
            f"border-radius: 4px; font-size: 11px; font-weight: 600; "
            f"color: {COLORS_LIGHT['text']}; padding: 4px 12px; }}"
            f"QPushButton:hover {{ background: {COLORS_LIGHT['panel']}; }}"
        )

        icon_btn_ss = (
            f"QPushButton {{ background: none; border: 1px solid {COLORS_LIGHT['border']}; "
            f"border-radius: 4px; font-family: 'Segoe MDL2 Assets'; font-size: 14px; "
            f"color: {COLORS_LIGHT['text']}; padding: 0; }}"
            f"QPushButton:hover {{ background: {COLORS_LIGHT['panel']}; }}"
            + TOOLTIP_CSS
        )

        # WI-051: Settings button (gear icon from Segoe MDL2 Assets)
        self.settings_btn = QPushButton("\uE713")  # Settings gear
        self.settings_btn.setFixedSize(36, 36)
        self.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_btn.setToolTip("Settings")
        self.settings_btn.setStyleSheet(icon_btn_ss)
        self.settings_btn.clicked.connect(self._open_settings)
        h_layout.addWidget(self.settings_btn)

        # WI-040: Dark Mode toggle (moon icon from Segoe MDL2 Assets)
        self.theme_btn = QPushButton("\uE708")  # Brightness / sun
        self.theme_btn.setFixedSize(36, 36)
        self.theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_btn.setToolTip("Toggle Dark Mode")
        self.theme_btn.setStyleSheet(icon_btn_ss)
        self.theme_btn.clicked.connect(self._toggle_theme)
        h_layout.addWidget(self.theme_btn)

        return header

    def _open_settings(self):
        """WI-051: Open settings dialog."""
        self.settings_dialog.show()
        self.settings_dialog.raise_()
        self.settings_dialog.activateWindow()

    def _on_settings_closed(self):
        """Refresh selection screen after settings dialog closes."""
        if self.stack.currentIndex() == 1:
            self.selection_screen.set_pattern_registry(
                self.settings_dialog.pattern_registry
            )
            self.selection_screen.set_pii_fields_enabled(
                self.settings_dialog.get_pii_fields_enabled()
            )
            self.selection_screen.set_parse_result(
                self.input_screen.get_parse_result()
            )

    def _toggle_theme(self):
        """WI-040: Toggle between light and dark mode by re-applying stylesheets."""
        theme_manager.toggle()
        c = theme_manager.current_colors()

        if theme_manager.is_dark():
            self.theme_btn.setText("\uE706")  # Sunny / light mode
        else:
            self.theme_btn.setText("\uE708")  # Brightness / dark mode

        # Full palette for dark mode / restore system palette for light mode
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(c['bg']))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(c['text']))
        palette.setColor(QPalette.ColorRole.Base, QColor(c['surface']))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(c['panel']))
        palette.setColor(QPalette.ColorRole.Text, QColor(c['text']))
        palette.setColor(QPalette.ColorRole.Button, QColor(c['surface']))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(c['text']))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(c['accent']))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor('#ffffff'))
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(c['text_muted']))
        # Tooltip colors — always dark bg with white text
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#2d3748"))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#ffffff"))
        QApplication.instance().setPalette(palette)

        # Force-update structural widgets that have inline stylesheets
        self.header.setStyleSheet(
            f"background: {c['surface']}; border-bottom: 3px solid {c['accent']};"
        )
        self.header_title.setStyleSheet(f"color: {c['text']}; border: none;")
        self.header_subtitle.setStyleSheet(f"color: {c['text_muted']}; font-size: 11px; border: none;")
        self.nav_bar.setStyleSheet(
            f"background: {c['surface']}; border-bottom: 1px solid {c['border']};"
        )
        self.stack.setStyleSheet(f"background: {c['bg']};")

        header_btn_style = (
            f"QPushButton {{ background: none; border: 1px solid {c['border']}; "
            f"border-radius: 4px; font-family: 'Segoe MDL2 Assets'; font-size: 14px; "
            f"color: {c['text']}; padding: 0; }}"
            f"QPushButton:hover {{ background: {c['panel']}; }}"
            + TOOLTIP_CSS
        )
        self.theme_btn.setStyleSheet(header_btn_style)
        self.settings_btn.setStyleSheet(header_btn_style)

        # Update step buttons
        for i, btn in enumerate(self.step_buttons):
            active = btn.isChecked()
            if active:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: none; border: none; border-bottom: 3px solid {c['accent']};
                        color: {c['accent']}; font-weight: 700; font-size: 13px;
                        padding: 0 20px;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: none; border: none; border-bottom: 3px solid transparent;
                        color: {c['text_muted']}; font-weight: 500; font-size: 13px;
                        padding: 0 20px;
                    }}
                    QPushButton:hover {{
                        color: {c['text']}; background: {c['panel']};
                    }}
                """)

        # Refresh child screens
        self.settings_dialog.refresh_theme()
        self.input_screen.refresh_theme()
        self.selection_screen.refresh_theme()
        self.output_screen.refresh_theme()

    def _go_step(self, index: int):
        if 0 <= index < self.stack.count():
            self.stack.setCurrentIndex(index)
            for i, btn in enumerate(self.step_buttons):
                btn.set_active(i == index)

            # When navigating to step 2, pass parsed data + detection settings
            if index == 1:
                self.selection_screen.set_pattern_registry(
                    self.settings_dialog.pattern_registry
                )
                self.selection_screen.set_pii_fields_enabled(
                    self.settings_dialog.get_pii_fields_enabled()
                )
                self.selection_screen.set_llm_config(
                    self.settings_dialog.get_llm_config()
                )
                self.selection_screen.set_parse_result(
                    self.input_screen.get_parse_result()
                )

            # When navigating to step 3 (Output), run anonymization engine
            if index == 2:
                self._run_anonymization()

    def _run_anonymization(self):
        """Collect selections from step 2, run engine, pass result to step 3."""
        parse_result = self.input_screen.get_parse_result()
        raw_selections = self.selection_screen.get_selections()

        # Build set of (msg_index, path) for the engine
        selections = {(msg_idx, path) for msg_idx, _seg, _fi, path, _state in raw_selections}

        # WI-027: Collect log metadata
        segments_touched = {seg for _mi, seg, _fi, _p, _s in raw_selections}
        msg_count = len(parse_result.messages) if parse_result.is_valid_hl7 else 0

        # WI-042: Pass original text for diff view
        self.output_screen.set_original_text(self.input_screen.text_edit.toPlainText())

        mask = self.settings_dialog.get_mask()
        length_preserve = self.settings_dialog.get_length_preserve()
        consistent = self.settings_dialog.get_consistent()
        message_separator = self.settings_dialog.get_message_separator()
        preserve_non_hl7 = self.settings_dialog.get_preserve_non_hl7()
        result = anonymize(
            parse_result, selections, mask=mask,
            length_preserve=length_preserve, consistent=consistent,
            message_separator=message_separator,
            preserve_non_hl7=preserve_non_hl7,
        )
        self.output_screen.set_anonymized_output(
            result, len(selections),
            msg_count=msg_count, segments=segments_touched, mask=mask,
        )
