# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Projektziel

Plattformübergreifende Dokumentenscanner-Anwendung mit moderner UI (Windows + Linux). Zugriff auf
im Betriebssystem hinterlegte Scanner/Drucker, Mehrseiten-PDF-Erstellung mit direktem Speichern
nach jedem Scan, Seitenverwaltung (löschen, neu anordnen, rotieren), OCR-Texterkennung vor dem
PDF-Speichern.

UI-Vorlage: Figma-artiges Claude-Design unter `claude.ai/design/p/476beec9-...` ("Scanner App").
Referenzlayout: Fenstertitel mit Scanner-Namen, linkes Einstellungspanel (Scanner-Auswahl, Quelle,
Dateityp, Farbmodus, Auflösung, Helligkeit/Kontrast, automatische Bildkorrektur), rechtes
Vorschau-Panel (großer Preview + Thumbnail-Leiste der gescannten Seiten), Gear-Icon für
App-Einstellungen (OCR an/aus + Sprachauswahl, Theme, Speicherpfad).

## Tech-Stack

- **Python** (>=3.10) mit **PySide6** (Qt6) für die UI — natives Fenster pro Betriebssystem
  (kein selbstgezeichneter Fensterrahmen), Look & Feel per QSS an das Design angenähert
- **Scanner-Zugriff:** `python-sane` unter Linux (SANE), WIA via `pywin32`-COM-Automation unter
  Windows — siehe `src/scanner_app/backend/`
- **PDF/Bild:** `Pillow` (Bildbearbeitung/Rotation/Thumbnails), `img2pdf` (verlustfreie
  Bild→PDF-Konvertierung), `pypdf` (Seiten löschen/neu anordnen/rotieren in bestehendem PDF)
- **OCR:** `ocrmypdf` (wrapt Tesseract, fügt durchsuchbare Textebene ins PDF ein). Benötigt
  System-Binaries `tesseract`, `qpdf`, `ghostscript` — nicht über pip installierbar.
- Paketierung/Build-Backend: `setuptools` über `pyproject.toml` (PEP 621), src-Layout

## Versionierung

**SemVer + Conventional Commits, automatisiert über `python-semantic-release`.** Startversion:
`0.0.1` (siehe `pyproject.toml` `[project.version]` und `src/scanner_app/__init__.py:__version__`
— beide werden von semantic-release synchron gehalten, siehe `[tool.semantic_release]` in
`pyproject.toml`).

Commit-Messages **müssen** dem Conventional-Commits-Format folgen, sonst wird kein Release
ausgelöst:

- `feat: ...` → Minor-Bump
- `fix: ...` → Patch-Bump
- `perf: ...` → Patch-Bump
- `feat!: ...` / Footer `BREAKING CHANGE: ...` → Major-Bump (sobald >0.x; siehe `major_on_zero`)
- `chore:`, `docs:`, `refactor:`, `test:`, `ci:`, `style:` → kein Release

Release-Workflow (`.github/workflows/release.yml`) läuft bei jedem Push auf `main` und erstellt
bei releasefähigen Commits automatisch Git-Tag (`vX.Y.Z`), GitHub-Release und aktualisiert
`CHANGELOG.md`. `.github/workflows/ci.yml` führt bei jedem Push/PR Tests + Lint auf Linux und
Windows aus.

## Bekannte Einschränkung dieser Dev-Umgebung

Diese Session läuft in WSL2 (Linux). Der Windows-WIA-Backend-Code (`backend/windows_wia.py`) kann
hier **nicht** getestet werden — nur auf Syntax-/Importebene verifizierbar, nicht funktional. Echte
Scanner-Hardware ist hier ebenfalls nicht angeschlossen; SANE-Backend wird gegen `python-sane`
entwickelt, aber ohne physisches Gerät nur bis zur Geräteerkennung testbar.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

Unter Windows entsprechend `.venv\Scripts\pip install -e ".[dev]"`.

System-Abhängigkeiten (Linux, Debian/Ubuntu):

```bash
sudo apt-get install -y libsane-dev sane-utils tesseract-ocr tesseract-ocr-deu tesseract-ocr-eng qpdf ghostscript
```

## Häufige Befehle

```bash
# App starten
.venv/bin/scanner
# äquivalent:
.venv/bin/python -m scanner_app.main

# Tests
.venv/bin/pytest

# einzelnen Test ausführen
.venv/bin/pytest tests/test_smoke.py::test_import

# Linting
.venv/bin/ruff check .

# Version/Release lokal simulieren (ohne zu veröffentlichen)
.venv/bin/semantic-release version --print
```

