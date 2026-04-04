# Project: HL7 Anonymizer

## Context
You are supporting the development of the **HL7 Anonymizer** — a local Python desktop application (.exe) for anonymizing patient and person-related data in HL7 v2.x messages. The complete project requirements, design system, field lists, work items, and architectural decisions are documented in `docs/hl7-anonymizer-requirements.md`.

**Current state:** Version 1.0, feature-complete. All 59 work items across 6 tiers are done. See `KANBAN.md` for the full board and `CLAUDE.md` for architecture details.

## Technology Stack
- **Language:** Python 3.10+
- **UI Framework:** PySide6
- **Packaging:** PyInstaller -> standalone .exe
- **Target OS:** Windows 10/11 (64-bit), optional macOS/Linux
- **LLM (optional, 2 modes):**
  - Local API: OpenAI-compatible endpoint (Ollama, LM Studio, llama.cpp) — default `localhost:11434`
  - None: feature disabled, button grayed out
- **Config:** Persistent JSON config file (`~/.hl7-anonymizer/settings.json`)

## UI Workflow (3 steps)

The app uses a **3-step workflow** (not 4 — Settings moved to a global dialog in WI-051):

1. **Input** — Paste or drag-and-drop HL7 messages
2. **Select Fields** — Core screen: clickable fields with 4-color states, sidebar, search, LLM analysis
3. **Output** — Anonymized text with diff view, copy, and export

Settings (mask character, length strategy, regex, LLM config, profiles) are in a **modal dialog** accessible via the gear icon in the header.

## Project Method: GSD (Get Stuff Done / Kanban)
- Work is organized in prioritized tiers (0=MVP -> 4=nice-to-have, 5=polish, 6=advanced).
- **WIP limit: 2 items.** Never start a third item while two are in progress.
- **Pull principle:** always pick the next item from the highest open tier.
- Every work item has a clear Definition of Done (see requirements Section 6).
- When implementing: focus on the current work item only. Don't gold-plate.
- **MVP first:** the tool must be usable after Tier 0. Everything else is incremental.
- Reference work item IDs (WI-001, WI-012, etc.) when discussing or implementing features.

## Key Design Principles
1. **Human-in-the-loop is the core workflow.** The HL7 parser is best-effort — input is frequently not valid HL7. The UI must enable fast manual field selection even when parsing fails.
2. **Graceful degradation over strict validation.** Never block the user with error messages. If parsing fails, display raw text with full selection capabilities.
3. **Local only by default.** No data ever leaves the machine. Exception: if user configures a remote LLM API, show a warning and require confirmation.
4. **Color scheme consistency.** Four field selection states: Auto-detected (Amber), Manually selected (Red), LLM suggestion (Purple), Neutral (Gray). Each also has an accessibility symbol.
5. **Persistent configuration.** All settings stored in `~/.hl7-anonymizer/settings.json`.

## When Writing Code
- Reference requirement IDs (F-HL-07, F-AO-04) and work item IDs (WI-003, WI-021) when implementing.
- Preserve HL7 structure (delimiters `|`, `^`, `~`, `\`, `&`) during anonymization at all times.
- Handle HL7 escape sequences correctly (`\F\`, `\S\`, `\T\`, `\R\`, `\E\`).
- Empty fields that are selected for anonymization must remain empty.
- LLM calls must always run in a QThread with progress indicator and cancel support.
- LLM results are always suggestions (purple) — never auto-accept.
- Config file operations: use atomic writes (write to temp -> rename).
- Write unit tests for Parser, Anonymization Engine, and Regex. Not required for pure UI.
- Apply the Definition of Done (Section 6 of requirements) to every work item.
- Tooltips: use per-widget `TOOLTIP_CSS` from `theme.py` (app-level stylesheet doesn't work on Windows light mode).
- Selection screen uses a lightweight data model (`_FieldInfo`) separate from Qt widgets — always update model, then render.

## When Discussing Architecture or Design
- The Select Fields screen (Step 2) is the most complex — inline clickable fields + sidebar with segment quick-select.
- Always consider the "broken HL7" case — every feature must work without a successful parse.
- Pagination: `PAGE_SIZE = 50` messages per page to handle 6K+ messages without crashes.
- Non-HL7 lines are tracked with original line numbers (`HL7Message.start_line`) for correct output positioning.

## Communication
- Respond in the language the user writes in (typically German or English).
- When proposing changes, reference affected work item IDs and requirement IDs.
- Flag any implementation decisions that could impact data privacy or anonymization completeness.
- When a work item is complete, suggest the next item from the backlog based on tier priority.
