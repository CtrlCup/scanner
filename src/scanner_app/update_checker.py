from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass

_API_URL = "https://api.github.com/repos/CtrlCup/scanner/releases/latest"
_TIMEOUT_SECONDS = 8
_WINDOWS_INSTALLER_SUFFIX = "-windows-x86_64-setup.exe"


@dataclass
class UpdateInfo:
    version: str
    html_url: str
    notes: str
    # None, wenn das Release (noch) keinen Windows-Installer bzw. keine dazugehörige
    # .sha256-Prüfsumme als Asset enthält — dann bleibt nur der Hinweis-Dialog mit Link
    # zur Release-Seite (siehe MainWindow._on_update_available).
    windows_installer_url: str | None = None
    windows_installer_checksum_url: str | None = None


def _find_asset_url(assets: list[dict], suffix: str) -> str | None:
    for asset in assets:
        name = asset.get("name") or ""
        if name.endswith(suffix):
            return asset.get("browser_download_url")
    return None


def _parse_version(tag: str) -> tuple[int, ...]:
    cleaned = tag.lstrip("vV")
    parts = []
    for piece in cleaned.split("."):
        digits = "".join(ch for ch in piece if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def is_newer(remote_version: str, current_version: str) -> bool:
    return _parse_version(remote_version) > _parse_version(current_version)


def check_for_update(current_version: str) -> UpdateInfo | None:
    """Fragt die neueste GitHub-Release-Version ab.

    Gibt bei jedem Fehler (kein Internet, Rate-Limit, unerwartete Antwort, ...) still None
    zurück, statt eine Exception zu werfen — Update-Prüfung ist ein Komfortfeature und darf
    die App-Stabilität nie beeinträchtigen (siehe Issue #2). Blockierend, daher nur aus einem
    Hintergrund-Thread aufrufen, nie im UI-Thread.
    """
    request = urllib.request.Request(
        _API_URL,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "scanner-app-update-check"},
    )
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
            data = json.load(response)
    except Exception:  # noqa: BLE001 - jeder Fehler zählt als "kein Update verfügbar"
        return None

    tag = data.get("tag_name") or ""
    if not tag or not is_newer(tag, current_version):
        return None

    assets = data.get("assets") or []
    return UpdateInfo(
        version=tag.lstrip("vV"),
        html_url=data.get("html_url") or "https://github.com/CtrlCup/scanner/releases/latest",
        notes=(data.get("body") or "").strip(),
        windows_installer_url=_find_asset_url(assets, _WINDOWS_INSTALLER_SUFFIX),
        windows_installer_checksum_url=_find_asset_url(assets, _WINDOWS_INSTALLER_SUFFIX + ".sha256"),
    )
