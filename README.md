# HL7 Anonymizer

Local desktop application for anonymizing personal data in HL7 v2.x messages, built with Python and PySide6. Data never leaves your machine.

## Features

- **Best-effort HL7 parser** — works with valid and broken HL7 input alike
- **4-color field selection** — Auto-detected (Amber), Manual (Red), LLM suggestion (Purple), Neutral (Gray)
- **Auto-preselection** of 49 known PII fields (PID, NK1, PV1, IN1, GT1, ...)
- **Regex detection** — built-in patterns for dates, phone numbers, email, Swiss AHV; custom patterns via editor
- **LLM integration** — optional analysis via local OpenAI-compatible API (Ollama, LM Studio)
- **Consistent pseudonymization** — same value produces same pseudonym across all messages
- **Diff view** — side-by-side comparison of original and anonymized output
- **Batch processing** — paste or drag-and-drop multiple HL7 messages at once
- **Profiles** — save and load named field selection configurations
- **Undo/Redo** — full undo history for field selections
- **Dark mode** — with accessible symbols alongside colors
- **Export** — copy to clipboard or save as `.txt` file
- **Keyboard navigation** — Tab/Arrow keys between fields, Space to toggle

## Requirements

- Python 3.10+
- Windows 10/11 (64-bit), optional macOS/Linux

## Setup

```bash
pip install -r requirements.txt
```

## Run

```bash
python -m src.main
```

## Test

```bash
pytest tests/
```

## Build standalone .exe

```bash
build.bat
```

Produces a single-file executable via PyInstaller.

## Workflow

1. **Input** — Paste HL7 messages (supports multiple messages, detects boundaries automatically)
2. **Select Fields** — Review auto-selected PII fields, adjust manually, optionally run LLM analysis
3. **Output** — View anonymized result, compare with diff view, copy or export

Settings (mask character, length strategy, regex patterns, LLM config, profiles) are accessible via the gear icon in the header.

## Project Structure

```
src/
  main.py               # Application entry point
  parser/hl7_parser.py  # HL7 v2.x parser
  engine/anonymizer.py  # Anonymization engine
  engine/llm_client.py  # LLM API client
  engine/llm_worker.py  # Background LLM thread
  config/               # Field definitions, regex patterns, config persistence
  ui/                   # PySide6 screens (input, selection, output, settings, theme)
tests/                  # Unit tests (parser, anonymizer, LLM client)
docs/                   # Requirements document
```

## Configuration

Settings are persisted in `~/.hl7-anonymizer/settings.json`. Use Config Export/Import to share configurations between machines.

## Privacy

- No network requests by default — all processing is local
- No telemetry, no temp files with patient data
- Remote LLM API requires explicit user confirmation with data locality warning

## License

All rights reserved.
