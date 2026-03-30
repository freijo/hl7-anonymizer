# HL7 Anonymizer – Projektanforderungen (GSD)

## 1. Projektziel

Lokale Python-Desktop-Anwendung (standalone .exe) zur Anonymisierung personenbezogener Daten in HL7-v2.x-Nachrichten, um diese sicher an externe Empfänger weitergeben zu können.

**Technologie:** Python 3.10+ / PySide6 / PyInstaller → standalone .exe
**Sprache UI:** Englisch
**HL7-Versionen:** Alle v2.x
**Methode:** GSD (Get Stuff Done) — Kanban, WIP-Limit 2, Pull-Prinzip

---

## 2. Design System & Farbschema

Übernommen aus dem Projekt HL7_ADT_Doku und erweitert um Anonymizer-spezifische Zustände.

### 2.1 Basis-Farben (aus HL7_ADT_Doku)

| Variable | Light | Dark | Verwendung |
|----------|-------|------|-----------|
| `--accent` | `#0066A1` | `#4da6d9` | Primärfarbe, Buttons, aktive Tabs |
| `--accent-hover` | `#004d7a` | `#6dbde6` | Hover-Zustand |
| `--accent-light` | `#e8f2fa` | `#1a2d3d` | Hintergrund Badges, Info-Bereiche |
| `--text` | `#2d3748` | `#e2e8f0` | Haupttext |
| `--text-muted` | `#718096` | `#a0aec0` | Sekundärtext, Labels |
| `--bg` | `#f7f8fc` | `#0f1117` | Seitenhintergrund |
| `--surface` | `#ffffff` | `#171923` | Karten, Panels |
| `--panel` | `#edf0f5` | `#1e2130` | Toolbar-Hintergrund |
| `--border` | `#d2d8e2` | `#2d3748` | Rahmen |
| `--gray-dark` | `#4a5568` | `#2d3748` | Header-Leisten |
| `--action-bg` | `#38a169` | `#276749` | Anonymisierungs-Button (Grün) |
| `--action-hover` | `#2f855a` | `#22543d` | Hover Anonymisierungs-Button |

### 2.2 Feld-Selektionszustände (NEU für Anonymizer)

| Zustand | Background | Border | Text | Verwendung |
|---------|-----------|--------|------|-----------|
| **Auto-detected** | `#fef9e7` | `#e6c84d` | `#92600a` | HL7-Spec + Regex-Vorselektion (Amber) |
| **Manually selected** | `#fee2e2` | `#f87171` | `#991b1b` | Vom User manuell selektiert (Rot) |
| **LLM suggestion** | `#f5f0fc` | `#c4b5e0` | `#553c8b` | LLM-Vorschlag, unbestätigt (Lila) |
| **Neutral** | `#ffffff` | `#e8ecf1` | `var(--text)` | Nicht selektiert |

### 2.3 Warnfarben (NEU für Anonymizer)

| Zustand | Background | Border | Text | Verwendung |
|---------|-----------|--------|------|-----------|
| **Non-HL7 Warning** | `#fff1f0` | `#e53e3e` | `#c53030` | Nicht-HL7-Inhalte, ungültige Zeichen |
| **Success** | `#c6f6d5` | `#38a169` | `#276749` | Anonymisierung abgeschlossen |

---

## 3. UI-Struktur

4-Schritt-Workflow mit Tab-Navigation. Siehe Wireframe-Datei (`hl7_anonymizer_wireframe.html`) für interaktiven Prototyp.

**Step 1 — Input:** Freitext-Paste für HL7-Nachrichten. Statusleiste mit Nachrichtenzähler. Nicht-HL7-Inhalte farblich markiert mit Hinweis.

**Step 2 — Select Fields (Kern-Screen):** Zwei-Spalten-Layout. Links: HL7-Rohtext mit klickbaren Feldern (4-Farben-Schema) + Toolbar (Suche, LLM-Button, Apply-to-all). Message-Tabs. Rechts: Sidebar mit Selektionszähler, Segment-Schnellauswahl, Feldliste, wertbasierte Selektion.

