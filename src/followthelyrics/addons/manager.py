"""Installed add-on lifecycle and explicit local ZIP installation."""

import importlib.util
import json
import logging
import os
import re
import shutil
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from pathlib import PurePosixPath
from types import ModuleType

logger = logging.getLogger(__name__)
ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]{1,63}\Z")
MAX_ARCHIVE_BYTES = 80 * 1024 * 1024
MAX_EXPANDED_BYTES = 160 * 1024 * 1024


class AddonError(ValueError):
    pass


@dataclass
class AddonInfo:
    id: str
    name: str
    version: str
    description: str = ""
    enabled: bool = False
    approved: bool = False
    error: str = ""


class AddonAPI:
    """Small stable surface given to third-party add-ons."""

    api_version = 1

    def __init__(self, addon_id: str):
        self.addon_id = addon_id

    def log(self, message: str) -> None:
        logger.info("Add-on %s: %s", self.addon_id, message)


class AddonManager:
    def __init__(self, data_dir: str | Path):
        self.root = Path(data_dir) / "addons"
        self.root.mkdir(parents=True, exist_ok=True)
        self.state_path = self.root / "state.json"
        self.modules: dict[str, ModuleType] = {}
        self.errors: dict[str, str] = {}
        self.state = self._read_state()
        for addon_id, state in list(self.state.items()):
            if state.get("enabled"):
                try:
                    self._load(addon_id)
                except (AddonError, OSError, Exception) as exc:
                    self.errors[addon_id] = str(exc)
                    logger.exception("Could not start add-on %s", addon_id)

    def _read_state(self) -> dict:
        try:
            value = json.loads(self.state_path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            return {}

    def _write_state(self) -> None:
        fd, temp = tempfile.mkstemp(
            prefix="state-", suffix=".json", dir=self.root
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(self.state, stream, indent=2)
            os.replace(temp, self.state_path)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)

    @staticmethod
    def _manifest(data: object) -> dict:
        if not isinstance(data, dict):
            raise AddonError("Invalid add-on manifest")
        addon_id = data.get("id")
        if not isinstance(addon_id, str) or not ID_PATTERN.fullmatch(addon_id):
            raise AddonError("Invalid add-on ID")
        if data.get("api_version") != 1:
            raise AddonError("Unsupported add-on API version")
        if not isinstance(data.get("name"), str) or not data["name"].strip():
            raise AddonError("Missing add-on name")
        if not isinstance(data.get("version"), str) or not data["version"]:
            raise AddonError("Missing add-on version")
        entry = data.get("entry")
        if not isinstance(entry, str) or not re.fullmatch(
            r"[a-zA-Z0-9_-]+\.py", entry
        ):
            raise AddonError("Invalid add-on entry file")
        return data

    def _installed_manifest(self, addon_id: str) -> dict:
        if not ID_PATTERN.fullmatch(addon_id):
            raise AddonError("Invalid add-on ID")
        path = self.root / addon_id / "manifest.json"
        try:
            return self._manifest(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError) as exc:
            raise AddonError(f"Cannot read add-on {addon_id}: {exc}") from exc

    def list_addons(self) -> list[AddonInfo]:
        items = []
        for path in sorted(self.root.iterdir()):
            if not path.is_dir() or not ID_PATTERN.fullmatch(path.name):
                continue
            try:
                manifest = self._installed_manifest(path.name)
            except AddonError:
                continue
            state = self.state.get(path.name, {})
            items.append(
                AddonInfo(
                    id=path.name,
                    name=manifest["name"],
                    version=manifest["version"],
                    description=str(manifest.get("description", "")),
                    enabled=path.name in self.modules,
                    approved=bool(state.get("approved")),
                    error=self.errors.get(path.name, ""),
                )
            )
        return items

    def install(self, archive: str | Path, approved: bool = False) -> AddonInfo:
        archive = Path(archive)
        if archive.stat().st_size > MAX_ARCHIVE_BYTES:
            raise AddonError("Add-on ZIP exceeds size limit")
        with zipfile.ZipFile(archive) as source:
            members = source.infolist()
            if (
                len(members) > 256
                or sum(i.file_size for i in members) > MAX_EXPANDED_BYTES
            ):
                raise AddonError("Add-on ZIP exceeds extraction limits")
            if "manifest.json" not in source.namelist():
                raise AddonError("ZIP must contain manifest.json at its root")
            manifest = self._manifest(json.loads(source.read("manifest.json")))
            addon_id = manifest["id"]
            target = self.root / addon_id
            if target.exists():
                raise AddonError(f"Add-on {addon_id} is already installed")
            if manifest["entry"] not in source.namelist():
                raise AddonError("Entry file is missing from the ZIP")
            for member in members:
                name = member.filename
                path = PurePosixPath(name)
                if (
                    path.is_absolute()
                    or ".." in path.parts
                    or "\\" in name
                    or ":" in name
                    or (member.external_attr >> 16) & 0o170000 == 0o120000
                ):
                    raise AddonError("ZIP contains an unsafe file path")
            temporary = Path(tempfile.mkdtemp(prefix="addon-", dir=self.root))
            try:
                source.extractall(temporary)
                temporary.rename(target)
            except Exception:
                shutil.rmtree(temporary)
                raise
        self.state[addon_id] = {"enabled": False, "approved": bool(approved)}
        self._write_state()
        return next(item for item in self.list_addons() if item.id == addon_id)

    def _load(self, addon_id: str) -> None:
        manifest = self._installed_manifest(addon_id)
        entry = self.root / addon_id / manifest["entry"]
        spec = importlib.util.spec_from_file_location(
            f"ftl_addon_{addon_id.replace('-', '_')}", entry
        )
        if spec is None or spec.loader is None:
            raise AddonError("Could not load add-on entry point")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        try:
            spec.loader.exec_module(module)
            callback = getattr(module, "on_enable", None)
            if callable(callback):
                callback(AddonAPI(addon_id))
        except Exception:
            sys.modules.pop(spec.name, None)
            raise
        self.modules[addon_id] = module

    def enable(self, addon_id: str) -> None:
        if addon_id in self.modules:
            return
        self._load(addon_id)
        self.errors.pop(addon_id, None)
        self.state.setdefault(addon_id, {})["enabled"] = True
        self._write_state()

    def disable(self, addon_id: str) -> None:
        module = self.modules.pop(addon_id, None)
        if module is not None:
            callback = getattr(module, "on_disable", None)
            if callable(callback):
                try:
                    callback()
                except Exception:
                    logger.exception(
                        "Add-on %s failed during shutdown", addon_id
                    )
            sys.modules.pop(module.__name__, None)
        self.errors.pop(addon_id, None)
        self.state.setdefault(addon_id, {})["enabled"] = False
        self._write_state()

    def uninstall(self, addon_id: str) -> None:
        self._installed_manifest(addon_id)
        self.disable(addon_id)
        shutil.rmtree(self.root / addon_id)
        self.state.pop(addon_id, None)
        self._write_state()

    def emit(self, callback_name: str, *args) -> None:
        if callback_name not in ("on_track", "on_lyrics"):
            raise AddonError("Unsupported add-on event")
        for addon_id, module in list(self.modules.items()):
            callback = getattr(module, callback_name, None)
            if callable(callback):
                try:
                    callback(*args)
                except Exception as exc:
                    self.errors[addon_id] = str(exc)
                    logger.exception(
                        "Add-on %s failed in %s", addon_id, callback_name
                    )

    def shutdown(self) -> None:
        for addon_id, module in list(self.modules.items()):
            callback = getattr(module, "on_disable", None)
            if callable(callback):
                try:
                    callback()
                except Exception:
                    logger.exception(
                        "Add-on %s failed during shutdown", addon_id
                    )
            sys.modules.pop(module.__name__, None)
        self.modules.clear()
