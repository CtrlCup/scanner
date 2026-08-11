from __future__ import annotations

import shutil
import urllib.request
from pathlib import Path

from platformdirs import user_data_dir

_TESSDATA_BASE_URL = "https://github.com/tesseract-ocr/tessdata_fast/raw/main"

# UI-Anzeigename -> Tesseract-Sprachcode (ISO 639-2/T)
AVAILABLE_LANGUAGES: dict[str, str] = {
    "Deutsch": "deu",
    "Englisch": "eng",
    "Französisch": "fra",
    "Spanisch": "spa",
    "Italienisch": "ita",
    "Niederländisch": "nld",
    "Polnisch": "pol",
    "Portugiesisch": "por",
}

DEFAULT_LANGUAGES: tuple[str, ...] = ("Deutsch", "Englisch")


def tessdata_dir() -> Path:
    """Benutzerschreibbares Verzeichnis für Tesseract-Sprachpakete (kein Admin nötig).

    Bewusst nicht das systemweite tessdata-Verzeichnis: Sprachen werden hier bei Bedarf
    im Hintergrund heruntergeladen, unabhängig davon, was via apt/Installer vorhanden ist.
    """
    path = Path(user_data_dir("scanner-app", "scanner-app")) / "tessdata"
    path.mkdir(parents=True, exist_ok=True)
    return path


def is_language_installed(display_name: str) -> bool:
    code = AVAILABLE_LANGUAGES[display_name]
    return (tessdata_dir() / f"{code}.traineddata").exists()


def installed_languages() -> list[str]:
    return [name for name in AVAILABLE_LANGUAGES if is_language_installed(name)]


def download_language(display_name: str) -> Path:
    """Lädt ein Sprachpaket herunter, falls noch nicht vorhanden. Blockierend —
    von der UI-Schicht aus einem Hintergrund-Thread aufzurufen, nicht im UI-Thread.
    """
    code = AVAILABLE_LANGUAGES[display_name]
    dest = tessdata_dir() / f"{code}.traineddata"
    if dest.exists():
        return dest

    url = f"{_TESSDATA_BASE_URL}/{code}.traineddata"
    tmp_dest = dest.with_suffix(".traineddata.part")
    with urllib.request.urlopen(url) as response, open(tmp_dest, "wb") as out_file:
        shutil.copyfileobj(response, out_file)
    tmp_dest.rename(dest)
    return dest


def ensure_default_languages_installed() -> None:
    for name in DEFAULT_LANGUAGES:
        if not is_language_installed(name):
            download_language(name)
