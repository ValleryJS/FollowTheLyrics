import logging
import sys

from followthelyrics.system import crash_reporting


def test_unhandled_exception_is_logged_before_default_handler(
    monkeypatch, caplog, tmp_path
):
    called = []
    monkeypatch.setattr(sys, "excepthook", lambda *args: called.append(args))
    monkeypatch.setattr(crash_reporting.faulthandler, "enable", lambda **kwargs: None)
    crash_reporting.install(tmp_path / "crash.log")
    try:
        with caplog.at_level(logging.CRITICAL):
            try:
                raise RuntimeError("idle-crash-marker")
            except RuntimeError:
                sys.excepthook(*sys.exc_info())
        assert "idle-crash-marker" in caplog.text
        assert len(called) == 1
    finally:
        crash_reporting.uninstall()
