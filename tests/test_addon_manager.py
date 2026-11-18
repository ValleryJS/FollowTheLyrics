import json
import zipfile

import pytest

from followthelyrics.addons.manager import AddonError
from followthelyrics.addons.manager import AddonManager


def package(path, manifest=None, code=""):
    if manifest is None:
        manifest = {
            "id": "sample-addon",
            "name": "Sample add-on",
            "version": "1.0.0",
            "api_version": 1,
            "entry": "addon.py",
        }
    with zipfile.ZipFile(path, "w") as out:
        out.writestr("manifest.json", json.dumps(manifest))
        out.writestr("addon.py", code)
    return path


def test_install_enable_events_disable_and_restart(tmp_path):
    script = (
        "def on_enable(api):\n"
        "    api.log('enabled')\n"
        "def on_track(track):\n"
        "    open(DATA_FILE, 'a').write(str(track) + '\\n')\n"
        "def on_lyrics(key, lines):\n"
        "    open(DATA_FILE, 'a').write(key + ':' + str(len(lines)) + '\\n')\n"
        "def on_disable():\n"
        "    open(DATA_FILE, 'a').write('disabled\\n')\n"
    )
    data_file = tmp_path / "events.txt"
    script = f"DATA_FILE = {str(data_file)!r}\n" + script
    manager = AddonManager(tmp_path / "data")
    addon = manager.install(package(tmp_path / "sample.zip", code=script))
    assert addon.id == "sample-addon"
    assert addon.enabled is False
    manager.enable("sample-addon")
    manager.emit("on_track", {"title": "Hello"})
    manager.emit("on_lyrics", "track-1", [{"text": "Hello"}])
    manager.disable("sample-addon")
    assert "track-1:1" in data_file.read_text()
    assert "disabled" in data_file.read_text()
    restarted = AddonManager(tmp_path / "data")
    assert restarted.list_addons()[0].enabled is False


def test_enabled_addon_restores_on_restart(tmp_path):
    manager = AddonManager(tmp_path / "data")
    manager.install(package(tmp_path / "sample.zip"))
    manager.enable("sample-addon")
    restored = AddonManager(tmp_path / "data")
    assert restored.list_addons()[0].enabled is True
    restored.shutdown()
    after_clean_exit = AddonManager(tmp_path / "data")
    assert after_clean_exit.list_addons()[0].enabled is True
    after_clean_exit.disable("sample-addon")


def test_bad_addon_cannot_escape_install_directory(tmp_path):
    archive = tmp_path / "malicious.zip"
    with zipfile.ZipFile(archive, "w") as out:
        out.writestr(
            "manifest.json",
            json.dumps(
                {
                    "id": "test",
                    "name": "Test",
                    "version": "1",
                    "api_version": 1,
                    "entry": "addon.py",
                }
            ),
        )
        out.writestr("../escaped.py", "bad")
        out.writestr("addon.py", "")
    with pytest.raises(AddonError):
        AddonManager(tmp_path / "data").install(archive)
    assert not (tmp_path / "escaped.py").exists()


def test_duplicate_ids_and_unsupported_api_are_rejected(tmp_path):
    manager = AddonManager(tmp_path / "data")
    archive = package(tmp_path / "sample.zip")
    manager.install(archive)
    with pytest.raises(AddonError, match="installed"):
        manager.install(archive)
    future = package(
        tmp_path / "future.zip",
        manifest={
            "id": "future",
            "name": "Future",
            "version": "1",
            "api_version": 2,
            "entry": "addon.py",
        },
    )
    with pytest.raises(AddonError, match="API"):
        manager.install(future)


def test_plugin_failure_is_isolated_and_can_be_disabled(tmp_path):
    manager = AddonManager(tmp_path / "data")
    manager.install(
        package(
            tmp_path / "sample.zip",
            code=("def on_track(track):\n    raise RuntimeError('broken')\n"),
        )
    )
    manager.enable("sample-addon")
    manager.emit("on_track", {"title": "Hello"})
    assert "broken" in manager.list_addons()[0].error
    manager.disable("sample-addon")
    assert manager.list_addons()[0].enabled is False


def test_uninstall_removes_only_selected_addon(tmp_path):
    manager = AddonManager(tmp_path / "data")
    manager.install(package(tmp_path / "sample.zip"))
    manager.uninstall("sample-addon")
    assert manager.list_addons() == []
    assert (tmp_path / "data" / "addons").is_dir()


def test_update_replaces_package_and_preserves_enabled_state(tmp_path):
    manager = AddonManager(tmp_path / "data")
    first = package(tmp_path / "old.zip", code="VERSION = 'old'\n")
    manager.install(first, approved=True)
    manager.enable("sample-addon")
    new_manifest = {
        "id": "sample-addon",
        "name": "Sample add-on",
        "version": "2.0.0",
        "api_version": 1,
        "entry": "addon.py",
    }
    updated = package(
        tmp_path / "new.zip",
        manifest=new_manifest,
        code="VERSION = 'new'\n",
    )
    result = manager.update("sample-addon", updated, approved=True)
    assert result.version == "2.0.0"
    assert result.enabled is True
    assert manager.modules["sample-addon"].VERSION == "new"
    assert result.approved is True


def test_update_failure_restores_previous_package_and_process(tmp_path):
    manager = AddonManager(tmp_path / "data")
    manager.install(package(tmp_path / "old.zip", code="VERSION = 'old'\n"))
    manager.enable("sample-addon")
    newer = package(
        tmp_path / "bad.zip",
        manifest={
            "id": "sample-addon",
            "name": "Broken",
            "version": "2.0.0",
            "api_version": 1,
            "entry": "addon.py",
        },
        code="raise RuntimeError('cannot start')\n",
    )
    with pytest.raises(AddonError, match="restored"):
        manager.update("sample-addon", newer)
    assert manager.list_addons()[0].version == "1.0.0"
    assert manager.list_addons()[0].enabled is True
    assert manager.modules["sample-addon"].VERSION == "old"


def test_update_rejects_wrong_addon_id_without_modifying_existing(tmp_path):
    manager = AddonManager(tmp_path / "data")
    manager.install(package(tmp_path / "old.zip"))
    wrong = package(
        tmp_path / "wrong.zip",
        manifest={
            "id": "another-addon",
            "name": "Another",
            "version": "2.0.0",
            "api_version": 1,
            "entry": "addon.py",
        },
    )
    with pytest.raises(AddonError, match="ID"):
        manager.update("sample-addon", wrong)
    assert manager.list_addons()[0].version == "1.0.0"


def test_external_download_history_survives_restart(tmp_path):
    manager = AddonManager(tmp_path / "data")
    assert manager.external_version("ets2-sync") is None
    manager.mark_external_download("ets2-sync", "1.0.0")
    restarted = AddonManager(tmp_path / "data")
    assert restarted.external_version("ets2-sync") == "1.0.0"
