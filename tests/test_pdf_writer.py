from PIL import Image
from pypdf import PdfReader

from scanner_app.models.document import Document, DocumentType
from scanner_app.pdf.pdf_writer import save_document


def _make_image(path, size=(40, 20), color="white"):
    Image.new("RGB", size, color).save(path)
    return path


def test_save_document_writes_multi_page_pdf(tmp_path):
    doc = Document(document_type=DocumentType.PDF)
    doc.add_page(_make_image(tmp_path / "a.png"))
    doc.add_page(_make_image(tmp_path / "b.png"))
    doc.add_page(_make_image(tmp_path / "c.png"))

    out = save_document(doc, tmp_path / "out.pdf")

    reader = PdfReader(str(out))
    assert len(reader.pages) == 3


def test_save_document_updates_pdf_after_delete(tmp_path):
    doc = Document(document_type=DocumentType.PDF)
    p1 = doc.add_page(_make_image(tmp_path / "a.png"))
    doc.add_page(_make_image(tmp_path / "b.png"))
    out_path = tmp_path / "out.pdf"
    save_document(doc, out_path)

    doc.remove_page(p1.id)
    save_document(doc, out_path)

    reader = PdfReader(str(out_path))
    assert len(reader.pages) == 1


def test_rotation_changes_page_dimensions(tmp_path):
    doc = Document(document_type=DocumentType.PDF)
    page = doc.add_page(_make_image(tmp_path / "a.png", size=(40, 20)))
    doc.rotate_page(page.id, 90)
    out = save_document(doc, tmp_path / "out.pdf")

    reader = PdfReader(str(out))
    box = reader.pages[0].mediabox
    # a 40x20 image rotated 90° should yield a taller-than-wide page
    assert box.height > box.width


def test_save_document_writes_image(tmp_path):
    doc = Document(document_type=DocumentType.IMAGE)
    doc.add_page(_make_image(tmp_path / "a.png"))
    out = save_document(doc, tmp_path / "out.png")

    assert out.exists()
    with Image.open(out) as img:
        assert img.size == (40, 20)
