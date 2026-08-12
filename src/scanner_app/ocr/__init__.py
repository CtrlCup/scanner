from scanner_app.ocr.language_manager import (
    AVAILABLE_LANGUAGES,
    DEFAULT_LANGUAGES,
    download_language,
    ensure_default_languages_installed,
    installed_languages,
    is_language_installed,
    tessdata_dir,
)
from scanner_app.ocr.ocr_engine import OcrError, apply_ocr
from scanner_app.ocr.orientation import detect_rotation, ensure_osd_installed, is_osd_installed

__all__ = [
    "AVAILABLE_LANGUAGES",
    "DEFAULT_LANGUAGES",
    "OcrError",
    "apply_ocr",
    "detect_rotation",
    "download_language",
    "ensure_default_languages_installed",
    "ensure_osd_installed",
    "installed_languages",
    "is_language_installed",
    "is_osd_installed",
    "tessdata_dir",
]
