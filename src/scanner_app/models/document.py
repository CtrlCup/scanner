from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path


class DocumentType(Enum):
    PDF = "pdf"
    IMAGE = "image"


@dataclass
class Page:
    """A single scanned page: the raw scanned image plus its display rotation.

    `image_path` always points at the untouched scan output — rotation is applied
    on export, never destructively, so re-scanning a page or undoing a rotation
    never needs to re-touch the source file.
    """

    image_path: Path
    rotation: int = 0
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def rotate(self, degrees: int = 90) -> None:
        self.rotation = (self.rotation + degrees) % 360


@dataclass
class Document:
    """A scan session in progress: an ordered list of pages plus where it's saved.

    For DocumentType.IMAGE there is always at most one page — a fresh scan starts
    a new Document/image rather than appending, since a single image file can't
    hold multiple pages.
    """

    document_type: DocumentType = DocumentType.PDF
    pages: list[Page] = field(default_factory=list)
    output_path: Path | None = None

    @property
    def is_empty(self) -> bool:
        return not self.pages

    @property
    def can_add_page(self) -> bool:
        """Whether the '+' (add page) action is allowed for the current state."""
        if self.document_type is not DocumentType.PDF:
            return False
        return not self.is_empty

    def add_page(self, image_path: Path) -> Page:
        if self.document_type is DocumentType.IMAGE and self.pages:
            raise ValueError("Ein Bild-Dokument kann nur eine Seite enthalten.")
        page = Page(image_path=Path(image_path))
        self.pages.append(page)
        return page

    def remove_page(self, page_id: str) -> None:
        self.pages = [p for p in self.pages if p.id != page_id]

    def move_page(self, page_id: str, new_index: int) -> None:
        current_index = next(i for i, p in enumerate(self.pages) if p.id == page_id)
        page = self.pages.pop(current_index)
        new_index = max(0, min(new_index, len(self.pages)))
        self.pages.insert(new_index, page)

    def rotate_page(self, page_id: str, degrees: int = 90) -> None:
        for page in self.pages:
            if page.id == page_id:
                page.rotate(degrees)
                return
        raise KeyError(page_id)

    def get_page(self, page_id: str) -> Page:
        for page in self.pages:
            if page.id == page_id:
                return page
        raise KeyError(page_id)


def generate_filename(
    document_type: DocumentType,
    *,
    when: datetime | None = None,
    pattern: str = "Scan_{Datum}_{Nummer}",
    sequence: int = 1,
) -> str:
    """Dateiname aus einem Muster mit den Platzhaltern ``{Datum}`` (Zeitstempel bis auf die
    Sekunde) und ``{Nummer}`` (laufende, 3-stellig gepolsterte Nummer innerhalb desselben
    Speicherordners — vom Aufrufer über `sequence` übergeben, da diese Funktion selbst
    nichts vom Dateisystem weiß). Enthält das Muster keinen der beiden Platzhalter, bleibt
    der Name für jeden Scan gleich — Kollisionen löst der Aufrufer (siehe
    `MainWindow._make_unique_path`).
    """
    when = when or datetime.now()  # noqa: DTZ005 - bewusst lokale Wanduhrzeit für Dateinamen
    stamp = when.strftime("%Y-%m-%d_%H-%M-%S")
    extension = "pdf" if document_type is DocumentType.PDF else "png"
    stem = pattern.format(Datum=stamp, Nummer=f"{sequence:03d}")
    return f"{stem}.{extension}"
