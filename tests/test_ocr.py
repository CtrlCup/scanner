import shutil
from unittest.mock import patch

import pytest
from PIL import Image, ImageDraw

from scanner_app.models.document import Document, DocumentType
from scanner_app.ocr.language_manager import is_language_installed
from scanner_app.ocr.ocr_engine import OcrError, apply_ocr, dependency_hint, missing_dependencies
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


def test_missing_dependencies_empty_when_all_tools_present():
    with patch("scanner_app.ocr.ocr_engine.shutil.which", return_value="/usr/bin/tool"):
        assert missing_dependencies() == []


def test_missing_dependencies_lists_absent_tools():
    with patch("scanner_app.ocr.ocr_engine.shutil.which", return_value=None):
        missing = missing_dependencies()
    assert set(missing) == {"tesseract", "qpdf", "ghostscript"}


def test_dependency_hint_names_each_missing_tool_with_install_link():
    hint = dependency_hint(["tesseract", "qpdf"])
    assert "tesseract" in hint
    assert "qpdf" in hint
    assert "https://" in hint


def test_apply_ocr_raises_specific_error_when_dependency_missing(tmp_path):
    doc = Document(document_type=DocumentType.PDF)
    doc.add_page(_make_text_image(tmp_path / "a.png"))
    out_path = save_document(doc, tmp_path / "out.pdf")

    with (
        patch("scanner_app.ocr.ocr_engine.missing_dependencies", return_value=["tesseract"]),
        pytest.raises(OcrError, match="tesseract"),
    ):
        apply_ocr(out_path)
