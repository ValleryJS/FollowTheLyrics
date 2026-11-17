from followthelyrics.ui.panel import PAGES
from followthelyrics.ui.panel import Panel


def test_addons_page_registered():
    assert "addons" in [page[0] for page in PAGES]
    assert callable(Panel.build_addons)
