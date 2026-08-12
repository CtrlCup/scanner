"""End-to-End-Test des UI-Kernflows (Scan -> Seite hinzufügen -> rotieren -> neuordnen ->
löschen -> Dateityp-Wechsel) gegen ein Fake-Scanner-Backend, ohne echte Hardware/Anzeige.
"""

import os
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PIL import Image
from pypdf import PdfReader
from PySide6.QtWidgets import QApplication

from scanner_app.backend.base import ScannerBackend, ScannerDevice, ScanOptions
from scanner_app.ui.main_window import MainWindow
from scanner_app.ui.settings_page import SettingsPage


class _FakeScannerBackend(ScannerBackend):
    """Backend-Doppel für Tests — vermeidet jeden Kontakt mit echtem SANE/python-sane.

    Wiederholte sane.init()/sane.exit()-Zyklen (ein Zyklus pro MainWindow-Konstruktion,
    also einer pro Test) haben sich als scharfer nativer Absturz im installierten
    libsane-epson2-Backend erwiesen (Segfault bei der Netzwerk-Geräteerkennung) — von
    Python aus mit try/except nicht abfangbar. Tests dürfen echte Scanner-Treiber daher
    grundsätzlich nie berühren, nicht nur aus Geschwindigkeits-, sondern aus
    Stabilitätsgründen.
    """

    def __init__(self, devices: list[ScannerDevice]) -> None:
        self._devices = devices

    def list_devices(self) -> list[ScannerDevice]:
        return self._devices

    def scan_page(self, device: ScannerDevice, options: ScanOptions, output_path: Path) -> Path:
        Image.new("RGB", (200, 100), "white").save(output_path)
        return Path(output_path)


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app, tmp_path):
    # Nach der Konstruktion auf eine isolierte, dateibasierte QSettings-Instanz umstellen,
    # damit Tests keine echte lokale App-Installation lesen/verändern.
    from PySide6.QtCore import QSettings

    fake_devices = [ScannerDevice(device_id="fake0", display_name="Test-Scanner")]
    with patch("scanner_app.ui.main_window.get_backend", return_value=_FakeScannerBackend(fake_devices)):
        win = MainWindow()

    win.settings._settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    win.settings.save_directory = tmp_path / "scans"
    # Verhindert den echten Netzwerkaufruf, den der verzögerte Start-Update-Check sonst
    # ~1,5s nach jeder Fenster-Konstruktion auslösen würde.
    win.settings.auto_update_check_enabled = False

    win.settings_panel._devices = fake_devices
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


def test_auto_rotate_disabled_by_default_leaves_page_unrotated(window):
    with patch("scanner_app.ui.main_window.detect_rotation", return_value=180) as mock_detect:
        window._on_scan_requested()
    mock_detect.assert_not_called()
    assert window.document.pages[0].rotation == 0


def test_auto_rotate_enabled_applies_detected_rotation(window):
    window.settings.auto_rotate_enabled = True
    with patch("scanner_app.ui.main_window.detect_rotation", return_value=180):
        window._on_scan_requested()
    assert window.document.pages[0].rotation == 180


def test_auto_rotate_skips_page_rotation_when_no_rotation_detected(window):
    window.settings.auto_rotate_enabled = True
    with patch("scanner_app.ui.main_window.detect_rotation", return_value=0):
        window._on_scan_requested()
    assert window.document.pages[0].rotation == 0


def test_handwriting_toggle_only_visible_when_ocr_enabled(window):
    page = SettingsPage(window.settings)
    page.show()
    try:
        assert page._ocr_toggle.isChecked() is False
        assert not page._language_section.isVisible()

        page._ocr_toggle.setChecked(True)
        assert page._language_section.isVisible()
        assert page._handwriting_toggle.isVisible()

        page._ocr_toggle.setChecked(False)
        assert not page._language_section.isVisible()
    finally:
        page.close()


def test_handwriting_setting_persisted_from_page(window):
    page = SettingsPage(window.settings)
    page._handwriting_toggle.setChecked(True)
    assert window.settings.handwriting_enabled is True
    page.close()


def test_gear_icon_navigates_to_settings_page_and_back(window):
    assert window._stack.currentWidget() is not window.settings_page

    window.settings_panel.openSettingsRequested.emit()
    assert window._stack.currentWidget() is window.settings_page

    window.settings_page.backRequested.emit()
    assert window._stack.currentWidget() is not window.settings_page


def test_check_for_updates_click_shows_searching_state(window, app):
    # check_for_update gemockt, damit der Test nicht auf einen echten Netzwerkaufruf wartet.
    page = SettingsPage(window.settings)
    try:
        with patch("scanner_app.ui.settings_page.check_for_update", return_value=None):
            assert page._check_update_button.isEnabled()
            page._on_check_updates_clicked()
            assert not page._check_update_button.isEnabled()
            assert "Suche nach Updates" in page._update_status_label.text()

            for thread in list(page._threads):
                thread.wait(2000)
            app.processEvents()
    finally:
        page.close()


def test_update_checked_with_result_shows_download_button_and_emits_signal(window):
    from scanner_app.update_checker import UpdateInfo

    page = SettingsPage(window.settings)
    page.show()
    try:
        info = UpdateInfo(version="9.9.9", html_url="https://example.invalid/x", notes="")
        received = []
        page.updateAvailable.connect(received.append)

        page._on_update_checked(info)

        assert page._pending_update is info
        assert page._download_update_button.isVisible()
        assert "9.9.9" in page._update_status_label.text()
        assert received == [info]
    finally:
        page.close()


def test_update_checked_with_no_result_hides_download_button(window):
    page = SettingsPage(window.settings)
    try:
        page._download_update_button.setVisible(True)
        page._on_update_checked(None)
        assert not page._download_update_button.isVisible()
        assert "aktuell" in page._update_status_label.text()
    finally:
        page.close()


def test_auto_update_toggle_persists_setting(window):
    page = SettingsPage(window.settings)
    try:
        page._auto_update_toggle.setChecked(False)
        assert window.settings.auto_update_check_enabled is False
    finally:
        page.close()


def test_main_window_shows_dialog_when_update_available(window):
    from scanner_app.update_checker import UpdateInfo

    info = UpdateInfo(version="9.9.9", html_url="https://example.invalid/x", notes="Testnotiz")
    with patch("scanner_app.ui.main_window.QMessageBox") as mock_box_cls:
        mock_box = mock_box_cls.return_value
        mock_box.clickedButton.return_value = None
        window._on_update_available(info)
    mock_box.exec.assert_called_once()
