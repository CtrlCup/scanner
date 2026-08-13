# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Projektziel

Plattformübergreifende Dokumentenscanner-Anwendung mit moderner UI (Windows + Linux). Zugriff auf
im Betriebssystem hinterlegte Scanner/Drucker, Mehrseiten-PDF-Erstellung mit direktem Speichern
nach jedem Scan, Seitenverwaltung (löschen, neu anordnen, rotieren), OCR-Texterkennung vor dem
PDF-Speichern.

**UI-Vorlage (verbindlich, pixelgetreu umzusetzen):** von Alex als HTML-Mockup vorgegeben
(`Dokumentenscanner-UI.html`, ein selbstentpackendes Claude-Artifact-Bundle — die eigentliche
Struktur/Styles/Farbwerte liegen darin base64/gzip-komprimiert in
`<script type="__bundler/template">` bzw. `__bundler/manifest`; zum Auslesen im Browser öffnen
oder das Manifest per Python `base64.b64decode` + `gzip.decompress` entpacken). Referenzlayout:
selbstgezeichnete Titelleiste („Scanner" + eigene Minimize/Maximize/Close-Buttons), schmale
Icon-Leiste ganz links (Scan-Button oben, Ordner-Icon = **Speicherort öffnen** — nicht wählen —
und Zahnrad unten), Einstellungspanel (Scanner-Karte, Quelle, Dateityp, Farbmodus, Auflösung,
Helligkeit/Kontrast, automatische Bildkorrektur, Scan-Button + „+"), rechtes Vorschau-Panel
(weiße „Papier"-Karte mit Schatten + Thumbnail-Leiste). Exakte Farbwerte/Abstände siehe
`src/scanner_app/ui/theme.py` (Light-/Dark-Palette 1:1 aus dem Mockup übernommen).

**Falle beim Nachbauen der Mockup-SVG-Icons:** `QSvgRenderer.render(painter)` **ohne**
Ziel-`QRectF` zeichnet in der nativen viewBox-Größe des SVGs (z.B. 24×24 Einheiten) oben links
in die Pixmap statt auf deren volle Größe skaliert — sichtbar als abgeschnittenes Mini-Icon in
der Ecke. Zusätzlich ignoriert `QtSvg` `rgba(...)`-Farbfunktionen in `stroke`/`fill`-Attributen
lautlos (Icon bleibt unsichtbar) — dort sind nur Hex-/Named-/`rgb()`-Farben zulässig, siehe
`src/scanner_app/ui/icons.py::svg_icon()`.

## Tech-Stack

- **Python** (>=3.10) mit **PySide6** (Qt6) für die UI. Bewusste Kursänderung gegenüber einer
  früheren Version dieser Datei: die App verwendet **kein natives Fensterdekor** mehr, sondern
  ein komplett selbstgezeichnetes Fenster (`FramelessWindowHint` + `WA_TranslucentBackground`,
  eigene Titelleiste mit Minimize/Maximize/Close, abgerundete Ecken, Schlagschatten via
  `QGraphicsDropShadowEffect`, Rand-Resize über `QWindow.startSystemResize()`) — Ziel ist ein auf
  Windows und Linux pixelidentisches Erscheinungsbild nach dem verbindlichen Design-Mockup
  (siehe unten), da native Titelleisten sich zwischen den Plattformen sichtbar unterscheiden.
  Siehe `src/scanner_app/ui/main_window.py` (`_ResizableRoot`, `MainWindow`) und
  `src/scanner_app/ui/widgets/window_chrome.py` (`TitleBar`, `IconRail`).
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

**⚠️ Echtes `sane.get_devices()` in diesem Sandbox-Setup kann abstürzen:** Das installierte
`libsane-epson2`-Backend crasht (nativer Segfault, in Python nicht abfangbar) bei wiederholten
`sane.init()`/`sane.exit()`-Zyklen im selben Prozess (z.B. viele Tests hintereinander, die je
ein `MainWindow()` konstruieren) — vermutlich ein Bug in dessen Netzwerk-Geräteerkennung. Deshalb
verwenden UI-Tests (`tests/test_ui_flow.py`) grundsätzlich ein gemocktes `get_backend()`
(`_FakeScannerBackend`), nie den echten `SaneScannerBackend` — nicht nur aus
Geschwindigkeitsgründen, sondern aus Stabilitätsgründen. Beim Schreiben neuer Tests, die
`MainWindow()` konstruieren, dieses Pattern übernehmen statt echtes SANE laufen zu lassen.

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

# Distributionspakete bauen (Linux: tar.gz, AppImage, deb, rpm — siehe unten)
pip install -e ".[build]"
bash packaging/build_linux.sh
```

## Distributionspakete

`packaging/scanner.spec` ist die PyInstaller-Spec (onedir-Bundle, gemeinsam für Linux und
Windows genutzt). `packaging/build_linux.sh` baut daraus lokal `.tar.gz`, `.AppImage`, `.deb`
und `.rpm` (Ausgabe in `dist/packages/`). Benötigt zusätzlich `appimagetool` und `fpm`
(`gem install fpm`) im PATH — beide sind nicht Teil des Python-Envs.

Der Windows-`.exe`-Build läuft ausschließlich über den GitHub-Actions-Workflow
`.github/workflows/package.yml` (Job `windows`, `windows-latest`-Runner) — hier gibt es keine
Windows-Umgebung zum lokalen Bauen/Testen.

`package.yml` wird nach jedem erfolgreichen Release automatisch von `release.yml` per
`gh workflow run package.yml -f tag=vX.Y.Z` angestoßen (**nicht** über den `v*`-Tag-Push
selbst — ein von `GITHUB_TOKEN` gepushter Tag löst laut GitHub-Rekursionsschutz keine
weiteren Workflow-Runs aus, daher der explizite Dispatch mit `tag`-Input). Mit gesetztem
`tag`-Input werden die gebauten Dateien zusätzlich per `gh release upload` an das
entsprechende GitHub-Release angehängt — jede Datei mit einem beschreibenden Label
(`Datei#Label`-Syntax), zusätzlich hängt der Job `annotate-release` eine Downloads-Tabelle
an den Release-Text an. Manueller Lauf ohne Release-Upload: `gh workflow run package.yml`
(Artefakte dann nur über `gh run download` abrufbar, laufen nach ~90 Tagen ab).

`packaging/scanner.spec` baut plattformabhängig unterschiedlich: Windows als **Onefile**
(eine einzelne `Scanner.exe`, das ist die als `.exe` erwartete Datei), Linux als **Onedir**
(Ordner mit `Scanner` + `_internal/`, passend für AppImage/deb/rpm/tar.gz).

Windows bekommt zusätzlich einen echten Installer über `packaging/scanner.iss`
(Inno Setup, im `windows`-Job via `choco install innosetup` + `ISCC.exe` gebaut) —
`Scanner-X.Y.Z-windows-x86_64-setup.exe` mit Startmenü-Eintrag und sauberer
Deinstallation über die Windows-Einstellungen. Die portable `Scanner.exe` bleibt zusätzlich
als Download bestehen, für alle, die nichts installieren wollen.

`packaging/icon.png`/`icon.ico` sind ein generischer Platzhalter (kein echtes Markenlogo) —
bei Bedarf ersetzen.

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
  Einstellungsseite, Theme/QSS)
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
- **Update-Check** (`scanner_app/update_checker.py`): fragt die GitHub-Releases-API ab und
  vergleicht gegen `scanner_app.__version__`. MVP-Scope bewusst begrenzt (siehe Issue #2):
  informiert nur (Dialog + Link zur Release-Seite), lädt/installiert nichts automatisch — kein
  Checksummen-/Signatur-Check, kein stiller Ersatz der laufenden Datei. Läuft immer in einem
  Hintergrund-Thread, schlägt bei fehlendem Internet still fehl (gibt `None` zurück statt zu
  werfen). Automatischer Start-Check ~1,5s nach Fensteröffnung, abschaltbar über
  `auto_update_check_enabled`; die Prüfung dieser Einstellung erfolgt bewusst erst beim
  Timer-Feuern, nicht beim Scheduling (relevant für Tests, die sie direkt danach ändern).
- Einstellungen sind eine **eingebettete Seite** (`SettingsPage`, `QStackedWidget` in
  `main_window.py`), kein separates Fenster/Dialog — Navigation über das Zahnrad in der
  `IconRail` (hin, siehe `window_chrome.py`) und den Zurück-Pfeil im Seitenkopf (zurück). Der
  Seiteninhalt liegt in einer `QScrollArea` mit auf ~520px begrenzter, zentrierter Breite (sonst
  zieht sich jede Zeile über die volle Fensterbreite); am Ende der `content`-Layout steht bewusst
  ein `addStretch()`, sonst verteilt Qt überschüssige Höhe auf die Zeilen und bläst sie unnötig
  auf. Bei künftigen neuen Optionen ins `content`-Widget der Scroll-Area einhängen, nicht direkt
  in `outer_layout`.
- **Ordner-Icon in der `IconRail`** (unten links, über dem Zahnrad) **öffnet** den aktuellen
  Speicherort im OS-Dateimanager (`QDesktopServices.openUrl`) — es öffnet **keinen**
  Verzeichnisauswahl-Dialog. Den Speicherort **ändern** kann man ausschließlich über
  „Standard-Speicherort" → „Durchsuchen…" auf der Einstellungen-Seite. Beim Hovern über das
  Ordner-Icon zeigt ein `PathPopover` (siehe `window_chrome.py`) den aktuellen Pfad.
- Weitere App-Settings ohne direkte Entsprechung im ursprünglichen Design-Mockup, aber reale
  Funktionalität (siehe `app_settings.py`): `auto_load_last_scanner` (steuert, ob
  `SettingsPanel.refresh_devices()` den zuletzt verwendeten Scanner vorauswählt),
  `show_thumbnails` (blendet die Thumbnail-Leiste im Vorschau-Panel aus), `notify_on_finish`
  (steuert die Toast-Meldung nach dem Speichern eines Scans — das eingebettete `Toast`-Widget,
  keine OS-Benachrichtigung), `default_filename_pattern` (Dateinamensmuster mit Platzhaltern
  `{Datum}` und `{Nummer}`, siehe `models/document.py::generate_filename()` — enthält das Muster
  `{Nummer}`, sucht `MainWindow._first_free_path()` die nächste freie laufende Nummer im
  Zielordner statt wie sonst „ (2)", „ (3)" anzuhängen).
