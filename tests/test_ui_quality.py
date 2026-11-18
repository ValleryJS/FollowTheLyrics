import inspect

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

from followthelyrics.ui import widgets
from followthelyrics.ui.panel import Panel


def test_windows_ui_prefers_native_segoe_font():
    available = {"Segoe UI", "Helvetica Neue", "TeX Gyre Heros"}
    assert widgets.preferred_font_family(available, "win32") == "Segoe UI"
    assert widgets.preferred_font_family(available, "linux") == "Helvetica Neue"


def test_small_ui_fonts_request_antialiasing_and_hinting():
    app = QApplication.instance() or QApplication([])
    font = widgets.ui_font(13)
    assert font.styleStrategy() & QFont.StyleStrategy.PreferAntialias
    assert font.hintingPreference() == QFont.HintingPreference.PreferFullHinting
    assert app is not None


def test_page_titles_are_not_rasterized_through_drop_shadow():
    source = inspect.getsource(Panel.__init__)
    assert "page_title.setGraphicsEffect" not in source
