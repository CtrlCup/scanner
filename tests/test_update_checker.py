import json
from unittest.mock import MagicMock, patch

from scanner_app.update_checker import check_for_update, is_newer


def test_is_newer_true_for_higher_patch():
    assert is_newer("v1.2.4", "1.2.3") is True


def test_is_newer_false_for_equal_version():
    assert is_newer("v1.2.3", "1.2.3") is False


def test_is_newer_false_for_lower_version():
    assert is_newer("v1.0.0", "1.2.3") is False


def test_is_newer_handles_missing_v_prefix():
    assert is_newer("2.0.0", "1.9.9") is True


def _fake_response(payload: dict):
    body = json.dumps(payload).encode("utf-8")

    class _Resp:
        def read(self) -> bytes:
            return body

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    return _Resp()


def test_check_for_update_returns_info_when_newer_release_exists():
    payload = {
        "tag_name": "v9.9.9",
        "html_url": "https://github.com/CtrlCup/scanner/releases/tag/v9.9.9",
        "body": "Neue Features",
    }
    with patch("scanner_app.update_checker.urllib.request.urlopen", return_value=_fake_response(payload)):
        info = check_for_update("0.1.0")
    assert info is not None
    assert info.version == "9.9.9"
    assert info.html_url.endswith("v9.9.9")
    assert info.notes == "Neue Features"


def test_check_for_update_returns_none_when_already_current():
    payload = {"tag_name": "v0.1.0", "html_url": "https://x", "body": ""}
    with patch("scanner_app.update_checker.urllib.request.urlopen", return_value=_fake_response(payload)):
        assert check_for_update("0.1.0") is None


def test_check_for_update_returns_none_on_network_error():
    with patch("scanner_app.update_checker.urllib.request.urlopen", side_effect=OSError("kein Netz")):
        assert check_for_update("0.1.0") is None


def test_check_for_update_returns_none_on_malformed_response():
    bad_response = MagicMock()
    bad_response.__enter__.return_value = bad_response
    bad_response.read.return_value = b"not json"
    with patch("scanner_app.update_checker.urllib.request.urlopen", return_value=bad_response):
        assert check_for_update("0.1.0") is None
