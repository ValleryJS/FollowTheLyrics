import hashlib
import io
import json
import time
import zipfile

import pytest

from followthelyrics.lyrics.model import Line
from followthelyrics.system import addons


def archive(manifest, extra=None):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        z.writestr("addon.json", json.dumps(manifest))
        for path, content in (extra or {}).items():
            z.writestr(path, content)
    return stream.getvalue()


def test_catalogue_rejects_untrusted_downloads():
    payload = {
        "addons": [
            {
                "id": "example",
                "name": "Test",
                "version": "1.0.0",
                "download": "http://example.com/a.zip",
                "sha256": "a" * 64,
            }
        ]
    }
    assert addons.parse_catalogue(payload) == []


def test_catalogue_accepts_valid_entries():
    entry = {
        "id": "example",
        "name": "Example",
        "version": "1.0.0",
        "author": "Test",
        "download": "https://github.com/example/repo/releases/download/v1/a.zip",
        "sha256": "a" * 64,
    }
    assert addons.parse_catalogue({"addons": [entry]}) == [entry]


def test_install_archive_disabled_by_default(tmp_path):
    manager = addons.AddonManager(tmp_path)
    manifest = {
        "id": "example",
        "name": "Example",
        "version": "1.0.0",
        "entrypoint": "main.py",
        "permissions": ["lyrics.read"],
    }
    data = archive(manifest, {"main.py": "print('hello')"})
    manager.install(data, "example", hashlib.sha256(data).hexdigest())
    assert (tmp_path / "addons" / "example" / "main.py").exists()
    assert manager.installed()[0]["enabled"] is False


def test_zip_traversal_rejected(tmp_path):
    manager = addons.AddonManager(tmp_path)
    manifest = {
        "id": "example",
        "name": "Example",
        "version": "1.0.0",
        "entrypoint": "main.py",
    }
    data = archive(manifest, {"../escape.txt": "bad", "main.py": "pass"})
    with pytest.raises(ValueError):
        manager.install(data, "example", hashlib.sha256(data).hexdigest())
    assert not (tmp_path / "escape.txt").exists()


def test_invalid_digest_rejected(tmp_path):
    manager = addons.AddonManager(tmp_path)
    with pytest.raises(ValueError):
        manager.install(b"content", "example", "0" * 64)


def test_enabled_addon_receives_events(tmp_path):
    manager = addons.AddonManager(tmp_path)
    manifest = {
        "id": "example",
        "name": "Example",
        "version": "1.0.0",
        "entrypoint": "main.py",
    }
    script = (
        "import pathlib,sys\n"
        "pathlib.Path('received.txt').write_text(sys.stdin.readline())\n"
    )
    data = archive(manifest, {"main.py": script})
    manager.install(data, "example", hashlib.sha256(data).hexdigest())
    manager.set_enabled("example", True)
    runtime = addons.AddonRuntime(manager)
    try:
        runtime.start_enabled()
        runtime.publish({"type": "track", "title": "Demo"})
        target = tmp_path / "addons" / "example" / "received.txt"
        for _ in range(100):
            if target.exists():
                break
            time.sleep(0.02)
        assert json.loads(target.read_text())["title"] == "Demo"
    finally:
        runtime.stop()


def test_lyric_event_includes_word_and_character_timing():
    line = Line(12.0, "Hello world", chars=[(12.0, 12.2)], end=14.0)
    event = addons.lyrics_event([line])
    assert event["type"] == "lyrics"
    assert event["lines"][0]["text"] == "Hello world"
    assert event["lines"][0]["chars"] == [[12.0, 12.2]]


def test_only_fivem_addon_may_report_renderer_readiness(tmp_path):
    runtime = addons.AddonRuntime(addons.AddonManager(tmp_path))
    runtime.receive_event("other-addon", '{"type":"rendering","ready":true}')
    assert runtime.drain_events() == []
    runtime.receive_event("fivem-reshade", '{"type":"rendering","ready":true}')
    assert runtime.drain_events() == [
        {"addon_id": "fivem-reshade", "type": "rendering", "ready": True}
    ]
