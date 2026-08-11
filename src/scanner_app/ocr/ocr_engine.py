from __future__ import annotations

import os
from pathlib import Path

from scanner_app.ocr.language_manager import AVAILABLE_LANGUAGES, DEFAULT_LANGUAGES, tessdata_dir


class OcrError(Exception):
    """OCR konnte nicht angewendet werden (z.B. fehlende Systemabhängigkeiten)."""


def apply_ocr(pdf_path: Path | str, languages: list[str] | None = None) -> Path:
    """Fügt dem PDF unter pdf_path in-place eine durchsuchbare Textebene hinzu.

    languages sind UI-Anzeigenamen (z.B. "Deutsch"), nicht Tesseract-Codes.
    """
    import ocrmypdf
    from ocrmypdf.exceptions import EncryptedPdfError, MissingDependencyError, TesseractNotFoundError

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
        )
    except (MissingDependencyError, TesseractNotFoundError) as exc:
        raise OcrError(
            "OCR-Engine (tesseract/qpdf/ghostscript) nicht gefunden oder unvollständig "
            "installiert."
        ) from exc
    except EncryptedPdfError as exc:
        raise OcrError("PDF ist verschlüsselt und kann nicht mit OCR versehen werden.") from exc

    return pdf_path