## Architektur

- `src/scanner_app/main.py` — Einstiegspunkt, startet `QApplication` + Hauptfenster
- `src/scanner_app/app_settings.py` — persistente Einstellungen (QSettings): Speicherpfad,
  OCR an/aus + Sprachen, Theme, zuletzt verwendeter Scanner
- `src/scanner_app/models/` — Domain-Modell: `Document`/`Page` (Bild, Rotation, Reihenfolge),
  unabhängig von UI und Backend testbar
- `src/scanner_app/backend/` — Scanner-Zugriff hinter gemeinsamer Schnittstelle
  (`base.py`: `ScannerBackend` ABC, `ScannerDevice`, `ScanOptions`); `linux_sane.py` und
  `windows_wia.py` sind austauschbare Implementierungen, `factory.py` wählt per Plattform aus.
  Die UI-Schicht kennt nur die Abstraktion, nie die Plattformdetails.
- `src/scanner_app/ocr/` — OCR-Pipeline (`ocrmypdf`-Wrapper, Sprachpaket-Verwaltung)
- `src/scanner_app/pdf/` — PDF-Erstellung/-Aktualisierung aus `Document`, inkl. Löschen/
  Neuordnen/Rotieren bestehender Seiten
- `src/scanner_app/ui/` — UI-Code (Hauptfenster, Einstellungspanel, Vorschau/Thumbnail-Strip,
  Einstellungsdialog, Theme/QSS)
- `tests/` — pytest-Tests

## Funktionslogik (aus Anforderung, nicht aus Code ableitbar)

- **Neue Seite scannen** (Dateityp PDF): erzeugt bei leerem aktuellem Dokument ein neues PDF;
  bei vorhandenem Dokument wird per separatem **„+" (Seite hinzufügen)**-Button eine Seite an das
  aktuelle Dokument angehängt — „Neue Seite scannen" startet in dem Fall stattdessen ein
  **komplett neues** Dokument (fragt ggf. nach, da vorherige Seiten sonst verworfen werden).
- **„+" (Seite hinzufügen) ist ausgegraut**, wenn Dateityp = Bild ist (Bilder sind immer
  Einzelseiten, kein Mehrseiten-Konzept).
- Nach **jedem** Scan wird die PDF-Datei sofort im eingestellten Speicherpfad geschrieben/
  aktualisiert (nicht erst bei explizitem „Speichern").
- Seiten-Thumbnail-Leiste: Löschen per „×" auf der Kachel, Neuanordnen per Drag & Drop,
  Rotieren per Button oberhalb der Vorschau (wirkt auf die aktuell fokussierte Seite).
- OCR wird, falls in den Einstellungen aktiviert, beim PDF-Schreiben automatisch angewendet
  (Sprachen aus den Einstellungen, Standardsprachen Deutsch+Englisch vorinstalliert, weitere
  Sprachen werden bei Auswahl im Hintergrund nachgeladen).
- **Automatisches Drehen** (eigener Einstellungen-Toggle, unabhängig von OCR): nach jedem Scan
  wird die Ausrichtung der Seite per Tesseract-OSD (`scanner_app/ocr/orientation.py`) erkannt
  und die Seite automatisch in die erkannte Richtung gedreht — best effort, bei fehlender
  Erkennung (z.B. zu wenig Text) bleibt die Seite unverändert. Benötigt `osd.traineddata`,
  wird beim Aktivieren des Toggles bei Bedarf im Hintergrund heruntergeladen.
- **Handschrift-Erkennung** (Toggle nur sichtbar, wenn OCR aktiviert ist): schaltet Tesseract
  auf den reinen LSTM-Engine-Modus (`oem=1`) um. Realistische Erwartungshaltung: Tesseract ist
  primär für Druckschrift trainiert, auch mit diesem Modus ist echte Handschrift nur begrenzt
  zuverlässig erkennbar.
- Der Einstellungsdialog-Inhalt liegt in einer `QScrollArea` — bei künftigen neuen Optionen
  nicht direkt in `QVBoxLayout(self)` einhängen, sondern in das `content`-Widget der
  Scroll-Area, sonst quetscht Qt bei zu viel Inhalt einzelne Zeilen ohne Fehlermeldung
  unsichtbar zusammen (siehe Git-History zu `settings_dialog.py` für das konkrete Symptom).
