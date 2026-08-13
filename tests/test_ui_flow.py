"""End-to-End-Test des UI-Kernflows (Scan -> Seite hinzufügen -> rotieren -> neuordnen ->
löschen -> Dateityp-Wechsel) gegen ein Fake-Scanner-Backend, ohne echte Hardware/Anzeige.
"""

import os
import time
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PIL import Image
from pypdf import PdfReader
from PySide6.QtWidgets import QApplication

from scanner_app.backend.base import ScannerBackend, ScannerDevice, ScanOptions
from scanner_app.models.document import DocumentType
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


def _wait_for_scan(window, timeout_ms: int = 3000) -> None:
    """Scannen läuft seit der QThread-Umstellung (Issue #7) im Hintergrund — Tests müssen
    die Event-Loop pumpen, bis der Worker-Thread sein QueuedConnection-Signal zugestellt hat,
    statt sich (wie vor der Umstellung) auf einen synchron abgeschlossenen Aufruf zu verlassen.
    """
    app = QApplication.instance()
    elapsed = 0
    step_ms = 10
    while window._scan_thread is not None and elapsed < timeout_ms:
        app.processEvents()
        time.sleep(step_ms / 1000)
        elapsed += step_ms
    assert window._scan_thread is None, "Scan im Hintergrund-Thread nicht rechtzeitig beendet"


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


def _scan(window) -> None:
    window._on_scan_requested()
    _wait_for_scan(window)


def _scan_and_restart(window) -> None:
    window._on_scan_and_restart_requested()
    _wait_for_scan(window)


def test_scan_creates_new_pdf(window):
    _scan(window)
    assert len(window.document.pages) == 1
    assert window.document.output_path.exists()


def test_scan_shows_and_clears_scanning_state(window):
    window._on_scan_requested()
    # Direkt nach dem Auslösen (vor dem ersten processEvents()) muss der gesperrte Zustand
    # bereits sichtbar sein — er wird synchron im UI-Thread gesetzt, bevor der Hintergrund-
    # Thread überhaupt startet.
    assert window.settings_panel._scan_stack.currentIndex() == 1
    assert not window.settings_panel._device_combo.isEnabled()
    _wait_for_scan(window)
    assert window.settings_panel._scan_stack.currentIndex() == 0
    assert window.settings_panel._device_combo.isEnabled()


def test_cancel_scan_discards_result(window):
    window._on_scan_requested()
    window._cancel_scan()
    assert window.settings_panel._scan_stack.currentIndex() == 0
    _wait_for_scan(window)
    assert window.document.pages == []


def test_scan_recovers_ui_after_unexpected_backend_exception(window):
    # Regression: _ScanWorker.run() fing früher nur ScannerBackendError ab — jede andere
    # Exception (z.B. eine rohe COM-Exception aus dem WIA-Backend) ließ weder finished noch
    # failed emittieren, der QThread lief für immer weiter und die UI blieb dauerhaft im
    # "Scan läuft…"-Zustand hängen. Jetzt muss auch ein unerwarteter Fehlertyp die UI
    # zuverlässig wieder freigeben.
    def raise_unexpected(_device, _options, _output_path):
        raise RuntimeError("unerwarteter Treiberfehler")

    window.backend.scan_page = raise_unexpected
    with patch("scanner_app.ui.main_window.QMessageBox"):
        window._on_scan_requested()
        _wait_for_scan(window)
    assert window.settings_panel._scan_stack.currentIndex() == 0
    assert window.settings_panel._device_combo.isEnabled()
    assert window.document.pages == []


def test_scan_default_mode_append_adds_to_existing_document(window):
    window.settings.scan_default_mode = "append"
    _scan(window)
    assert len(window.document.pages) == 1
    _scan(window)
    assert len(window.document.pages) == 2
    reader = PdfReader(str(window.document.output_path))
    assert len(reader.pages) == 2


def test_scan_default_mode_new_starts_fresh_document(window):
    window.settings.scan_default_mode = "new"
    _scan(window)
    first_output = window.document.output_path
    assert len(window.document.pages) == 1

    _scan(window)
    assert len(window.document.pages) == 1
    assert window.document.output_path != first_output
    assert first_output.exists()


