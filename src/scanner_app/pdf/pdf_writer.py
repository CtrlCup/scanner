from __future__ import annotations

import io
from pathlib import Path

import img2pdf
from PIL import Image

from scanner_app.models.document import Document, DocumentType, Page


def _rotated_png_bytes(page: Page) -> bytes:
    """Render a page's source image at its current rotation, re-encoded as PNG.

    Rotation is never applied to the source file — it's re-derived on every
    export so that undoing a rotation or re-ordering pages needs no extra state.
    """
    with Image.open(page.image_path) as image:
        if page.rotation:
            # PIL rotates counter-clockwise for positive angles; our rotation is clockwise.
            image = image.rotate(-page.rotation, expand=True)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()


def write_pdf(document: Document, output_path: Path | str) -> Path:
    if document.document_type is not DocumentType.PDF:
        raise ValueError("write_pdf erwartet ein Dokument vom Typ PDF.")
    if document.is_empty:
        raise ValueError("Dokument enthält keine Seiten.")

    page_images = [_rotated_png_bytes(page) for page in document.pages]
    pdf_bytes = img2pdf.convert(page_images)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(pdf_bytes)
    return output_path


# JPG und BMP unterstützen keinen Alpha-Kanal — Pillow würde beim Speichern einer RGBA-Quelle
# in diese Formate mit OSError abbrechen, daher vorher auf weißem Hintergrund flach zeichnen.
_NO_ALPHA_EXTENSIONS = {"jpg", "bmp"}


def write_image(document: Document, output_path: Path | str) -> Path:
    if document.document_type is DocumentType.PDF:
        raise ValueError("write_image erwartet ein Dokument vom Typ Bild.")
    if document.is_empty:
        raise ValueError("Dokument enthält keine Seite.")

    page = document.pages[0]
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(page.image_path) as image:
        if page.rotation:
            image = image.rotate(-page.rotation, expand=True)
        extension = output_path.suffix.lstrip(".").lower()
        if extension in _NO_ALPHA_EXTENSIONS and image.mode in ("RGBA", "LA", "PA"):
            background = Image.new("RGB", image.size, "white")
            background.paste(image.convert("RGBA"), mask=image.convert("RGBA").split()[-1])
            image = background
        image.save(output_path)
    return output_path


def save_document(document: Document, output_path: Path | str) -> Path:
    """Rebuild the document's output file from its current pages/rotation/order.

    Called after every mutating action (scan, delete, reorder, rotate) so the
    file at `output_path` always reflects the current state — never a manual
    'save' step.
    """
    if document.document_type is DocumentType.PDF:
        return write_pdf(document, output_path)
    return write_image(document, output_path)
