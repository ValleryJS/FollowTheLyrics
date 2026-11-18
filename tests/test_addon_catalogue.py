import hashlib
import io
import json
import zipfile

import pytest

from followthelyrics.addons.catalogue import Catalogue
from followthelyrics.addons.catalogue import CatalogueError


def response(data, url="https://example.org/catalog.json"):
    class Response(io.BytesIO):
        def geturl(self):
            return url

    return Response(data)


def listing(sha="a" * 64, kind="ftl"):
    return [
        {
            "id": "ets2-sync",
            "name": "ETS2 Sync",
            "version": "1.0",
            "description": "Show lyrics in trucks",
            "type": kind,
            "download_url": "https://example.org/ets2.zip",
            "sha256": sha,
            "instructions": "Install the game-side component separately.",
        }
    ]


def test_remote_catalogue_accepts_valid_approved_entries():
    client = Catalogue(
        opener=lambda *_args, **_kwargs: response(
            json.dumps({"addons": listing()}).encode()
        )
    )
    found = client.fetch()
    assert found[0].id == "ets2-sync"
    assert found[0].kind == "ftl"


def test_catalogue_rejects_non_https_download_links():
    entries = listing()
    entries[0]["download_url"] = "http://example.org/download.zip"
    client = Catalogue(
        opener=lambda *_args, **_kwargs: response(
            json.dumps({"addons": entries}).encode()
        )
    )
    with pytest.raises(CatalogueError):
        client.fetch()


def test_download_checks_sha256_before_install(tmp_path):
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as zip_file:
        zip_file.writestr("manifest.json", "{}")
    body = payload.getvalue()
    client = Catalogue(
        opener=lambda *_args, **_kwargs: response(
            body, "https://example.org/ets2.zip"
        )
    )
    addon = client.parse({"addons": listing(hashlib.sha256(body).hexdigest())})[
        0
    ]
    target = tmp_path / "download.zip"
    client.download(addon, target)
    assert target.read_bytes() == body


def test_bad_checksum_does_not_leave_download(tmp_path):
    client = Catalogue(
        opener=lambda *_args, **_kwargs: response(
            b"bad", "https://example.org/ets2.zip"
        )
    )
    addon = client.parse({"addons": listing()})[0]
    target = tmp_path / "download.zip"
    with pytest.raises(CatalogueError, match="checksum"):
        client.download(addon, target)
    assert not target.exists()


def test_external_game_mod_is_listed_as_download_only():
    client = Catalogue()
    addon = client.parse({"addons": listing(kind="external")})[0]
    assert addon.kind == "external"
