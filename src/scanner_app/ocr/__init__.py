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

__all__ = [
    "AVAILABLE_LANGUAGES",
    "DEFAULT_LANGUAGES",
    "OcrError",
    "apply_ocr",
    "download_language",
    "ensure_default_languages_installed",
    "installed_languages",
    "is_language_installed",
    "tessdata_dir",
]
