from __future__ import annotations

import os
import shutil
import subprocess
import urllib.request
from pathlib import Path

from scanner_app.ocr.language_manager import tessdata_dir

_OSD_URL = "https://github.com/tesseract-ocr/tessdata/raw/main/osd.traineddata"
_OSD_FILENAME = "osd.traineddata"


def is_osd_installed() -> bool:
    return (tessdata_dir() / _OSD_FILENAME).exists()


def ensure_osd_installed() -> Path:
    """Lädt das für die Ausrichtungserkennung benötigte OSD-Modell bei Bedarf herunter.
    Blockierend — von der UI aus einem Hintergrund-Thread aufzurufen, nicht im UI-Thread.
    """
    dest = tessdata_dir() / _OSD_FILENAME
    if dest.exists():
        return dest

    tmp_dest = dest.with_suffix(".traineddata.part")
    with urllib.request.urlopen(_OSD_URL) as response, open(tmp_dest, "wb") as out_file:
        shutil.copyfileobj(response, out_file)
    tmp_dest.rename(dest)
    return dest


def detect_rotation(image_path: Path | str) -> int:
    """Erkennt per Tesseract-Ausrichtungserkennung (OSD), um wie viel Grad im Uhrzeigersinn
    das Bild gedreht werden muss, damit es aufrecht steht.

    Gibt 0 zurück, wenn keine verlässliche Erkennung möglich ist (z.B. zu wenig Text auf der
    Seite, Tesseract/OSD-Modell fehlt) — die Seite bleibt dann unverändert, statt einen Fehler
    zu werfen, da Ausrichtungserkennung ein Best-effort-Komfortfeature ist.
    """
    env = os.environ.copy()
    env["TESSDATA_PREFIX"] = str(tessdata_dir())
    try:
        result = subprocess.run(
            ["tesseract", str(image_path), "stdout", "--psm", "0"],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return 0

    for line in result.stdout.splitlines():
        if line.startswith("Rotate:"):
            try:
                return int(line.split(":", 1)[1].strip()) % 360
            except ValueError:
                return 0
    return 0