def test_scan_and_restart_always_starts_fresh_document(window):
    window.settings.scan_default_mode = "append"
    _scan(window)
    first_output = window.document.output_path
    assert len(window.document.pages) == 1

    _scan_and_restart(window)
    assert len(window.document.pages) == 1
    assert window.document.output_path != first_output
    assert first_output.exists()  # vorheriges Dokument bleibt unangetastet auf der Platte


def test_delete_page_updates_pdf(window):
    window.settings.scan_default_mode = "append"
    _scan(window)
    _scan(window)
    out_path = window.document.output_path
    to_delete = window.document.pages[0].id
    window._on_delete_page(to_delete)
    assert len(window.document.pages) == 1
    reader = PdfReader(str(out_path))
    assert len(reader.pages) == 1


def test_reorder_pages(window):
    window.settings.scan_default_mode = "append"
    _scan(window)
    _scan(window)
    _scan(window)
    ids = [p.id for p in window.document.pages]
    window._on_pages_reordered(list(reversed(ids)))
    assert [p.id for p in window.document.pages] == list(reversed(ids))


def test_rotate_page(window):
    _scan(window)
    page_id = window.document.pages[0].id
    window._on_rotate_page(page_id, 90)
    assert window.document.pages[0].rotation == 90


def test_image_filetype_always_starts_fresh_document(window):
    window.settings.scan_default_mode = "append"
    window.settings_panel._filetype_combo.setCurrentText("PNG")

    _scan(window)
    assert window.document.output_path.suffix == ".png"
    assert window.document.document_type is DocumentType.PNG
    first_output = window.document.output_path

    _scan(window)
    assert len(window.document.pages) == 1  # keine zweite Seite angehängt
    assert window.document.output_path != first_output


def test_auto_rotate_disabled_by_default_leaves_page_unrotated(window):
    with patch("scanner_app.ui.main_window.detect_rotation", return_value=180) as mock_detect:
        _scan(window)
    mock_detect.assert_not_called()
    assert window.document.pages[0].rotation == 0


def test_auto_rotate_enabled_applies_detected_rotation(window):
    window.settings.auto_rotate_enabled = True
    with patch("scanner_app.ui.main_window.detect_rotation", return_value=180):
        _scan(window)
    assert window.document.pages[0].rotation == 180


def test_auto_rotate_skips_page_rotation_when_no_rotation_detected(window):
    window.settings.auto_rotate_enabled = True
    with patch("scanner_app.ui.main_window.detect_rotation", return_value=0):
        _scan(window)
    assert window.document.pages[0].rotation == 0


def test_ocr_toggle_disabled_when_dependencies_missing(window):
    with patch("scanner_app.ui.settings_page.missing_dependencies", return_value=["tesseract"]):
        page = SettingsPage(window.settings)
    try:
        assert not page._ocr_toggle.isEnabled()
        assert "tesseract" in page._ocr_dependency_hint.text()
    finally:
        page.close()


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

    window._icon_rail.settingsRequested.emit()
    assert window._stack.currentWidget() is window.settings_page

    window.settings_page.backRequested.emit()
    assert window._stack.currentWidget() is not window.settings_page


def test_rail_scan_icon_returns_to_scanner_page_from_settings(window):
    window._icon_rail.settingsRequested.emit()
    assert window._stack.currentWidget() is window.settings_page

    window._icon_rail.scanRequested.emit()
    assert window._stack.currentWidget() is not window.settings_page
    _wait_for_scan(window)


def test_check_for_updates_click_shows_searching_state(window):
    # check_for_update gemockt, damit der Test nicht auf einen echten Netzwerkaufruf wartet.
    page = SettingsPage(window.settings)
    try:
        with patch("scanner_app.ui.settings_page.check_for_update", return_value=None):
            assert page._check_update_button.isEnabled()
            page._on_check_updates_clicked()
            assert not page._check_update_button.isEnabled()
            assert "Suche nach Updates" in page._update_status_label.text()
    finally:
        # Wartet aktiv auf den Hintergrund-Thread, bevor die Seite zerstört wird — Qt darf
        # nie einen QThread zerstören, während sein Worker noch läuft (harter Absturz statt
        # nur einer Warnung, siehe CLAUDE.md).
        page.shutdown()
        page.close()


