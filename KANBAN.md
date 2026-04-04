# HL7 Anonymizer — Kanban Board

## IN PROGRESS (WIP: 2)

## REVIEW

## DONE
- [x] WI-001: HL7 Parser (best-effort)
- [x] WI-002: Input-Screen
- [x] WI-003: Field Selection (Basis)
- [x] WI-004: Auto-Preselection + Multi-Message Sync
- [x] WI-005: Anonymisierungs-Engine
- [x] WI-006: Output-Screen
- [x] WI-007: Maskenzeichen-Setting
- [x] WI-011: Segment Quick-Select (Sidebar)
- [x] WI-012: Value-based Selection
- [x] WI-013: Search
- [x] WI-014: Apply to all Messages (in WI-004)
- [x] WI-015: Hover Tooltips
- [x] WI-016: 4-Farben-Schema (in WI-003)
- [x] WI-017: Export .txt
- [x] WI-019: Non-HL7 Inline-Warnung (in WI-003)
- [x] WI-020: Default Regex Patterns
- [x] WI-021: Custom Regex Editor
- [x] WI-022: Config File
- [x] WI-023: Längenstrategie
- [x] WI-024: Konsistente Pseudonymisierung
- [x] WI-025: Kontextmenü (Rechtsklick)
- [x] WI-026: Tastaturnavigation
- [x] WI-027: Anonymisierungslog
- [x] WI-028: Settings Reset

## DONE (Tier 3 — LLM-Integration)
- [x] WI-030: LLM Settings UI
- [~] WI-031: Embedded NER Model (deferred — Local API covers use case)
- [x] WI-032: Local API Anbindung
- [x] WI-033: LLM Analyse Button
- [x] WI-034: LLM Results als Suggestions
- [x] WI-035: Remote API Warnung
- [x] WI-036: LLM Prompt konfigurierbar

## DONE (Tier 4 — Nice-to-have)
- [x] WI-040: Dark Mode
- [x] WI-041: Anonymisierungsprofile
- [x] WI-042: Diff-View
- [x] WI-043: Batch File Upload
- [x] WI-044: Undo/Redo
- [x] WI-045: Config Export/Import
- [x] WI-046: Bereichsmarkierung
- [x] WI-047: Accessibility

## DONE (Tier 5 — Export & Settings Refactor)
- [x] WI-051: Globaler Settings-Dialog (Zahnrad-Button, Settings aus Step 3 in Dialog verschieben, 3-Step-Navigation)
- [x] WI-050: Export-Trenner zwischen HL7-Meldungen (konfigurierbar, Default: HL7-Standard-Zeilenumbruch)
- [x] WI-052: Non-HL7-Elemente im Export beibehalten (optional, Position erhalten, in Settings konfigurierbar)

## DONE (Tier 5 — UI Polish)
- [x] WI-053: Tooltips einheitlich in Light & Dark Mode (per-Widget QToolTip CSS)
- [x] WI-054: Header-Buttons mit Segoe MDL2 Font-Icons (Zahnrad, Theme-Toggle)
- [x] WI-055: Font-Konsistenz Input/Output (Cascadia Code 11 überall)
- [x] WI-056: Settings-Dialog schwarzer Rand entfernt (QPalette + ScrollContent Background)

## DONE (Tier 6 — Diff & Performance)
- [x] WI-057: Diff-View Scroll-Sync + NoWrap (Zeilen nebeneinander, synchrones Scrollen)
- [x] WI-058: Performance Pagination Screen 2 (50 Msg/Seite, Data Model für alle, kein Crash bei 6K+)
