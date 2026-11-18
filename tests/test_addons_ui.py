import json
import zipfile
from types import SimpleNamespace

from PyQt6.QtWidgets import QApplication
from PyQt6.QtWidgets import QPushButton

from followthelyrics.addons.catalogue import Catalogue
from followthelyrics.addons.manager import AddonManager
from followthelyrics.ui.addons_page import AddonsPage
from followthelyrics.ui.panel import PAGES
from followthelyrics.ui.panel import Panel


def test_addons_page_registered():
    assert "addons" in [page[0] for page in PAGES]
    assert callable(Panel.build_addons)


def test_addons_page_shows_catalogue_and_manual_install(tmp_path):
    qt_app = QApplication.instance() or QApplication([])
    _ = qt_app
    page = AddonsPage(SimpleNamespace(addons=AddonManager(tmp_path)))
    buttons = {button.text() for button in page.findChildren(QPushButton)}
    assert "Refresh catalogue" in buttons
    assert "Install ZIP manually" in buttons
    page.show_catalogue(
        Catalogue.parse(
            {
                "addons": [
                    {
                        "id": "ets2-sync",
                        "name": "ETS2 Sync",
                        "version": "1.0",
                        "description": "External game mod",
                        "type": "external",
                        "download_url": "https://example.org/ets2.zip",
                        "sha256": "a" * 64,
                        "instructions": "Place it in your game directory.",
                    }
                ]
            }
        )
    )
    buttons = {button.text() for button in page.findChildren(QPushButton)}
    assert "Download ZIP" in buttons
    page.close()


def test_catalogue_marks_installed_plugin_updates(tmp_path):
    qt_app = QApplication.instance() or QApplication([])
    _ = qt_app
    manager = AddonManager(tmp_path)
    archive = tmp_path / "plugin.zip"
    with zipfile.ZipFile(archive, "w") as source:
        source.writestr(
            "manifest.json",
            json.dumps(
                {
                    "id": "sample-addon",
                    "name": "Example",
                    "version": "1.0.0",
                    "api_version": 1,
                    "entry": "addon.py",
                }
            ),
        )
        source.writestr("addon.py", "")
    manager.install(archive)
    page = AddonsPage(SimpleNamespace(addons=manager))
    page.show_catalogue(
        Catalogue.parse(
            {
                "addons": [
                    {
                        "id": "sample-addon",
                        "name": "Example",
                        "version": "2.0.0",
                        "description": "New",
                        "type": "ftl",
                        "download_url": "https://example.org/sample.zip",
                        "sha256": "a" * 64,
                    }
                ]
            }
        )
    )
    assert "Update" in {
        button.text() for button in page.findChildren(QPushButton)
    }
    page.close()
