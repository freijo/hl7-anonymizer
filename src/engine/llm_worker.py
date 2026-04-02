"""WI-033: Background worker for LLM analysis.

Runs LLM field analysis in a QThread so the UI stays responsive.
Emits progress updates and can be cancelled mid-run.
"""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from src.engine.llm_client import LLMConfig, LLMResult, analyze_field


class LLMWorker(QThread):
    """Analyses field values via LLM in the background.

    Signals:
        progress(current, total): Emitted after each field is analysed.
        field_result(field_text, result): Emitted per field with LLM result.
        finished_all(results): Emitted when all fields are done.
        error(message): Emitted on fatal error.
    """

    progress = Signal(int, int)
    field_result = Signal(str, object)  # (field_text, LLMResult)
    finished_all = Signal(list)  # list of (field_text, LLMResult)
    error = Signal(str)

    def __init__(self, config: LLMConfig, field_texts: list[str], parent=None):
        super().__init__(parent)
        self.config = config
        self.field_texts = field_texts
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        results: list[tuple[str, LLMResult]] = []
        total = len(self.field_texts)
        had_fatal_error = False

        for i, text in enumerate(self.field_texts):
            if self._cancelled:
                break

            result = analyze_field(self.config, text)
            results.append((text, result))
            self.field_result.emit(text, result)
            self.progress.emit(i + 1, total)

            if result.error:
                self.error.emit(result.error)
                had_fatal_error = True
                break

        if not had_fatal_error:
            self.finished_all.emit(results)
