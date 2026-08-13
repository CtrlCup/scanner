from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from scanner_app.ocr.language_manager import AVAILABLE_LANGUAGES, DEFAULT_LANGUAGES, tessdata_dir
from scanner_app.resources import frozen_bundle_dir

# Ghostscript heißt unter Windows gswin64c/gswin32c statt gs — pro Werkzeug reicht ein
# Treffer aus den Kandidaten-Binärnamen (siehe missing_dependencies()).
_REQUIRED_TOOLS: dict[str, tuple[str, ...]] = {
    "tesseract": ("tesseract",),
    "qpdf": ("qpdf",),
    "ghostscript": ("gswin64c", "gswin32c") if sys.platform == "win32" else ("gs",),
}

_INSTALL_HINTS: dict[str, str] = {
    "tesseract": "https://github.com/UB-Mannheim/tesseract/wiki bzw. „choco install tesseract“",
    "qpdf": "https://github.com/qpdf/qpdf/releases bzw. „choco install qpdf“",
    "ghostscript": "https://www.ghostscript.com/download/gsdnld.html bzw. „choco install ghostscript“",
}


def _bundled_tools_dir() -> Path | None:
    """Verzeichnis mit mitgelieferten OCR-Programmen (tesseract/qpdf/ghostscript), falls der
    Build sie bündelt (siehe packaging/build_linux.sh bzw. package.yml für Windows) — None im
    Dev-Betrieb oder wenn ein Build sie (noch) nicht enthält, dann zählt ausschließlich das
    System-PATH.
    """
    base = frozen_bundle_dir()
    if base is None:
        return None
    candidate = base / "ocr-tools"
    return candidate if candidate.is_dir() else None


def _ensure_bundled_tools_available() -> None:
    """Stellt mitgelieferte OCR-Programme vor allen System-Installationen ins PATH und setzt
    GS_LIB, falls ein gebündeltes Ghostscript-Resource-Verzeichnis existiert (Ghostscript
    braucht das zwingend zusätzlich zur nackten Programmdatei). Läuft einmalig beim Import
    dieses Moduls — vor jedem `missing_dependencies()`- oder `apply_ocr()`-Aufruf, auch dem
    allerersten beim App-Start (Settings-Seite prüft die Abhängigkeiten schon beim Öffnen).

    Unterstützt zwei Layouts gleichzeitig: Linux (build_linux.sh) kopiert alle Programme +
    Shared Libraries flach in EIN gemeinsames Verzeichnis (rpath=$ORIGIN löst die
    Bibliotheken auf); Windows (package.yml) kopiert pro Werkzeug einen eigenen
    Unterordner (tesseract/, qpdf/, ghostscript/), da Windows-Programme ihre DLLs
    üblicherweise im eigenen Installationsordner statt zentral erwarten. Beide Formen landen
    daher im PATH: das Wurzelverzeichnis selbst UND alle direkten Unterordner.
    """
    bundled = _bundled_tools_dir()
    if bundled is None:
        return
    candidate_dirs = [bundled, *(p for p in bundled.iterdir() if p.is_dir())]
    path_entries = os.environ.get("PATH", "").split(os.pathsep)
    new_entries = [str(d) for d in candidate_dirs if str(d) not in path_entries]
    if new_entries:
        os.environ["PATH"] = os.pathsep.join([*new_entries, *path_entries])

    for resource_dir in bundled.glob("*/Resource"):
        os.environ["GS_LIB"] = str(resource_dir)
        break


_ensure_bundled_tools_available()


def missing_dependencies() -> list[str]:
    """Namen der OCR-Systemabhängigkeiten (tesseract/qpdf/ghostscript), die nicht im PATH
    gefunden wurden — leere Liste, wenn alles vorhanden ist. Günstig genug (nur `shutil.which`-
    Aufrufe, kein Prozessstart), um sie auch synchron im UI-Thread aufzurufen — z.B. um den
    OCR-Toggle in den Einstellungen vorab zu sperren (siehe Issue #6), statt den Nutzer erst
    nach einem gescheiterten Scan mit einer generischen Fehlermeldung zu konfrontieren.
    """
    return [name for name, candidates in _REQUIRED_TOOLS.items() if not any(shutil.which(c) for c in candidates)]


def dependency_hint(missing: list[str]) -> str:
    """Formatiert `missing_dependencies()`-Ergebnisse zu einem für Nutzer verständlichen
    Satz mit konkreten Installationshinweisen pro fehlendem Werkzeug.
    """
    details = "; ".join(f"{name} ({_INSTALL_HINTS[name]})" for name in missing)
    return f"Fehlende OCR-Abhängigkeiten: {details}."


class OcrError(Exception):
    """OCR konnte nicht angewendet werden (z.B. fehlende Systemabhängigkeiten)."""


def apply_ocr(
    pdf_path: Path | str, languages: list[str] | None = None, *, handwriting: bool = False
) -> Path:
    """Fügt dem PDF unter pdf_path in-place eine durchsuchbare Textebene hinzu.

    languages sind UI-Anzeigenamen (z.B. "Deutsch"), nicht Tesseract-Codes.

    handwriting schaltet Tesseract auf den reinen LSTM-Engine-Modus (oem=1), der auf
    unregelmäßiger/handschriftlicher Schrift tendenziell robuster ist als der kombinierte
    Standardmodus — Tesseract ist primär für Druckschrift trainiert, daher ist auch mit
    handwriting=True keine verlässliche Erkennung echter Handschrift zu erwarten.
    """
    import ocrmypdf
    from ocrmypdf.exceptions import EncryptedPdfError, MissingDependencyError

    missing = missing_dependencies()
    if missing:
        raise OcrError(dependency_hint(missing))

    languages = languages or list(DEFAULT_LANGUAGES)
    codes = [AVAILABLE_LANGUAGES[name] for name in languages]

    # ocrmypdf startet tesseract als Subprozess, der TESSDATA_PREFIX aus der Prozess-Umgebung
    # liest — es gibt keinen Weg, das Verzeichnis direkt als Parameter zu übergeben.
    os.environ["TESSDATA_PREFIX"] = str(tessdata_dir())

    pdf_path = Path(pdf_path)
    try:
        ocrmypdf.ocr(
            pdf_path,
            pdf_path,
            language=codes,
            force_ocr=True,  # unsere PDFs sind frisch aus Bildern erzeugt, nie vorab-OCRt
            progress_bar=False,
            tesseract_oem=1 if handwriting else None,
        )
    except MissingDependencyError as exc:
        # Sollte dank der Vorab-Prüfung oben kaum noch auftreten (z.B. bei kaputter statt
        # fehlender Installation) — bleibt als zweites Sicherheitsnetz mit generischerer Meldung.
        raise OcrError(
            "OCR-Engine (tesseract/qpdf/ghostscript) nicht gefunden oder unvollständig "
            "installiert."
        ) from exc
    except EncryptedPdfError as exc:
        raise OcrError("PDF ist verschlüsselt und kann nicht mit OCR versehen werden.") from exc

    return pdf_path
