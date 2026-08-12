import shutil
import subprocess
from unittest.mock import patch

import pytest

from scanner_app.ocr.orientation import detect_rotation, is_osd_installed


def _fake_run(stdout: str):
    def _run(*_args, **_kwargs):
        return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")

    return _run


def test_detect_rotation_parses_osd_output(tmp_path):
    osd_output = (
        "Page number: 0\n"
        "Orientation in degrees: 90\n"
        "Rotate: 270\n"
        "Orientation confidence: 6.66\n"
    )
    with patch("scanner_app.ocr.orientation.subprocess.run", _fake_run(osd_output)):
        assert detect_rotation(tmp_path / "a.png") == 270


def test_detect_rotation_returns_zero_when_no_rotate_line(tmp_path):
    with patch("scanner_app.ocr.orientation.subprocess.run", _fake_run("Page number: 0\n")):
        assert detect_rotation(tmp_path / "a.png") == 0


def test_detect_rotation_returns_zero_on_failure(tmp_path):
    def _raise(*_args, **_kwargs):
        raise FileNotFoundError("tesseract not found")

    with patch("scanner_app.ocr.orientation.subprocess.run", _raise):
        assert detect_rotation(tmp_path / "a.png") == 0


@pytest.mark.skipif(
    shutil.which("tesseract") is None or not is_osd_installed(),
    reason="tesseract oder osd.traineddata nicht installiert",
)
def test_detect_rotation_against_real_tesseract_returns_int(tmp_path):
    from PIL import Image

    image_path = tmp_path / "blank.png"
    Image.new("RGB", (100, 100), "white").save(image_path)
    # Ein leeres Bild liefert keine verlässliche Erkennung -> best-effort 0, kein Crash.
    assert detect_rotation(image_path) == 0
