"""End-to-End-Test des UI-Kernflows (Scan -> Seite hinzufügen -> rotieren -> neuordnen ->
löschen -> Dateityp-Wechsel) gegen ein Fake-Scanner-Backend, ohne echte Hardware/Anzeige.
"""

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PIL import Image
from pypdf import PdfReader
from PySide6.QtWidgets import QApplication

from scanner_app.backend.base import ScannerDevice
from scanner_app.ui.main_window import MainWindow


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app, tmp_path):
    # Nach der Konstruktion auf eine isolierte, dateibasierte QSettings-Instanz umstellen,
    # damit Tests keine echte lokale App-Installation lesen/verändern.
    from PySide6.QtCore import QSettings

    win = MainWindow()
    win.settings._settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    win.settings.save_directory = tmp_path / "scans"

    win.settings_panel._devices = [ScannerDevice(device_id="fake0", display_name="Test-Scanner")]
    win.settings_panel._device_combo.clear()
    win.settings_panel._device_combo.addItem("Test-Scanner", userData="fake0")
    win.settings_panel._device_combo.setEnabled(True)

    counter = {"n": 0}

    def fake_scan_page(_device, _options, output_path):
        counter["n"] += 1
        Image.new("RGB", (200, 100), "white").save(output_path)
        return Path(output_path)

    win.backend.scan_page = fake_scan_page
    yield win
    win.close()


def test_scan_creates_new_pdf(window):
    window._on_scan_requested()
    assert len(window.document.pages) == 1
    assert window.document.output_path.exists()


def test_add_page_appends_to_pdf(window):
    window._on_scan_requested()
    assert window.settings_panel._add_page_button.isEnabled()
    window._on_add_page_requested()
    assert len(window.document.pages) == 2
    reader = PdfReader(str(window.document.output_path))
    assert len(reader.pages) == 2


def test_delete_page_updates_pdf(window):
    window._on_scan_requested()
    window._on_add_page_requested()
    out_path = window.document.output_path
    to_delete = window.document.pages[0].id
    window._on_delete_page(to_delete)
    assert len(window.document.pages) == 1
    reader = PdfReader(str(out_path))
    assert len(reader.pages) == 1


def test_reorder_pages(window):
    window._on_scan_requested()
    window._on_add_page_requested()
    window._on_add_page_requested()
    ids = [p.id for p in window.document.pages]
    window._on_pages_reordered(list(reversed(ids)))
    assert [p.id for p in window.document.pages] == list(reversed(ids))


def test_rotate_page(window):
    window._on_scan_requested()
    page_id = window.document.pages[0].id
    window._on_rotate_page(page_id, 90)
    assert window.document.pages[0].rotation == 90


def test_add_page_disabled_for_image_filetype(window):
    window.settings_panel._filetype_combo.setCurrentText("Bild")
    window._update_add_page_enabled()
    assert not window.settings_panel._add_page_button.isEnabled()

    window._on_scan_requested()
    assert window.document.output_path.suffix == ".png"
    assert not window.settings_panel._add_page_button.isEnabled()


def test_new_scan_always_starts_fresh_document(window):
    window._on_scan_requested()
    window._on_add_page_requested()
    first_output = window.document.output_path
    assert len(window.document.pages) == 2

    window._on_scan_requested()
    assert len(window.document.pages) == 1
    assert window.document.output_path != first_output
    assert first_output.exists()  # vorheriges Dokument bleibt unangetastet auf der Platte
