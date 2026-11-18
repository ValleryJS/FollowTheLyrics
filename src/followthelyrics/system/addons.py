"""Curated external add-on catalogue and local package management."""

import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from queue import Empty
from queue import Full
from queue import Queue

from followthelyrics.config import settings

CATALOGUE_URL = (
    "https://raw.githubusercontent.com/ValleryJS/FollowTheLyrics/"
    "main/addons.json"
)
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")
HASH_PATTERN = re.compile(r"^[a-fA-F0-9]{64}$")
MAX_PACKAGE_BYTES = 30 * 1024 * 1024
MAX_UNPACKED_BYTES = 100 * 1024 * 1024


def parse_catalogue(payload):
    if not isinstance(payload, dict) or not isinstance(
        payload.get("addons"), list
    ):
        return []
    valid = []
    seen = set()
    for item in payload["addons"]:
        if not isinstance(item, dict):
            continue
        addon_id = item.get("id", "")
        url = item.get("download", "")
        digest = item.get("sha256", "")
        coming_soon = item.get("status") == "coming_soon"
        if (
            not isinstance(addon_id, str)
            or not ID_PATTERN.fullmatch(addon_id)
            or addon_id in seen
            or not isinstance(item.get("name"), str)
            or not item["name"].strip()
            or not isinstance(item.get("version"), str)
            or not isinstance(url, str)
            or not isinstance(digest, str)
            or (not coming_soon and not HASH_PATTERN.fullmatch(digest))
        ):
            continue
        if not coming_soon:
            parsed = urllib.parse.urlsplit(url)
            if parsed.scheme != "https" or parsed.hostname != "github.com":
                continue
        valid.append(item)
        seen.add(addon_id)
    return valid


def fetch_catalogue(timeout=8):
    req = urllib.request.Request(
        CATALOGUE_URL, headers={"User-Agent": "FollowTheLyrics"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        payload = response.read(512 * 1024 + 1)
    if len(payload) > 512 * 1024:
        raise ValueError("Catalogue is too large")
    return parse_catalogue(json.loads(payload))


def download_package(url, timeout=20):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != "github.com":
        raise ValueError("Download must be hosted on GitHub")
    req = urllib.request.Request(url, headers={"User-Agent": "FollowTheLyrics"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        data = response.read(MAX_PACKAGE_BYTES + 1)
    if len(data) > MAX_PACKAGE_BYTES:
        raise ValueError("Add-on exceeds maximum download size")
    return data


def lyrics_event(lines):
    return {
        "type": "lyrics",
        "lines": [
            {
                "time": line.time,
                "end": line.end,
                "text": line.text,
                "singer": line.singer,
                "translation": line.translation,
                "chars": [list(pair) for pair in (line.chars or [])],
                "words": line.word_meta or {},
            }
            for line in lines
        ],
    }


class AddonManager:
    def __init__(self, data_dir=None):
        self.root = Path(data_dir or settings.DATA_DIR) / "addons"

    def installed(self):
        if not self.root.exists():
            return []
        result = []
        for folder in sorted(self.root.iterdir()):
            if not folder.is_dir() or not ID_PATTERN.fullmatch(folder.name):
                continue
            try:
                metadata = json.loads(
                    (folder / "addon.json").read_text(encoding="utf-8")
                )
                state = json.loads(
                    (folder / "state.json").read_text(encoding="utf-8")
                )
                if metadata.get("id") == folder.name:
                    result.append(
                        {**metadata, "enabled": state.get("enabled") is True}
                    )
            except (OSError, ValueError, TypeError):
                continue
        return result

    def install(self, data, expected_id, expected_sha256):
        if not ID_PATTERN.fullmatch(expected_id):
            raise ValueError("Invalid add-on ID")
        if not HASH_PATTERN.fullmatch(expected_sha256):
            raise ValueError("Invalid package checksum")
        if (
            len(data) > MAX_PACKAGE_BYTES
            or hashlib.sha256(data).hexdigest().lower()
            != expected_sha256.lower()
        ):
            raise ValueError("Add-on checksum mismatch or package too large")
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            files = archive.infolist()
            if (
                len(files) > 1000
                or sum(f.file_size for f in files) > MAX_UNPACKED_BYTES
            ):
                raise ValueError("Add-on archive is too large")
            for entry in files:
                path = Path(entry.filename)
                if (
                    path.is_absolute()
                    or ".." in path.parts
                    or "\\" in entry.filename
                    or not entry.filename
                    or (entry.external_attr >> 16) & 0o170000 == 0o120000
                ):
                    raise ValueError("Unsafe path in add-on archive")
            manifest = json.loads(archive.read("addon.json"))
            entrypoint = manifest.get("entrypoint")
            if (
                manifest.get("id") != expected_id
                or not isinstance(manifest.get("name"), str)
                or not isinstance(manifest.get("version"), str)
                or not isinstance(entrypoint, str)
                or entrypoint not in archive.namelist()
                or Path(entrypoint).is_absolute()
                or ".." in Path(entrypoint).parts
                or Path(entrypoint).suffix.lower() not in (".py", ".exe")
            ):
                raise ValueError("Invalid add-on manifest")
            self.root.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=self.root) as staging:
                stage = Path(staging)
                archive.extractall(stage)
                (stage / "state.json").write_text(
                    '{"enabled": false}', encoding="utf-8"
                )
                target = self.root / expected_id
                backup = self.root / f"_{expected_id}_backup"
                if backup.exists():
                    raise ValueError(
                        "Previous installation recovery is required"
                    )
                if target.exists():
                    target.rename(backup)
                try:
                    shutil.move(str(stage), str(target))
                except Exception:
                    if backup.exists():
                        backup.rename(target)
                    raise
                if backup.exists():
                    shutil.rmtree(backup)
        return manifest

    def set_enabled(self, addon_id, enabled):
        if not ID_PATTERN.fullmatch(addon_id):
            raise ValueError("Invalid add-on ID")
        path = self.root / addon_id / "state.json"
        if not path.exists():
            raise ValueError("Add-on is not installed")
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"enabled": bool(enabled)}), encoding="utf-8")
        os.replace(tmp, path)

    def uninstall(self, addon_id):
        if not ID_PATTERN.fullmatch(addon_id):
            raise ValueError("Invalid add-on ID")
        target = self.root / addon_id
        if target.is_dir():
            shutil.rmtree(target)


