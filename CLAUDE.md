# CLAUDE.md — HL7 Anonymizer

## What this project is

Local Python/PySide6 desktop app for anonymizing personal data in HL7 v2.x messages. Standalone .exe via PyInstaller. No data ever leaves the machine (unless user explicitly configures a remote LLM API).

**Version:** 1.0
**Status:** Feature-complete (all 59 work items across 6 tiers done)

## Quick commands

```bash
# Run
python -m src.main

# Test
pytest tests/ -x -q

# Build .exe
build.bat
```

## Architecture

3-step UI workflow: **Input** -> **Select Fields** -> **Output**
Settings are in a global dialog (gear icon), not a separate step.

```
src/
  main.py                     # Entry point: QApplication + MainWindow
  parser/
    hl7_parser.py             # Best-effort HL7 v2.x parser (never throws)
  engine/
    anonymizer.py             # Replaces selected fields with mask, preserves HL7 structure
    llm_client.py             # OpenAI-compatible API client (Ollama default)
    llm_worker.py             # QThread for background LLM analysis
  config/
    field_definitions.py      # DEFAULT_PII_FIELDS for auto-preselection
    field_descriptions.py     # Tooltip descriptions per HL7 field
    regex_patterns.py         # Built-in + custom regex patterns
    config_file.py            # Persistent JSON config (~/.hl7-anonymizer/settings.json)
  ui/
    main_window.py            # 3-step navigation, header, settings/info/theme buttons
    input_screen.py           # Step 1: paste HL7 text
    selection_screen.py       # Step 2: clickable field selection (core screen)
    output_screen.py          # Step 3: anonymized output + diff view + export
    settings_screen.py        # Modal settings dialog (mask, strategy, regex, LLM, profiles)
    theme.py                  # Light/Dark theme colors, TOOLTIP_CSS constant
tests/
  test_parser.py              # Parser: valid + broken HL7, escape sequences
  test_anonymizer.py          # Engine: mask strategies, structure preservation
  test_llm_client.py          # LLM client: connection, response parsing
```

## Key data flow

1. User pastes HL7 text in `input_screen.py`
2. `hl7_parser.parse(text)` returns `ParseResult` (messages, non_hl7_lines, is_valid_hl7)
3. `selection_screen.py` renders fields as clickable `ValueWidget`s with 4-color states
4. Auto-preselection marks PII fields (Amber), user clicks toggle (Red), LLM suggests (Purple)
5. `anonymizer.anonymize(parse_result, selections, ...)` replaces selected values
6. `output_screen.py` displays result with diff view and export

## Key conventions

- **Parser never throws.** All exceptions caught, returns non-HL7 fallback.
- **4 field states:** Auto-detected (Amber), Manual (Red), LLM suggestion (Purple), Neutral (Gray). Each has accessibility symbols too.
- **HL7 structure preservation:** Delimiters `|^~\&` and escape sequences `\F\ \S\ \T\ \R\ \E\` are never masked.
- **Empty fields stay empty** even when selected for anonymization.
- **Pagination:** Selection screen uses `PAGE_SIZE = 50` messages per page with a lightweight `_FieldInfo` data model (not Qt widgets) for all state tracking.
- **Config path:** `~/.hl7-anonymizer/settings.json` (atomic write: temp -> rename)
- **Fonts:** Segoe UI 10pt (UI), Cascadia Code 11pt (HL7 text), Segoe MDL2 Assets (icons)
- **Tooltips:** Per-widget `QToolTip` CSS via `TOOLTIP_CSS` constant from `theme.py` (app-level stylesheet doesn't work on Windows light mode)
- **LLM results are always suggestions** (Purple) — never auto-accepted.

## Path building (critical for anonymizer <-> UI sync)

The anonymizer and selection screen must use identical path strings to match fields:
- Simple field: `SEG.N` (e.g., `PID.5`)
- With repetitions: `SEG.N(R)` (e.g., `PID.3(1)`)
- With components: `SEG.N(R).C` or `SEG.N.C`
- With subcomponents: `SEG.N(R).C.S` or `SEG.N.C.S`

## MSH special handling

- MSH.1 = field separator character (implicit, not in pipe-split array)
- MSH.2 = encoding characters (first element after split)
- MSH field indexing: `parts[N-1]` maps to `MSH.N` (for N >= 2)
- Other segments: `parts[N]` maps to `SEG.N`

## Design system

See `docs/hl7-anonymizer-requirements.md` Section 2 for the full color palette. Key colors:
- Accent: `#0066A1` (light) / `#4da6d9` (dark)
- Auto-detected: Amber (`#fef9e7` bg, `#e6c84d` border)
- Manual: Red (`#fee2e2` bg, `#f87171` border)
- LLM: Purple (`#f5f0fc` bg, `#c4b5e0` border)

## Project method

GSD (Get Stuff Done) / Kanban. See `KANBAN.md` for board state.
- WIP limit: 2 items in progress
- Pull principle: next item from highest open tier
- Every work item has a Definition of Done (see requirements Section 6)
- Reference WI-### IDs when implementing

## Non-obvious decisions

- Settings moved from Step 3 to a modal dialog (WI-051) — UI is now 3 steps, not 4
- WI-031 (Embedded NER) deferred — Local API (WI-032) covers the use case
- Non-HL7 lines track original line numbers for correct position in output (HL7Message.start_line)
- QPalette + setAutoFillBackground needed for settings dialog background (CSS border:none doesn't affect OS window frame)
