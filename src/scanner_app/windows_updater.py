from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
import urllib.request
from collections.abc import Callable
from pathlib import Path

_CHUNK_SIZE = 256 * 1024
_TIMEOUT_SECONDS = 30
_USER_AGENT = "scanner-app-update"


class UpdateInstallError(Exception):
    """Download, Prüfsummen-Mismatch oder Start des Installers ist fehlgeschlagen."""


def is_installed_windows_build() -> bool:
    """True nur für eine über den Inno-Setup-Installer installierte Windows-Version — nie für
    die portable .exe (kein Installationsordner mit Uninstaller) und nie für einen Start aus
    dem Quellcode (kein gefrorenes PyInstaller-Executable). In den anderen Fällen bleibt es
    beim reinen Hinweis-Dialog mit Link zur Release-Seite — ein automatisch heruntergeladener
    Installer hätte dort keine laufende Datei zum Ersetzen bzw. keinen Sinn.
    """
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        return False
    return (Path(sys.executable).parent / "unins000.exe").exists()


def fetch_checksum(url: str) -> str:
    """Lädt die kleine `.sha256`-Sidecar-Datei (siehe package.yml) und liest den Hex-Digest
    heraus — akzeptiert sowohl eine reine Hex-Zeile als auch das `sha256sum`-Format
    ('<hex>  <dateiname>').
    """
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
            text = response.read().decode("utf-8", errors="strict")
    except Exception as exc:
        raise UpdateInstallError(f"Prüfsumme konnte nicht geladen werden: {exc}") from exc

    first_token = text.strip().split()[0] if text.strip() else ""
    if len(first_token) != 64:
        raise UpdateInstallError("Unerwartetes Format der Prüfsummen-Datei.")
    return first_token


def download_installer(
    url: str,
    expected_sha256: str,
    *,
    progress_callback: Callable[[int, int], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> Path:
    """Lädt den Setup-.exe-Release-Asset in eine temporäre Datei und verifiziert seine
    SHA-256-Prüfsumme gegen den vom Release-Workflow mitveröffentlichten `.sha256`-Sidecar.

    Ohne diese Prüfung würde ein automatisch gestarteter Installer jede über die URL
    erreichbare Datei ausführen — ein reales Sicherheitsrisiko (MITM, kompromittierter
    Mirror/CDN), das die ursprüngliche MVP-Update-Prüfung bewusst vermieden hat, indem sie
    überhaupt nichts automatisch ausführte (siehe Issue #2).

    `cancel_check` wird zwischen Chunks aufgerufen — liefert es True, bricht der Download
    sauber mit `UpdateInstallError` ab (statt den Hintergrund-Thread hart zu terminieren).
    """
    fd, tmp_name = tempfile.mkstemp(prefix="scanner-update-", suffix=".exe")
    dest = Path(tmp_name)
    digest = hashlib.sha256()
    try:
        # os.fdopen(fd, ...) MUSS das äußerste with sein, nicht innerhalb von urlopen()
        # verschachtelt: sein __exit__ (schließt den Datei-Handle) muss auf JEDEM Fehlerpfad
        # laufen, BEVOR die except-Blöcke unten dest.unlink() aufrufen — unter Windows lässt
        # sich eine Datei mit noch offenem Handle nicht löschen (PermissionError), anders als
        # unter Linux/POSIX, wo das stillschweigend funktioniert. War ein reproduzierbarer,
        # von der Windows-CI aufgedeckter Bug, nicht nur eine theoretische Möglichkeit.
        with os.fdopen(fd, "wb") as f:
            request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
            with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
                total = int(response.headers.get("Content-Length") or 0)
                written = 0
                while True:
                    if cancel_check is not None and cancel_check():
                        raise UpdateInstallError("Download abgebrochen.")
                    chunk = response.read(_CHUNK_SIZE)
                    if not chunk:
                        break
                    f.write(chunk)
                    digest.update(chunk)
                    written += len(chunk)
                    if progress_callback:
                        progress_callback(written, total)
    except UpdateInstallError:
        dest.unlink(missing_ok=True)
        raise
    except Exception as exc:
        dest.unlink(missing_ok=True)
        raise UpdateInstallError(f"Download fehlgeschlagen: {exc}") from exc

    if digest.hexdigest().lower() != expected_sha256.strip().lower():
        dest.unlink(missing_ok=True)
        raise UpdateInstallError("Prüfsumme des heruntergeladenen Installers stimmt nicht überein.")

    return dest


def launch_silent_install(installer_path: Path) -> None:
    """Startet den heruntergeladenen Installer losgelöst (überlebt das Beenden dieses
    Prozesses) im stillen Modus.

    `/CLOSEAPPLICATIONS /RESTARTAPPLICATIONS` aktiviert Inno Setups Windows-Restart-Manager-
    Integration (siehe packaging/scanner.iss) als Sicherheitsnetz — die eigentliche Anwendung
    beendet sich nach dem erfolgreichen Start dieses Prozesses aber bereits selbst geordnet
    (siehe MainWindow), sodass der Restart Manager im Normalfall gar nicht eingreifen muss.
    """
    creation_flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
        subprocess, "CREATE_NEW_PROCESS_GROUP", 0
    )
    try:
        subprocess.Popen(
            [
                str(installer_path),
                "/VERYSILENT",
                "/SUPPRESSMSGBOXES",
                "/NORESTART",
                "/CLOSEAPPLICATIONS",
                "/RESTARTAPPLICATIONS",
            ],
            creationflags=creation_flags,
            close_fds=True,
        )
    except OSError as exc:
        raise UpdateInstallError(f"Installer konnte nicht gestartet werden: {exc}") from exc
