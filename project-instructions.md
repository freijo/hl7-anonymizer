# Project: HL7 Anonymizer

## Context
You are supporting the development of the **HL7 Anonymizer** — a local Python desktop application (.exe) for anonymizing patient and person-related data in HL7 v2.x messages. The complete project requirements, design system, field lists, work items, and architectural decisions are documented in the Knowledge file `hl7-anonymizer-requirements.md`.

## Technology Stack
- **Language:** Python 3.10+
- **UI Framework:** PySide6
- **Packaging:** PyInstaller → standalone .exe
- **Target OS:** Windows 10/11 (64-bit), optional macOS/Linux
- **LLM (optional, 3 modes):**
  - Embedded: small ONNX/GGUF NER model (e.g., GLiNER-small, spaCy NER ONNX, TinyLlama GGUF Q4)
  - Local API: OpenAI-compatible endpoint (Ollama, LM Studio, llama.cpp) — default `localhost:11434`
  - None: feature disabled, button grayed out
- **Config:** Persistent JSON config file (`hl7anon_config.json`)

## Project Method: GSD (Get Stuff Done / Kanban)
- Work is organized in prioritized tiers (0=MVP → 4=nice-to-have), not sprints.
- **WIP limit: 2 items.** Never start a third item while two are in progress.
- **Pull principle:** always pick the next item from the highest open tier.
- Every work item has a clear Definition of Done (see requirements Section 6).
- When implementing: focus on the current work item only. Don't gold-plate or add features from later tiers unless they're trivially small (< 5 min).
- When in doubt about scope: ship the smaller version first, iterate later.
- **MVP first:** the tool must be usable after Tier 0. Everything else is incremental.
- Reference work item IDs (WI-001, WI-012, etc.) when discussing or implementing features.

## Key Design Principles
1. **Human-in-the-loop is the core workflow.** The automatic HL7 parser is best-effort only — input is frequently not valid HL7. The UI must enable fast, intuitive manual field selection even when parsing fails completely.
2. **Graceful degradation over strict validation.** Never block the user with error messages. If parsing fails, display raw text with full selection capabilities.
3. **Local only by default.** No data ever leaves the machine. No network requests, no telemetry, no temp files with patient data. Exception: if user explicitly configures a remote LLM API, show a warning with the target host and require confirmation.
4. **Color scheme consistency.** Follow the design system in Section 2 of the requirements, derived from the HL7_ADT_Doku project. Four field selection states: Auto-detected (Amber), Manually selected (Red), LLM suggestion (Purple), Neutral (Gray).
5. **Persistent configuration.** All settings, custom regex patterns, LLM config, and anonymization profiles are stored in `hl7anon_config.json`. Structure defined in Section 7.1.

## When Writing Code
- Reference requirement IDs (F-HL-07, F-AO-04, F-LLM-02) and work item IDs (WI-003, WI-021) when implementing features.
- Preserve HL7 structure (delimiters `|`, `^`, `~`, `\`, `&`) during anonymization at all times.
- Handle HL7 escape sequences correctly (`\F\`, `\S\`, `\T\`, `\R\`, `\E\`).
- Empty fields that are selected for anonymization must remain empty.
- LLM calls must always run in a QThread with progress indicator and cancel support. Never block the UI.
- LLM results are always suggestions (purple) — never auto-accept. User must confirm.
- When connecting to a non-localhost LLM API, always show a data locality warning before sending any data.
- Config file operations: use atomic writes (write to temp → rename) to prevent corruption. Load with fallback to defaults on parse error.
- Write unit tests for Parser, Anonymization Engine, and Regex. Not required for pure UI interactions.
- Apply the Definition of Done (Section 6) to every work item before marking it as done.

## When Discussing Architecture or Design
- Refer to the wireframe mockup for UI layout decisions (4-step workflow: Input → Select Fields → Settings → Output).
- The Select Fields screen (Step 2) is the most complex — two-column layout with inline-highlighted clickable fields + sidebar.
- Always consider the "broken HL7" case — every feature must work without a successful parse.
- PySide6 specifics: use QTextEdit with custom QSyntaxHighlighter or QTextCharFormat for inline field coloring. Use QThread for background tasks (LLM, large file parsing). Use signals/slots for UI updates.

## Communication
- Respond in the language the user writes in (typically German or English).
- When proposing changes, reference affected work item IDs and requirement IDs.
- Flag any implementation decisions that could impact data privacy or anonymization completeness.
- When a work item is complete, suggest the next item to pull from the backlog based on tier priority.