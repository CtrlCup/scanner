from unittest.mock import patch

from scanner_app.ocr.language_manager import _BUNDLED_TESSERACT_CONFIGS, tessdata_dir


def test_tessdata_dir_bundles_tesseract_output_configs(tmp_path):
    # Regression: ein isolierter TESSDATA_PREFIX ohne configs/{hocr,pdf,txt} lässt echtes
    # Tesseract mit "Can't open hocr" (TesseractConfigError) abbrechen — dieser Bug war
    # monatelang latent, weil der zugehörige Test übersprungen wurde, bis Sprachpakete
    # automatisch beim Start heruntergeladen wurden (siehe MainWindow).
    with patch("scanner_app.ocr.language_manager.user_data_dir", return_value=str(tmp_path)):
        path = tessdata_dir()

    configs_dir = path / "configs"
    for name in _BUNDLED_TESSERACT_CONFIGS:
        assert (configs_dir / name).exists(), f"Config-Datei {name} fehlt"
        assert (configs_dir / name).read_text().strip()


def test_tessdata_dir_does_not_overwrite_existing_configs(tmp_path):
    with patch("scanner_app.ocr.language_manager.user_data_dir", return_value=str(tmp_path)):
        path = tessdata_dir()
        (path / "configs" / "hocr").write_text("angepasst")
        tessdata_dir()  # zweiter Aufruf darf eine bereits vorhandene Datei nicht überschreiben

    assert (path / "configs" / "hocr").read_text() == "angepasst"
