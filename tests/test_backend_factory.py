import sys

import pytest

from scanner_app.backend import ScannerBackend, get_backend


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux-spezifischer Backend-Test")
def test_get_backend_returns_sane_backend_on_linux():
    from scanner_app.backend.linux_sane import SaneScannerBackend

    backend = get_backend()
    assert isinstance(backend, SaneScannerBackend)
    assert isinstance(backend, ScannerBackend)
