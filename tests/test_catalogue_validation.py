import hashlib
import json
import zipfile

import pytest
from tools.validate_addon_catalog import validate_catalogue


def catalogue_entry(**updates):
    entry = {
        "id": "hello-ftl",
        "name": "Hello",
        "version": "1.0.0",
        "description": "Example",
        "type": "ftl",
        "download_url": "https://example.org/hello.zip",
        "sha256": "a" * 64,
    }
    entry.update(updates)
    return entry


def test_validator_accepts_empty_catalogue(tmp_path):
    path = tmp_path / "catalog.json"
    path.write_text('{"addons": []}', encoding="utf-8")
    assert validate_catalogue(path) == 0


def test_validator_rejects_duplicate_ids(tmp_path):
    path = tmp_path / "catalog.json"
    entry = catalogue_entry()
    path.write_text(json.dumps({"addons": [entry, entry]}), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate"):
        validate_catalogue(path)


def test_validator_checks_ftl_manifest_without_running_addon(tmp_path):
    archive = tmp_path / "addon.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr(
            "manifest.json",
            json.dumps(
                {
                    "id": "wrong-id",
                    "name": "Hello",
                    "version": "1.0.0",
                    "api_version": 1,
                    "entry": "addon.py",
                }
            ),
        )
        z.writestr("addon.py", "raise RuntimeError('should never run')")
    path = tmp_path / "catalog.json"
    entry = catalogue_entry(
        sha256=hashlib.sha256(archive.read_bytes()).hexdigest()
    )
    path.write_text(json.dumps({"addons": [entry]}), encoding="utf-8")

    class FakeCatalogue:
        def download(self, item, dest):
            dest.write_bytes(archive.read_bytes())

    with pytest.raises(ValueError, match="manifest ID"):
        validate_catalogue(path, verify_downloads=True, client=FakeCatalogue())