class AddonRuntime:
    """Send read-only JSON events to enabled external add-on processes."""

    def __init__(self, manager):
        self.manager = manager
        self.processes = {}
        self.queues = {}
        self.threads = {}

    def start_enabled(self):
        self.stop()
        for item in self.manager.installed():
            if not item["enabled"]:
                continue
            addon_id = item["id"]
            path = self.manager.root / addon_id
            entrypoint = path / item["entrypoint"]
            if not entrypoint.is_file() or entrypoint.is_symlink():
                continue
            if entrypoint.suffix.lower() == ".py":
                interpreter = (
                    shutil.which("python")
                    if settings.FROZEN
                    else sys.executable
                )
                if not interpreter:
                    continue
                command = [interpreter, "-u", str(entrypoint)]
            else:
                command = [str(entrypoint)]
            try:
                process = subprocess.Popen(
                    command,
                    cwd=path,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env={
                        **os.environ,
                        "FTL_ADDON_ID": addon_id,
                        "FTL_API_VERSION": "1",
                    },
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except OSError:
                continue
            pending: Queue[bytes] = Queue(maxsize=32)
            self.processes[addon_id] = process
            self.queues[addon_id] = pending
            thread = threading.Thread(
                target=self._writer, args=(process, pending), daemon=True
            )
            self.threads[addon_id] = thread
            thread.start()

    @staticmethod
    def _writer(process, pending):
        while process.poll() is None:
            try:
                data = pending.get(timeout=0.2)
            except Empty:
                continue
            try:
                process.stdin.write(data)
                process.stdin.flush()
            except (OSError, ValueError):
                break

    def publish(self, event):
        payload = (
            json.dumps(event, ensure_ascii=False, default=str) + "\n"
        ).encode("utf-8")
        for pending in self.queues.values():
            try:
                pending.put_nowait(payload)
            except Full:
                try:
                    pending.get_nowait()
                    pending.put_nowait(payload)
                except (Empty, Full):
                    pass

    def stop(self):
        for process in self.processes.values():
            if process.poll() is None:
                process.terminate()
        for process in self.processes.values():
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        self.processes.clear()
        self.queues.clear()
        self.threads.clear()
