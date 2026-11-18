import argparse
import json
import tempfile
import zipfile
from pathlib import Path

from followthelyrics.addons.catalogue import Catalogue
from followthelyrics.addons.manager import AddonManager


def validate_catalogue(path, verify_downloads=False, client=None):
    path = Path(path)
    entries = Catalogue.parse(json.loads(path.read_text(encoding="utf-8")))
    if not verify_downloads:
        return len(entries)

    client = client or Catalogue()
    with tempfile.TemporaryDirectory(prefix="ftl-catalogue-check-") as tmp:
        for entry in entries:
            destination = Path(tmp) / f"{entry.id}.zip"
            client.download(entry, destination)
            with zipfile.ZipFile(destination) as archive:
                if entry.kind != "ftl":
                    continue
                if "manifest.json" not in archive.namelist():
                    raise ValueError(f"{entry.id}: manifest.json is missing")
                manifest = AddonManager._manifest(
                    json.loads(archive.read("manifest.json"))
                )
                if manifest["id"] != entry.id:
                    raise ValueError(f"{entry.id}: manifest ID does not match")
                if manifest["version"] != entry.version:
                    raise ValueError(
                        f"{entry.id}: manifest version does not match"
                    )
                if manifest["entry"] not in archive.namelist():
                    raise ValueError(f"{entry.id}: entry file is missing")
    return len(entries)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalogue", default="addons/catalog.json")
    parser.add_argument("--check-downloads", action="store_true")
    args = parser.parse_args()
    count = validate_catalogue(args.catalogue, args.check_downloads)
    print(f"Validated {count} catalogue entries")
