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
- **`QApplication.setStyle("Fusion")` ist Pflicht** (`main.py`), nicht optional/kosmetisch:
  native Stile (v.a. Windows' `windowsvista`) zeichnen für Buttons/Slider/ComboBoxen eigene
  Chrome-Elemente, die eigenes QSS (abgerundete Ecken, benutzerdefinierte Slider-Handles) nur
  teilweise überschreiben kann — sichtbar als eckige, nicht abgerundete Buttons bzw. graue
  Ränder um Slider-Handles unter Windows, obwohl auf Linux (bzw. im hiesigen Offscreen-
  Testsetup) alles korrekt aussah. Ohne `setStyle("Fusion")` ist das plattformübergreifende
  Pixel-Identität-Ziel (siehe oben) nicht erreichbar.
- **Scanner-Zugriff:** `python-sane` unter Linux (SANE), WIA via `pywin32`-COM-Automation unter
  Windows — siehe `src/scanner_app/backend/`. WIA/COM-Objekte sind apartment-gebunden (STA):
  `WiaScannerBackend` hält ihr `WIA.DeviceManager`-COM-Objekt daher `threading.local()` (mit
  `pythoncom.CoInitialize()` pro Thread) statt als geteiltes Instanzattribut — ein aus dem
  Haupt-Thread erzeugtes COM-Objekt, das der Scan-Hintergrund-Thread (`MainWindow._ScanWorker`)
  weiterverwendet, kann je nach Windows-Version ohne Exception dauerhaft blockieren.
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

## QThread-Worker: Referenz auf das Worker-Objekt selbst behalten

Beim Muster `thread = QThread(); worker = SomeWorker(); worker.moveToThread(thread); ...` reicht
es **nicht**, nur `thread` in einer Instanzliste/-variable am Leben zu halten — wird `worker`
nirgends zusätzlich referenziert, kann Pythons Garbage Collector es einsammeln, sobald die
aufrufende Methode zurückkehrt. Die Signal/Slot-Verbindung (`worker.finished.connect(...)`)
schützt in PySide6 **nicht** zuverlässig davor. Symptom: der Worker läuft im Hintergrund-Thread
zwar durch, sein `finished`/`failed`-Signal kommt aber nie beim UI-Thread an — sichtbar als eine
UI, die dauerhaft im „lädt …"-Zustand hängen bleibt, ohne jede Fehlermeldung. Dieser Bug war real
und per Test reproduzierbar (nicht nur eine Windows-Vermutung) in `SettingsPage._run_in_background()`
/`_start_update_check()`, behoben durch eine zusätzliche `self._workers`-Liste analog zu
`self._threads`. Beim Schreiben neuer Hintergrund-Worker immer **beide** Objekte (Thread UND
Worker) in einer Instanzvariable halten, bis der Worker fertig ist — siehe `MainWindow._start_scan()`/
`_start_auto_update()` für das korrekte Muster (`self._scan_worker`/`self._update_worker`).

Zusätzlich gilt seither für **jeden** Worker: `run()` muss jede Exception abfangen und in jedem
Fall ein Terminalsignal (`finished`/`failed`) emittieren — ein unerwarteter, nicht abgefangener
Fehlertyp hätte sonst denselben "hängt für immer"-Effekt, unabhängig vom Referenz-Bug oben.

## Bekannte Einschränkung dieser Dev-Umgebung

Diese Session läuft in WSL2 (Linux). Der Windows-WIA-Backend-Code (`backend/windows_wia.py`) kann
hier **nicht** getestet werden — nur auf Syntax-/Importebene verifizierbar, nicht funktional. Echte
Scanner-Hardware ist hier ebenfalls nicht angeschlossen; SANE-Backend wird gegen `python-sane`
entwickelt, aber ohne physisches Gerät nur bis zur Geräteerkennung testbar. Gleiches gilt für
`windows_updater.py`: `is_installed_windows_build()` liefert hier immer `False` (kein `win32`),
und der eigentliche stille Installer-Start (`/VERYSILENT ...`) lässt sich nur auf echtem Windows
end-to-end verifizieren — Download/Prüfsummen-Logik ist dagegen reines, plattformunabhängiges
Python und wird in `tests/test_windows_updater.py` reell getestet (nur `subprocess.Popen` bzw.
`urllib.request.urlopen` gemockt).

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

Beide Windows-Dateien bekommen zusätzlich eine `.sha256`-Sidecar-Datei (`sha256sum`-Format)
mit an das Release angehängt — die des Installers wird vom automatischen Update
(`windows_updater.py`) zur Verifikation vor der stillen Ausführung benötigt; ohne dieses Asset
in einem Release bietet der Update-Dialog dort keine automatische Installation an, nur den
Hinweis-Dialog.

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
- `src/scanner_app/ocr/` — OCR-Pipeline (`ocrmypdf`-Wrapper, Sprachpaket-Verwaltung,
  `ocr_engine.missing_dependencies()`/`dependency_hint()` für die Abhängigkeitsprüfung)
- `src/scanner_app/pdf/` — PDF-/Bild-Erstellung/-Aktualisierung aus `Document`, inkl. Löschen/
  Neuordnen/Rotieren bestehender Seiten
- `src/scanner_app/update_checker.py` — GitHub-Releases-Abfrage, liefert bei den
  Windows-Installer-Assets zusätzlich deren Download- und `.sha256`-URLs (siehe
  `windows_updater.py`)
- `src/scanner_app/windows_updater.py` — Download+Prüfsummen-Verifikation+stiller Start des
  Windows-Installers für das automatische Update (siehe Funktionslogik unten); reine Windows-
  Funktionalität, aber ohne `win32`-Import auf Modulebene plattformübergreifend importierbar/
  testbar (`is_installed_windows_build()` liefert auf anderen Plattformen einfach `False`)
- `src/scanner_app/ui/` — UI-Code (Hauptfenster, Einstellungspanel, Vorschau/Thumbnail-Strip,
  Einstellungsseite, Theme/QSS, `icons.py` für die SVG-Icons aus dem Design-Mockup)
- `tests/` — pytest-Tests

## Funktionslogik (aus Anforderung, nicht aus Code ableitbar)

- **Scannen** (`SettingsPanel`-Fußzeile bzw. Rail-Icon bzw. Strg+Eingabe): Verhalten hängt von
  der Einstellung **„Beim Scannen standardmäßig"** (`AppSettings.scan_default_mode`,
  `"append"`/`"new"`) ab — bei `"append"` wird an das aktuelle PDF-Dokument angehängt (sofern
  Dateityp weiterhin PDF ist und das aktuelle Dokument noch nicht gespeichert/leer ist), bei
  `"new"` wird immer neu begonnen. Der Chevron-Button daneben öffnet ein Menü mit den zwei
  expliziten Aktionen **„Scannen"** (= derselbe modusabhängige Klick, Kurzbefehl Strg+Eingabe)
  und **„Scannen und neu beginnen"** (verwirft das aktuelle Dokument immer, unabhängig vom
  Standardmodus, Kurzbefehl Strg+N). Einzelbild-Dateitypen (JPG/PNG/TIF/BMP) beginnen wegen
  `Document.can_add_page` (nur PDF erlaubt Mehrseiten) so oder so bei jedem Scan neu. Siehe
  `MainWindow._perform_scan()`.
