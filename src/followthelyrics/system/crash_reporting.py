import faulthandler
import logging
import sys
import threading
from pathlib import Path

logger = logging.getLogger(__name__)
_stream = None
_previous_hook = None
_previous_thread_hook = None


def install(path):
    global _stream, _previous_hook, _previous_thread_hook
    if _previous_hook is not None:
        return
    _previous_hook = sys.excepthook
    _previous_thread_hook = threading.excepthook

    def on_exception(error_type, error, traceback):
        logger.critical(
            "Unhandled application exception",
            exc_info=(error_type, error, traceback),
        )
        if _previous_hook is not None:
            _previous_hook(error_type, error, traceback)

    def on_thread_exception(args):
        logger.critical(
            "Unhandled exception in thread %s",
            args.thread.name if args.thread else "unknown",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )
        if _previous_thread_hook is not None:
            _previous_thread_hook(args)

    sys.excepthook = on_exception
    threading.excepthook = on_thread_exception

    try:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        _stream = target.open("a", encoding="utf-8")
        faulthandler.enable(file=_stream, all_threads=True)
    except (OSError, RuntimeError, ValueError):
        logger.warning("Native crash tracing could not be enabled")


def uninstall():
    global _stream, _previous_hook, _previous_thread_hook
    if _previous_hook is None:
        return
    sys.excepthook = _previous_hook
    if _previous_thread_hook is not None:
        threading.excepthook = _previous_thread_hook
    _previous_hook = None
    _previous_thread_hook = None
    faulthandler.disable()
    if _stream is not None:
        _stream.close()
        _stream = None