**Step 3 — Settings:** Maskenzeichen, Längenstrategie, Optionen, Regex-Patterns (Default + Custom Editor), LLM-Konfiguration.

**Step 4 — Output:** Anonymisierter Text + Copy-Button + Export-Button.

**Designprinzip:** Die Eingabe ist häufig kein valides HL7. Der Parser arbeitet best-effort. Bei fehlgeschlagenem Parsing: kein Abbruch — Rohtext wird angezeigt, alle Selektionsfunktionen bleiben verfügbar. Human-in-the-loop ist der Kern-Workflow.

---

## 4. Personenbezogene HL7-Felder (Default-Selektion)

### 4.1 Kernfelder (Default vorselektiert bei erkanntem HL7)

**PID – Patient Identification:**
PID-2 (Patient ID External), PID-3 (Patient Identifier List), PID-4 (Alternate Patient ID), PID-5 (Patient Name), PID-6 (Mother's Maiden Name), PID-7 (Date/Time of Birth), PID-9 (Patient Alias), PID-11 (Patient Address), PID-12 (County Code), PID-13 (Phone Number Home), PID-14 (Phone Number Business), PID-18 (Patient Account Number), PID-19 (SSN / AHV), PID-20 (Driver's License), PID-21 (Mother's Identifier), PID-23 (Birth Place), PID-26 (Citizenship), PID-28 (Nationality), PID-29 (Death Date/Time)

**Nicht vorselektiert, aber selektierbar:** PID-8 (Sex, Default: nein), PID-10 (Race), PID-27 (Veterans Military Status)

**NK1 – Next of Kin:**
NK1-2 (Name), NK1-4 (Address), NK1-5 (Phone), NK1-6 (Business Phone), NK1-30 (Contact Person Name), NK1-31 (Contact Person Phone), NK1-32 (Contact Person Address)

**PV1 – Patient Visit:**
PV1-7 (Attending Doctor), PV1-8 (Referring Doctor), PV1-9 (Consulting Doctor), PV1-17 (Admitting Doctor), PV1-19 (Visit Number), PV1-50 (Alternate Visit ID), PV1-52 (Other Healthcare Provider)

**PV2:** PV2-13 (Referral Source)

**IN1 – Insurance:**
IN1-2 (Plan ID), IN1-3 (Company ID), IN1-4 (Company Name), IN1-5 (Company Address), IN1-16 (Name of Insured), IN1-19 (Insured's Address), IN1-36 (Policy Number), IN1-49 (Insured's ID)

**GT1 – Guarantor:**
GT1-3 (Name), GT1-5 (Address), GT1-6 (Phone Home), GT1-7 (Phone Business), GT1-16 (Employer Name), GT1-17 (Employer Address), GT1-18 (Employer Phone)

### 4.2 Häufig übersehene Felder

ORC-12 (Ordering Provider), ORC-19 (Action By), OBR-10 (Collector), OBR-16 (Ordering Provider), OBR-28 (Result Copies To), OBX-16 (Responsible Observer), **OBX-5 (Observation Value — Freitext!)**, MSH-4 (Sending Facility), MSH-6 (Receiving Facility), MSH-10 (Message Control ID), **NTE-3 (Comment — Freitext!)**, DG1-16 (Diagnosing Clinician), AL1-6 (Identified By), Z-Segmente (manuell selektierbar)

### 4.3 Freitextfelder (kritisch)

OBX-5 und NTE-3 können beliebigen Freitext enthalten (Arztbriefe, Befunde mit Patientennamen). Reine Feld-Anonymisierung reicht nicht. Strategie: Regex-Engine automatisch, LLM-Analyse per Button.

---

## 5. Kanban-Board & Work Items

### Methode

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   BACKLOG    │  │ IN PROGRESS  │  │    REVIEW    │  │     DONE     │
│              │  │  (WIP: 2)    │  │  (WIP: 1)    │  │              │
│  Priorisiert │  │  Max 2 Items │  │  Manueller   │  │  DoD erfüllt │
│  nach Tier   │  │  gleichzeitig│  │  Test + DoD  │  │              │
└──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘
```

**WIP-Limit:** 2 in Progress, 1 in Review
**Pull-Prinzip:** Nächstes Item aus dem höchsten offenen Tier ziehen
**Scope-Regel:** Kein Gold-Plating. Wenn ein Feature aus einem späteren Tier < 5 Min dauert, darf es mitgenommen werden. Sonst: eigenes Work Item.

### Tier 0 — MVP (erstes nutzbares Tool)

| WI | Titel | Beschreibung | DoD-Kriterien |
|----|-------|-------------|---------------|
| WI-001 | HL7 Parser (best-effort) | MSH erkennen, Encoding Characters extrahieren, Segmente/Felder/Komponenten auflösen. Bei kaputtem Input: Rohtext zurückgeben, kein Fehler | Parser-Unit-Tests mit 5 gültigen + 3 kaputten Eingaben. Escape-Sequenzen (\F\, \S\, \T\, \R\, \E\) korrekt |
| WI-002 | Input-Screen | Textarea zum Pasten, Erkennung mehrerer Nachrichten (CR/LF), Nachrichtenzähler, Warnung bei Nicht-HL7-Zeilen mit Hinweis "will be ignored" | Funktioniert mit 0, 1, und 10+ Nachrichten |
| WI-003 | Field Selection (Basis) | HL7-Rohtext inline anzeigen. Jedes Pipe-getrennte Feld als klickbares Element. Klick togglet zwischen Auto/Manual/Neutral. Selektionszähler ("X of Y selected") | Klick togglet zuverlässig. Zähler aktualisiert in Echtzeit. Funktioniert auch bei Rohtext ohne HL7-Parsing |
| WI-004 | Auto-Preselection | Bei erkanntem HL7: Kernfelder (Abschnitt 4.1) automatisch selektieren (Amber). Statusanzeige "HL7 detected" vs "No valid HL7" | Alle Felder aus 4.1 korrekt erkannt. Bei kaputtem HL7: keine Vorselektion, kein Fehler |
| WI-005 | Anonymisierungs-Engine | Selektierte Felder mit Maskenzeichen ersetzen. Strukturerhalt (^~\& bleiben). Leere Felder bleiben leer. Fixwert-Länge (***) | Unit-Test: kein Originalwert selektierter Felder in Output. Roundtrip: Output ist valides HL7 |
| WI-006 | Output-Screen | Anonymisierter Text in Textarea. Copy-to-Clipboard Button | Copy funktioniert |
| WI-007 | Maskenzeichen-Setting | Eingabefeld für Maskenzeichen, Default `*` | Änderung wird sofort bei nächster Anonymisierung angewendet |

### Tier 1 — Usability (schnell und intuitiv arbeiten)

| WI | Titel | Beschreibung |
|----|-------|-------------|
| WI-010 | Message Tabs | Tab-Leiste zum Wechsel zwischen Nachrichten. Badge mit Selektionszähler pro Nachricht |
| WI-011 | Segment Quick-Select | Sidebar-Buttons (PID, NK1, PV1...) zum Selektieren/Deselektieren aller Felder eines Segments |
| WI-012 | Value-based Selection | Klick auf Wert → "Select this value across all messages". Alle Vorkommen (z.B. "Müller") werden selektiert |
| WI-013 | Search | Freitextsuche über alle Feldwerte. Treffer hervorheben. "Select matches" Button |
| WI-014 | Apply to all Messages | Selektion aus Nachricht 1 auf alle anderen übertragen (gleiche Feldpositionen) |
| WI-015 | Hover Tooltips | Bei Hover über Feld: Feldpfad + HL7-Beschreibung (z.B. "PID.5 – Patient Name") |
| WI-016 | 4-Farben-Schema | Farbschema gem. Abschnitt 2.2 vollständig umsetzen (Auto/Manual/LLM/Neutral) |
| WI-017 | Export .txt | Export-Button. Dateiname: `hl7_anonymized_YYYYMMDD_HHmmss.txt` |
| WI-018 | Sidebar: Selected Fields | Kompakte Liste aller selektierten Felder mit Pfad, Wert-Preview, Deselect-Button |
| WI-019 | Non-HL7 Inline-Warnung | Nicht-HL7-Zeilen auch im Select-Fields-View farblich markieren (nicht nur Input-Screen) |

### Tier 2 — Regex, Config & erweiterte Interaktion

| WI | Titel | Beschreibung |
|----|-------|-------------|
| WI-020 | Default Regex Patterns | Built-in Patterns: Telefon (international), E-Mail, Datumsformate, Swiss AHV. Aktiv per Default. Treffer werden auto-vorselektiert (Amber) |
| WI-021 | Custom Regex Editor | UI zum Hinzufügen/Bearbeiten/Löschen eigener Patterns. Name + Pattern + Beschreibung + Aktiv-Checkbox. Testfunktion gegen aktuelle Eingabe |
| WI-022 | Config File | `hl7anon_config.json` laden/speichern. Alle Settings persistent. Struktur gem. Abschnitt 7.1 |
| WI-023 | Längenstrategie | Konfigurierbar: Fixwert (Default) oder Datentyp-Max (wenn < 20 Zeichen) |
| WI-024 | Konsistente Pseudonymisierung | Optional per Checkbox. Gleicher Wert → gleiches Pseudonym über alle Nachrichten |
| WI-025 | Kontextmenü (Rechtsklick) | "Select this field", "Select all in segment", "Select this value everywhere", "Search for value" |
| WI-026 | Tastaturnavigation | Tab/Pfeiltasten zwischen Feldern, Leertaste toggle Selektion |
| WI-027 | Anonymisierungslog | Zusammenfassung nach Anonymisierung: Anzahl Felder, Anzahl Nachrichten, betroffene Segmente |
| WI-028 | Settings Reset | "Reset to Defaults" Button in Settings |

### Tier 3 — LLM-Integration

| WI | Titel | Beschreibung |
|----|-------|-------------|
| WI-030 | LLM Settings UI | Mode-Auswahl (Embedded / Local API / None). Bei "None": Analyze-Button ausgegraut |
| WI-031 | Embedded NER Model | Kleines ONNX/GGUF NER-Modell (z.B. GLiNER-small, spaCy NER ONNX, TinyLlama GGUF Q4). Download bei erstem Start mit Fortschrittsbalken. Ziel < 500 MB |
| WI-032 | Local API Anbindung | OpenAI-kompatibles `/v1/chat/completions` Endpoint. Konfigurierbar: Host, Port, Modellname, API-Key. Default: `localhost:11434` (Ollama). Connection-Test Button |
| WI-033 | LLM Analyse Button | "🧠 Analyze with LLM" in Step 2. Background-Thread, Fortschrittsbalken, Abbruch-Button. Nur nicht-selektierte Felder analysieren |
| WI-034 | LLM Results als Suggestions | Ergebnisse in Lila (gem. 2.2). "Accept all" / "Dismiss all" Buttons. Einzeln bestätigbar per Klick |
| WI-035 | Remote API Warnung | Bei Non-localhost: Warnhinweis "Data will be sent to [host]" mit Bestätigungsdialog. Blockiert bis User bestätigt |
| WI-036 | LLM Prompt konfigurierbar | Prompt-Template in Config-Datei editierbar. Default-Prompt: "Identify all person-related data (names, addresses, phone numbers, IDs, dates of birth, insurance numbers). Return JSON array of entities with type and position." |

### Tier 4 — Nice-to-have (bei Bedarf ziehen)

| WI | Titel | Beschreibung |
|----|-------|-------------|
| WI-040 | Dark Mode | Vollständiges Dark-Theme gem. Abschnitt 2.1 |
| WI-041 | Anonymisierungsprofile | Benannte Feldauswahl-Konfigurationen speichern/laden |
| WI-042 | Diff-View | Vorher/Nachher Vergleichsansicht |
| WI-043 | Batch File Upload | Drag & Drop von .hl7 / .txt Dateien statt nur Paste |
| WI-044 | Undo/Redo | Anonymisierung rückgängig machen (Session-basiert) |
| WI-045 | Config Export/Import | Gesamte Konfiguration als Datei exportieren/importieren |
| WI-046 | Bereichsmarkierung | Maus über mehrere Felder ziehen zum Selektieren |
| WI-047 | Accessibility | Icons/Symbole zusätzlich zu Farben für farbenblinde Nutzer |

---

## 6. Definition of Done

### Pro Work Item

1. **Funktioniert:** Feature ist implementiert und manuell getestet
2. **Kaputten Input getestet:** Funktioniert auch bei ungültigem HL7 / leerem Input
3. **Keine Regression:** Bestehende Features funktionieren weiterhin
4. **Kein Netzwerk:** Kein ausgehender Traffic (außer explizit konfigurierter LLM-API)
5. **Kein Datenleck:** Keine Patientendaten in Temp-Dateien, Logs oder Fehlermeldungen
6. **Unit Test** (wo sinnvoll): Parser, Engine, Regex — nicht für reine UI-Klickpfade

### Release-Checkliste (einmalig vor erstem Release nach Tier 0)

- [ ] Alle Tier-0 Work Items DONE
- [ ] Kein ausgehender Netzwerk-Traffic (Wireshark/netstat-Check)
- [ ] PyInstaller-Build startet auf sauberem Windows 10/11
- [ ] EXE-Dateigröße < 50 MB (ohne LLM-Modell)
- [ ] README mit Screenshot vorhanden
- [ ] Bekannte Einschränkungen dokumentiert

---

## 7. Entscheidungen

| # | Frage | Entscheidung |
|---|-------|-------------|
| 1 | Technologie-Stack | Python 3.10+ / PySide6 / PyInstaller → .exe |
| 2 | Längenstrategie | Fixwert `***`. Datentyp-Max (< 20) als Option (Tier 2) |
| 3 | Konsistente Pseudonymisierung | Optional, Checkbox, Default: aus (Tier 2) |
| 4 | HL7-Versionen | Alle v2.x, Feldliste als Union |
| 5 | Z-Segmente | Selektierbar wie reguläre Segmente, keine Warnung |
| 6 | UI-Sprache | Englisch |
| 7 | PID-8 (Geschlecht) | Default nicht vorselektiert, aber selektierbar |
| 8 | Projektmethode | GSD / Kanban, WIP-Limit 2, Pull-Prinzip |
| 9 | Regex | Default-Patterns aktiv, Custom Regex Editor (Tier 2) |
| 10 | LLM | 3 Modi: Embedded / Local API / None. Default: None. Nur per Button-Klick (Tier 3) |

### 7.1 Konfigurationsdatei-Struktur

```json
{
  "version": "1.0",
  "anonymization": {
    "pattern": "*",
    "length_strategy": "fixed",
    "preserve_separators": true,
    "skip_empty_fields": true,
    "consistent_pseudonymization": false
  },
  "regex_patterns": {
    "builtin": {
      "phone_international": true,
      "email": true,
      "date_formats": true,
      "swiss_ahv": true
    },
    "custom": [
      {
        "name": "German IBAN",
        "pattern": "DE\\d{2}\\s?\\d{4}\\s?\\d{4}\\s?\\d{4}\\s?\\d{4}\\s?\\d{2}",
        "description": "German bank account numbers",
        "enabled": true
      }
    ]
  },
  "llm": {
    "mode": "none",
    "embedded_model_path": "",
    "api": {
      "host": "http://localhost",
      "port": 11434,
      "endpoint": "/v1/chat/completions",
      "model_name": "",
      "api_key": ""
    },
    "prompt_template": "Identify all person-related data (names, addresses, phone numbers, IDs, dates of birth, insurance numbers) in the following HL7 field value. Return only a JSON array of found entities with type and position."
  },
  "profiles": {}
}
```

---

## 8. Risiken

| Risiko | Mitigation |
|--------|-----------|
| Eingabe ist häufig kein valides HL7 | Best-effort Parser + vollständige manuelle Selektion als gleichwertiger Hauptpfad |
| User übersieht sensible Felder | Wertbasierte Selektion, Suche, Selektionsliste, Disclaimer |
| Freitextfelder enthalten Patientendaten | Regex automatisch, LLM per Button, Warnung an User |
| LLM auf Remote-Host → Daten verlassen Rechner | Explizite Warnung + Bestätigung bei Non-localhost |
| LLM liefert False Positives | Ergebnisse immer als Vorschläge (Lila), nie auto-akzeptiert |
| API-Keys in Config im Klartext | Hinweis in Doku. Optional v2.x: OS-Keychain |
| PySide6 vergrößert .exe erheblich | Zielwert < 50 MB. Nuitka als Alternative wenn PyInstaller zu groß |

---

## 9. Referenz: Anforderungs-IDs

Detaillierte Anforderungs-IDs für Rückverfolgbarkeit vom Wireframe zu Work Items.

### Input
F-IN-01 (Paste-Eingabe), F-IN-02 (Message-Trennung), F-IN-03 (Non-HL7 Warnung), F-IN-04 (Ignored-Hinweis), F-IN-05 (Nachrichtenzähler), F-IN-06 (MSH-Validierung), F-IN-07 (Encoding Characters), F-IN-08 (Größenwarnung)

### Parsing & Auto-Detection
F-AN-01 (Best-effort Parse), F-AN-02 (Auto-Vorselektion), F-AN-03 (Graceful Degradation), F-AN-04 (Statusanzeige)

### Human-in-the-Loop Feldauswahl
F-HL-01 (Klickbare Felder), F-HL-02 (4-Farben-Schema), F-HL-03 (Hover-Preview), F-HL-04 (Bereichsmarkierung), F-HL-05 (Kontextmenü), F-HL-06 (Segment-Schnellauswahl), F-HL-07 (Wertbasierte Selektion), F-HL-08 (Suchfunktion), F-HL-09 (Tastaturnavigation), F-HL-10 (Selektionszähler), F-HL-11 (Selektionsliste Sidebar), F-HL-12 (Message-Tabs), F-HL-13 (Apply to all), F-HL-14 (Deselektieren)

### Regex
F-RE-01 (Regex-Engine), F-RE-02 (Default-Patterns), F-RE-03 (Auto-Vorselektion), F-RE-04 (Custom Editor), F-RE-04a (Pattern-Verwaltung), F-RE-04b (Testfunktion), F-RE-04c (Persistenz)

### LLM
F-LLM-01 (Embedded Model), F-LLM-02 (Local API), F-LLM-03 (Deaktiviert), F-LLM-10 (Analyse-Button), F-LLM-11 (Background Thread), F-LLM-12 (Abbruch), F-LLM-13 (Suggestions Lila), F-LLM-14 (Accept/Dismiss all), F-LLM-15 (Nur unselektierte Felder), F-LLM-20 (NER Prompt), F-LLM-21 (Feld-weise Analyse), F-LLM-22 (Prompt konfigurierbar), F-LLM-23 (Datenlokalität)

### Anonymisierung
F-AO-01 (Default-Muster *), F-AO-02 (Muster änderbar), F-AO-03 (Start-Button), F-AO-04 (Längenstrategie), F-AO-05 (Konsistente Pseudonymisierung), F-AO-06 (Leere Felder), F-AO-07 (Strukturerhalt)

### Output
F-OUT-01 (Textfeld), F-OUT-02 (Copy), F-OUT-03 (Export .txt), F-OUT-04 (Dateiname), F-OUT-05 (Diff-View), F-OUT-06 (Log)

### Config
F-CFG-01 (Config-Datei), F-CFG-02 (Speicherort), F-CFG-03 (Auto-laden/speichern), F-CFG-04 (Settings persistent), F-CFG-05 (LLM-Config), F-CFG-06 (Profile), F-CFG-07 (Export/Import), F-CFG-08 (Reset)