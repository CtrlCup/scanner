from PySide6.QtCore import QSettings

from scanner_app.app_settings import AppSettings


def _isolated_settings(tmp_path) -> AppSettings:
    settings = AppSettings()
    settings._settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    return settings


def test_auto_rotate_defaults_to_disabled(tmp_path):
    settings = _isolated_settings(tmp_path)
    assert settings.auto_rotate_enabled is False


def test_auto_rotate_roundtrip(tmp_path):
    settings = _isolated_settings(tmp_path)
    settings.auto_rotate_enabled = True
    assert settings.auto_rotate_enabled is True


def test_handwriting_defaults_to_disabled(tmp_path):
    settings = _isolated_settings(tmp_path)
    assert settings.handwriting_enabled is False


def test_handwriting_roundtrip(tmp_path):
    settings = _isolated_settings(tmp_path)
    settings.handwriting_enabled = True
    assert settings.handwriting_enabled is True