def test_check_for_updates_completes_and_reenables_button(window):
    # Regression: die vorige Version dieses Tests prüfte nur den "Suche…"-Zwischenzustand,
    # nie die tatsächliche Fertigstellung — dabei ist genau das der Zustand, der laut
    # Nutzer-Feedback in echten Läufen dauerhaft hängen blieb.
    page = SettingsPage(window.settings)
    try:
        with patch("scanner_app.ui.settings_page.check_for_update", return_value=None):
            page._on_check_updates_clicked()
            app = QApplication.instance()
            elapsed = 0
            while not page._check_update_button.isEnabled() and elapsed < 3000:
                app.processEvents()
                time.sleep(0.01)
                elapsed += 10
        assert page._check_update_button.isEnabled()
        assert "aktuell" in page._update_status_label.text()
    finally:
        page.shutdown()
        page.close()


def test_check_for_updates_recovers_after_unexpected_exception(window):
    # Regression: _UpdateCheckWorker.run() emittierte früher gar kein Signal, wenn
    # check_for_update() (entgegen seines eigenen Vertrags) doch einmal geworfen hätte —
    # der QThread lief dann für immer weiter und "Suche nach Updates…" blieb stehen.
    page = SettingsPage(window.settings)
    try:
        with patch("scanner_app.ui.settings_page.check_for_update", side_effect=RuntimeError("kaputt")):
            page._on_check_updates_clicked()
            app = QApplication.instance()
            elapsed = 0
            while not page._check_update_button.isEnabled() and elapsed < 3000:
                app.processEvents()
                time.sleep(0.01)
                elapsed += 10
        assert page._check_update_button.isEnabled()
    finally:
        page.shutdown()
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


def test_update_dialog_has_no_install_button_when_not_windows_installed_build(window):
    # Läuft unter Linux/CI — is_installed_windows_build() ist dort immer False, der
    # Dialog darf also nie eine automatische Installationsoption anbieten.
    from scanner_app.update_checker import UpdateInfo

    info = UpdateInfo(
        version="9.9.9",
        html_url="https://example.invalid/x",
        notes="",
        windows_installer_url="https://example.invalid/setup.exe",
        windows_installer_checksum_url="https://example.invalid/setup.exe.sha256",
    )
    with patch("scanner_app.ui.main_window.QMessageBox") as mock_box_cls:
        mock_box = mock_box_cls.return_value
        mock_box.clickedButton.return_value = None
        window._on_update_available(info)
    # Nur zwei Buttons ("Release-Seite öffnen", "Später") — kein "Jetzt installieren".
    assert mock_box.addButton.call_count == 2


def test_auto_update_downloads_and_launches_installer(window):
    from scanner_app.update_checker import UpdateInfo

    info = UpdateInfo(
        version="9.9.9",
        html_url="https://example.invalid/x",
        notes="",
        windows_installer_url="https://example.invalid/setup.exe",
        windows_installer_checksum_url="https://example.invalid/setup.exe.sha256",
    )
    fake_installer = window._scan_tmp_dir / "fake-setup.exe"
    fake_installer.write_bytes(b"x")

    with (
        patch("scanner_app.ui.main_window.windows_updater.fetch_checksum", return_value="abc"),
        patch("scanner_app.ui.main_window.windows_updater.download_installer", return_value=fake_installer),
        patch("scanner_app.ui.main_window.windows_updater.launch_silent_install") as mock_launch,
    ):
        window._start_auto_update(info)
        app = QApplication.instance()
        elapsed = 0
        while window._update_thread is not None and elapsed < 3000:
            app.processEvents()
            time.sleep(0.01)
            elapsed += 10

    mock_launch.assert_called_once_with(fake_installer)


def test_auto_update_shows_warning_on_failure(window):
    from scanner_app.update_checker import UpdateInfo

    info = UpdateInfo(
        version="9.9.9",
        html_url="https://example.invalid/x",
        notes="",
        windows_installer_url="https://example.invalid/setup.exe",
        windows_installer_checksum_url="https://example.invalid/setup.exe.sha256",
    )
    from scanner_app.windows_updater import UpdateInstallError

    with (
        patch("scanner_app.ui.main_window.windows_updater.fetch_checksum", side_effect=UpdateInstallError("kaputt")),
        patch("scanner_app.ui.main_window.QMessageBox") as mock_box_cls,
    ):
        window._start_auto_update(info)
        app = QApplication.instance()
        elapsed = 0
        while window._update_thread is not None and elapsed < 3000:
            app.processEvents()
            time.sleep(0.01)
            elapsed += 10

    mock_box_cls.warning.assert_called_once()
