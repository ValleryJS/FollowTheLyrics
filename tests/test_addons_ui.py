import inspect

from followthelyrics.ui.panel import PAGES
from followthelyrics.ui.panel import Panel


def test_addons_page_registered():
    assert "addons" in [page[0] for page in PAGES]
    assert callable(Panel.build_addons)


def test_addons_page_is_coming_soon_only():
    source = inspect.getsource(Panel.build_addons)
    assert "Coming soon - feature in development" in source
    assert "fivem" not in source.lower()
    assert "install_selected_addon" not in source
