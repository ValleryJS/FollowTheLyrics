"""Developer-maintained catalogue for approved integrations."""

import hashlib
import json
import os
import re
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

CATALOGUE_URL = (
    "https://raw.githubusercontent.com/War3l/FollowTheLyrics/"
    "main/addons/catalog.json"
)
MAX_CATALOGUE_BYTES = 1024 * 1024
MAX_DOWNLOAD_BYTES = 80 * 1024 * 1024


def is_newer(installed: str, available: str) -> bool:
    """Compare numeric release versions without lexicographic mistakes."""

    def parts(value: str):
        value = value.removeprefix("v")
        if not re.fullmatch(r"\d+(?:\.\d+){0,3}", value):
            return None
        numbers = tuple(int(part) for part in value.split("."))
        return numbers + (0,) * (4 - len(numbers))

    before, after = parts(installed), parts(available)
    return before is not None and after is not None and after > before


class CatalogueError(ValueError):
    pass


@dataclass(frozen=True)
class CatalogueAddon:
    id: str
    name: str
    version: str
    description: str
    kind: str
    download_url: str
    sha256: str
    instructions: str = ""


class Catalogue:
    def __init__(self, url: str = CATALOGUE_URL, opener=None):
        self.url = url
        self.opener = opener or urllib.request.urlopen

    def _open(self, url: str):
        if urlsplit(url).scheme != "https":
            raise CatalogueError("Add-on links must use HTTPS")
        response = self.opener(
            urllib.request.Request(
                url, headers={"User-Agent": "FollowTheLyrics-AddonCatalogue"}
            ),
            timeout=15,
        )
        if urlsplit(response.geturl()).scheme != "https":
            response.close()
            raise CatalogueError("Insecure catalogue redirect")
        return response

    @staticmethod
    def parse(payload: object) -> list[CatalogueAddon]:
        if not isinstance(payload, dict) or not isinstance(
            payload.get("addons"), list
        ):
            raise CatalogueError("Invalid add-on catalogue")
        items = []
        ids = set()
        for item in payload["addons"]:
            if not isinstance(item, dict):
                raise CatalogueError("Invalid catalogue entry")
            ident = item.get("id")
            if not isinstance(ident, str) or not re.fullmatch(
                r"[a-z0-9][a-z0-9_-]{1,63}", ident
            ):
                raise CatalogueError("Invalid catalogue add-on ID")
            if ident in ids:
                raise CatalogueError("Duplicate catalogue add-on ID")
            ids.add(ident)
            for field in (
                "name",
                "version",
                "description",
                "download_url",
                "sha256",
            ):
                if not isinstance(item.get(field), str):
                    raise CatalogueError(f"Invalid add-on {field}")
            if item.get("type") not in ("ftl", "external"):
                raise CatalogueError("Unknown add-on installation type")
            if urlsplit(item["download_url"]).scheme != "https":
                raise CatalogueError("Add-on downloads must use HTTPS")
            if not re.fullmatch(r"[0-9a-fA-F]{64}", item["sha256"]):
                raise CatalogueError("Invalid add-on SHA256")
            items.append(
                CatalogueAddon(
                    id=ident,
                    name=item["name"],
                    version=item["version"],
                    description=item["description"],
                    kind=item["type"],
                    download_url=item["download_url"],
                    sha256=item["sha256"].lower(),
                    instructions=str(item.get("instructions", "")),
                )
            )
        return items

    def fetch(self) -> list[CatalogueAddon]:
        with self._open(self.url) as reply:
            body = reply.read(MAX_CATALOGUE_BYTES + 1)
        if len(body) > MAX_CATALOGUE_BYTES:
            raise CatalogueError("Catalogue is too large")
        try:
            return self.parse(json.loads(body.decode("utf-8")))
        except (UnicodeError, ValueError) as exc:
            raise CatalogueError(f"Cannot read catalogue: {exc}") from exc

    def download(self, addon: CatalogueAddon, destination: str | Path) -> None:
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(
            prefix="addon-download-", suffix=".zip", dir=destination.parent
        )
        try:
            digest = hashlib.sha256()
            size = 0
            with (
                os.fdopen(fd, "wb") as out,
                self._open(addon.download_url) as reply,
            ):
                while chunk := reply.read(64 * 1024):
                    size += len(chunk)
                    if size > MAX_DOWNLOAD_BYTES:
                        raise CatalogueError("Add-on download is too large")
                    digest.update(chunk)
                    out.write(chunk)
            if digest.hexdigest() != addon.sha256:
                raise CatalogueError("Add-on checksum does not match catalogue")
            os.replace(temp, destination)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