- **Dateityp**: PDF (mehrseitig) oder JPG/PNG/TIF/BMP (Einzelbild, `DocumentType`-Enum-Wert =
  Dateiendung). Bei JPG/BMP wird eine RGBA-Quelle vor dem Speichern auf weißem Hintergrund
  flachgezeichnet (`pdf_writer.write_image`), da diese Formate keinen Alpha-Kanal unterstützen.
- **Scan läuft im Hintergrund-Thread** (`MainWindow._ScanWorker`, nie im UI-Thread — sonst
  friert das Fenster während des oft mehrere Sekunden blockierenden SANE/WIA-Aufrufs ein).
  Während ein Scan läuft, ist das gesamte Einstellungspanel gesperrt
  (`SettingsPanel.set_scanning()`), die Scan-Zeile wird durch Spinner + „Scan läuft…" + einen
  **Abbrechen**-Button ersetzt. Echte Scanner-Backends lassen sich nicht sauber mitten im Aufruf
  unterbrechen — „Abbrechen" markiert das kommende Ergebnis nur als zu verwerfen und gibt die
  UI sofort frei, der Hintergrund-Aufruf läuft bis zu seinem natürlichen Ende weiter durch.
- Nach **jedem** Scan sowie nach Löschen/Rotieren/Neuordnen wird die Ausgabedatei sofort im
  eingestellten Speicherpfad geschrieben/aktualisiert (nicht erst bei explizitem „Speichern") —
  jeweils mit einem Toast („Gespeichert: …", `AppSettings.notify_on_finish`-gesteuert) bestätigt.
- Seiten-Thumbnail-Leiste: Löschen per „×" auf der Kachel, Neuanordnen per Drag & Drop,
  Rotieren per Button oberhalb der Vorschau (wirkt auf die aktuell fokussierte Seite).
- OCR wird, falls in den Einstellungen aktiviert, beim PDF-Schreiben automatisch angewendet
  (Sprachen aus den Einstellungen, Standardsprachen Deutsch+Englisch vorinstalliert, weitere
  Sprachen werden bei Auswahl im Hintergrund nachgeladen).
- **OCR-Abhängigkeitsprüfung** (`ocr_engine.missing_dependencies()`, Issue #6): prüft per
  `shutil.which()`, ob `tesseract`, `qpdf` und Ghostscript (`gs` unter Linux/macOS,
  `gswin64c`/`gswin32c` unter Windows) im PATH gefunden werden. Fehlt eines davon, ist der
  OCR-Toggle in den Einstellungen von vornherein deaktiviert (mit Hinweistext + Installations-
  Links pro fehlendem Tool, `SettingsPage._refresh_ocr_dependency_state()`) — statt den Fehler
  erst nach einem gescheiterten Scan über die generische `MissingDependencyError`-Meldung von
  `ocrmypdf` zu zeigen. `apply_ocr()` prüft zusätzlich selbst vorab (zweites Sicherheitsnetz für
  den Fall, dass ein Tool zwischen App-Start und Scan aus dem PATH verschwindet).
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
  vergleicht gegen `scanner_app.__version__`. Läuft immer in einem Hintergrund-Thread, schlägt
  bei fehlendem Internet still fehl (gibt `None` zurück statt zu werfen). Automatischer
  Start-Check ~1,5s nach Fensteröffnung, abschaltbar über `auto_update_check_enabled`; die
  Prüfung dieser Einstellung erfolgt bewusst erst beim Timer-Feuern, nicht beim Scheduling
  (relevant für Tests, die sie direkt danach ändern).
- **Automatische Installation (nur Windows-Installer-Build)**: über das ursprüngliche MVP
  (Issue #2, nur Hinweis+Link) hinaus erweitert — `update_checker.check_for_update()` liest bei
  gefundenem neueren Release zusätzlich die Download-URLs des Windows-Setup-Assets und seiner
  vom Release-Workflow mitveröffentlichten `.sha256`-Sidecar-Datei (`package.yml`) aus den
  GitHub-Release-Assets. Der Update-Dialog (`MainWindow._on_update_available`) bietet einen
  „Jetzt installieren"-Button **nur** an, wenn `windows_updater.is_installed_windows_build()`
  zutrifft (erkannt am `unins000.exe`-Uninstaller neben der laufenden `sys.executable` — nie
  für die portable `.exe` oder einen Start aus dem Quellcode) UND beide URLs vorhanden sind.
  Ablauf bei Klick (`MainWindow._start_auto_update`, Hintergrund-Thread
  `_UpdateInstallWorker`): Prüfsumme laden → Installer laden (mit Fortschritts-Dialog +
  Abbrechen) → SHA-256 gegen die Prüfsumme verifizieren (Pflicht — ein automatisch gestarteter
  Installer darf nie eine unverifizierte Datei ausführen, siehe `windows_updater.py`) → still
  installieren (`/VERYSILENT /CLOSEAPPLICATIONS /RESTARTAPPLICATIONS`, nutzt Inno Setups
  Windows-Restart-Manager-Integration aus `scanner.iss`) → App beendet sich selbst geordnet
  (`self.close()`), der Installer startet die neue Version danach automatisch neu. Für
  Linux/portable-Windows/Dev-Läufe bleibt es beim reinen Hinweis-Dialog mit Link zur
  Release-Seite.
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
