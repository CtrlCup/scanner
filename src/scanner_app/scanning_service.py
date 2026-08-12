from __future__ import annotations

from pathlib import Path

from scanner_app.models.document import Document, DocumentType
from scanner_app.ocr.ocr_engine import apply_ocr
from scanner_app.pdf.pdf_writer import save_document


def save_and_process(
    document: Document,
    output_path: Path | str,
    *,
    ocr_enabled: bool = False,
    ocr_languages: list[str] | None = None,
    handwriting_enabled: bool = False,
) -> Path:
    """Schreibt/aktualisiert die Ausgabedatei aus dem aktuellen Dokumentzustand und wendet
    danach optional OCR an. Wird nach jedem Scan sowie nach Löschen/Neuordnen/Rotieren
    aufgerufen, damit die Datei im Speicherpfad immer den aktuellen Stand widerspiegelt.

    Löst scanner_app.ocr.OcrError, falls OCR aktiviert ist, aber fehlschlägt — die PDF ist
    dann trotzdem bereits ohne Textebene gespeichert (save_document lief vorher erfolgreich).
    """
    path = save_document(document, output_path)
    if ocr_enabled and document.document_type is DocumentType.PDF:
        apply_ocr(path, ocr_languages, handwriting=handwriting_enabled)
    return path
