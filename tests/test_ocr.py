import shutil

import pytest
from PIL import Image, ImageDraw

from scanner_app.models.document import Document, DocumentType
from scanner_app.ocr.language_manager import is_language_installed
from scanner_app.pdf.pdf_writer import save_document
from scanner_app.scanning_service import save_and_process

_OCR_AVAILABLE = (
    shutil.which("tesseract") is not None
    and shutil.which("qpdf") is not None
    and shutil.which("gs") is not None
    and is_language_installed("Englisch")
)


def _make_text_image(path):
    image = Image.new("RGB", (600, 200), "white")
    draw = ImageDraw.Draw(image)
    draw.text((20, 80), "HELLO WORLD", fill="black")
    image.save(path)
    return path


@pytest.mark.skipif(
    not _OCR_AVAILABLE,
    reason="tesseract/qpdf/ghostscript oder Sprachpaket nicht installiert",
)
def test_apply_ocr_adds_searchable_text(tmp_path):
    from pypdf import PdfReader

    doc = Document(document_type=DocumentType.PDF)
    doc.add_page(_make_text_image(tmp_path / "a.png"))
    out_path = save_document(doc, tmp_path / "out.pdf")

    save_and_process(
        doc, out_path, ocr_enabled=True, ocr_languages=["Englisch"]
    )

    reader = PdfReader(str(out_path))
    text = reader.pages[0].extract_text() or ""
    assert "HELLO" in text.upper() or "WORLD" in text.upper()
