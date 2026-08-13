import hashlib
from unittest.mock import patch

import pytest

from scanner_app.windows_updater import (
    UpdateInstallError,
    download_installer,
    fetch_checksum,
    is_installed_windows_build,
    launch_silent_install,
)


def test_is_installed_windows_build_false_outside_windows():
    # Diese Tests laufen unter Linux/CI — dort muss die Erkennung immer False liefern, ganz
    # unabhängig von sys.frozen, da sys.platform bereits nicht "win32" ist.
    assert is_installed_windows_build() is False


class _FakeResponse:
    def __init__(self, body: bytes, headers: dict[str, str] | None = None) -> None:
        self._body = body
        self._pos = 0
        self.headers = headers or {}

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            chunk, self._pos = self._body[self._pos :], len(self._body)
            return chunk
        chunk = self._body[self._pos : self._pos + size]
        self._pos += len(chunk)
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def test_fetch_checksum_parses_plain_hex_line():
    digest = "a" * 64
    with patch("scanner_app.windows_updater.urllib.request.urlopen", return_value=_FakeResponse(digest.encode())):
        assert fetch_checksum("https://example.invalid/x.sha256") == digest


def test_fetch_checksum_parses_sha256sum_format():
    digest = "b" * 64
    body = f"{digest}  Scanner-1.0.0-windows-x86_64-setup.exe\n".encode()
    with patch("scanner_app.windows_updater.urllib.request.urlopen", return_value=_FakeResponse(body)):
        assert fetch_checksum("https://example.invalid/x.sha256") == digest


def test_fetch_checksum_rejects_malformed_content():
    with (
        patch("scanner_app.windows_updater.urllib.request.urlopen", return_value=_FakeResponse(b"nope")),
        pytest.raises(UpdateInstallError),
    ):
        fetch_checksum("https://example.invalid/x.sha256")


def test_fetch_checksum_wraps_network_error():
    with (
        patch("scanner_app.windows_updater.urllib.request.urlopen", side_effect=OSError("kein Netz")),
        pytest.raises(UpdateInstallError),
    ):
        fetch_checksum("https://example.invalid/x.sha256")


def test_download_installer_succeeds_with_matching_checksum():
    body = b"fake installer bytes" * 1000
    expected = hashlib.sha256(body).hexdigest()
    progress: list[tuple[int, int]] = []

    with patch(
        "scanner_app.windows_updater.urllib.request.urlopen",
        return_value=_FakeResponse(body, headers={"Content-Length": str(len(body))}),
    ):
        path = download_installer(
            "https://example.invalid/setup.exe", expected, progress_callback=lambda done, total: progress.append((done, total))
        )

    try:
        assert path.exists()
        assert path.read_bytes() == body
        assert progress  # mindestens ein Fortschritts-Callback wurde aufgerufen
        assert progress[-1][0] == len(body)
    finally:
        path.unlink(missing_ok=True)


def test_download_installer_rejects_checksum_mismatch():
    body = b"fake installer bytes"
    with patch(
        "scanner_app.windows_updater.urllib.request.urlopen",
        return_value=_FakeResponse(body, headers={"Content-Length": str(len(body))}),
    ), pytest.raises(UpdateInstallError, match="Prüfsumme"):
        download_installer("https://example.invalid/setup.exe", "0" * 64)


def test_download_installer_respects_cancel_check():
    body = b"x" * (_chunk_size_for_test() * 3)
    calls = {"n": 0}

    def cancel_check():
        calls["n"] += 1
        return calls["n"] > 1

    with patch(
        "scanner_app.windows_updater.urllib.request.urlopen",
        return_value=_FakeResponse(body, headers={"Content-Length": str(len(body))}),
    ), pytest.raises(UpdateInstallError, match="abgebrochen"):
        download_installer(
            "https://example.invalid/setup.exe", "0" * 64, cancel_check=cancel_check
        )


def _chunk_size_for_test() -> int:
    from scanner_app.windows_updater import _CHUNK_SIZE

    return _CHUNK_SIZE


def test_download_installer_wraps_network_error():
    with (
        patch("scanner_app.windows_updater.urllib.request.urlopen", side_effect=OSError("kein Netz")),
        pytest.raises(UpdateInstallError),
    ):
        download_installer("https://example.invalid/setup.exe", "0" * 64)


def test_launch_silent_install_invokes_expected_flags(tmp_path):
    installer = tmp_path / "setup.exe"
    installer.write_bytes(b"x")
    with patch("scanner_app.windows_updater.subprocess.Popen") as mock_popen:
        launch_silent_install(installer)
    args = mock_popen.call_args.args[0]
    assert args[0] == str(installer)
    assert "/VERYSILENT" in args
    assert "/CLOSEAPPLICATIONS" in args
    assert "/RESTARTAPPLICATIONS" in args


def test_launch_silent_install_wraps_oserror(tmp_path):
    installer = tmp_path / "setup.exe"
    installer.write_bytes(b"x")
    with (
        patch("scanner_app.windows_updater.subprocess.Popen", side_effect=OSError("nope")),
        pytest.raises(UpdateInstallError),
    ):
        launch_silent_install(installer)
