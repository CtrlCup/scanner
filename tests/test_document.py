import pytest

from scanner_app.models.document import Document, DocumentType


def _doc() -> Document:
    return Document(document_type=DocumentType.PDF)


def test_new_document_is_empty():
    doc = _doc()
    assert doc.is_empty
    assert not doc.can_add_page


def test_add_page_enables_add_page_for_pdf(tmp_path):
    doc = _doc()
    doc.add_page(tmp_path / "a.png")
    assert not doc.is_empty
    assert doc.can_add_page


def test_image_document_never_allows_add_page(tmp_path):
    doc = Document(document_type=DocumentType.IMAGE)
    doc.add_page(tmp_path / "a.png")
    assert not doc.can_add_page


def test_image_document_rejects_second_page(tmp_path):
    doc = Document(document_type=DocumentType.IMAGE)
    doc.add_page(tmp_path / "a.png")
    with pytest.raises(ValueError):
        doc.add_page(tmp_path / "b.png")


def test_remove_page(tmp_path):
    doc = _doc()
    p1 = doc.add_page(tmp_path / "a.png")
    doc.add_page(tmp_path / "b.png")
    doc.remove_page(p1.id)
    assert len(doc.pages) == 1
    assert doc.pages[0].image_path.name == "b.png"


def test_move_page_reorders(tmp_path):
    doc = _doc()
    doc.add_page(tmp_path / "a.png")
    doc.add_page(tmp_path / "b.png")
    p3 = doc.add_page(tmp_path / "c.png")
    doc.move_page(p3.id, 0)
    assert [p.image_path.name for p in doc.pages] == ["c.png", "a.png", "b.png"]


def test_rotate_page_wraps_at_360(tmp_path):
    doc = _doc()
    page = doc.add_page(tmp_path / "a.png")
    doc.rotate_page(page.id, 90)
    doc.rotate_page(page.id, 90)
    doc.rotate_page(page.id, 90)
    doc.rotate_page(page.id, 90)
    assert page.rotation == 0
