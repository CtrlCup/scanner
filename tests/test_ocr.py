import os
import shutil
from unittest.mock import patch

import pytest
from PIL import Image, ImageDraw

from scanner_app.models.document import Document, DocumentType
from scanner_app.ocr import ocr_engine
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


@pytest.fixture
def restore_path():
    original = os.environ.get("PATH", "")
    yield
    os.environ["PATH"] = original


def test_ensure_bundled_tools_adds_flat_linux_layout_to_path(tmp_path, restore_path):
    # Linux (build_linux.sh): alle Programme+Shared-Libs liegen flach in einem Ordner.
    bundle_root = tmp_path / "bundle"
    ocr_tools = bundle_root / "ocr-tools"
    ocr_tools.mkdir(parents=True)
    (ocr_tools / "tesseract").touch()

    with patch("scanner_app.ocr.ocr_engine.frozen_bundle_dir", return_value=bundle_root):
        ocr_engine._ensure_bundled_tools_available()

    assert str(ocr_tools) in os.environ["PATH"].split(os.pathsep)


def test_ensure_bundled_tools_adds_windows_subfolder_layout_to_path(tmp_path, restore_path):
    # Windows (package.yml): jedes Werkzeug bekommt seinen eigenen Unterordner, da Windows-
    # Programme ihre DLLs üblicherweise im eigenen Installationsordner erwarten.
    bundle_root = tmp_path / "bundle"
    ocr_tools = bundle_root / "ocr-tools"
    (ocr_tools / "tesseract").mkdir(parents=True)
    (ocr_tools / "qpdf").mkdir(parents=True)
    gs_dir = ocr_tools / "ghostscript"
    (gs_dir / "Resource").mkdir(parents=True)

    with patch("scanner_app.ocr.ocr_engine.frozen_bundle_dir", return_value=bundle_root):
        ocr_engine._ensure_bundled_tools_available()

    path_entries = os.environ["PATH"].split(os.pathsep)
    assert str(ocr_tools / "tesseract") in path_entries
    assert str(ocr_tools / "qpdf") in path_entries
    assert str(ocr_tools / "ghostscript") in path_entries
    assert os.environ["GS_LIB"] == str(gs_dir / "Resource")


def test_ensure_bundled_tools_is_noop_without_frozen_bundle(restore_path):
    with patch("scanner_app.ocr.ocr_engine.frozen_bundle_dir", return_value=None):
        before = os.environ.get("PATH", "")
        ocr_engine._ensure_bundled_tools_available()
        assert os.environ.get("PATH", "") == before
