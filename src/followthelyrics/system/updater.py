import hashlib
import json
import logging
import os
import subprocess
import sys
import tempfile
import urllib.request

from PyQt6.QtCore import QThread
from PyQt6.QtCore import pyqtSignal

from followthelyrics import i18n
from followthelyrics import version
from followthelyrics.config import settings
from followthelyrics.system import startup

logger = logging.getLogger(__name__)

API_URL = f"https://api.github.com/repos/{version.REPO}/releases/latest"
RELEASES_URL = f"https://github.com/{version.REPO}/releases/latest"
DOWNLOAD_PREFIX = f"https://github.com/{version.REPO}/releases/download/"
USER_AGENT = "FollowTheLyrics-updater"


def parse_version(text):
    out = []
    for part in str(text).strip().lstrip("vV").split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        out.append(int(digits) if digits else 0)
    return tuple(out)


def is_newer(candidate, current):
    a, b = parse_version(candidate), parse_version(current)
    n = max(len(a), len(b))
    return a + (0,) * (n - len(a)) > b + (0,) * (n - len(b))


def repo_configured():
    return "YOUR_GITHUB_USERNAME" not in version.REPO and version.REPO.count("/") == 1


def fetch_latest(asset_name, timeout=8):
    if not repo_configured():
        return None

    api = os.environ.get("FTL_UPDATE_API") or API_URL
    if not api.startswith(f"https://api.github.com/repos/{version.REPO}/"):
        api = API_URL
    req = urllib.request.Request(
        api,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8"))
    for asset in data.get("assets", []):
        url = asset.get("browser_download_url", "")
        if asset.get("name") == asset_name and url.startswith(DOWNLOAD_PREFIX):
            digest = asset.get("digest") or ""
            return {
                "version": str(data.get("tag_name", "")).lstrip("vV"),
                "url": url,
                "size": int(asset.get("size") or 0),
                "sha256": digest.split(":", 1)[1].lower()
                if digest.startswith("sha256:")
                else "",
                "notes": (data.get("body") or "").strip(),
            }
    return None


def download(info, dest, release, progress=None, timeout=20):
    if not info["url"].startswith(DOWNLOAD_PREFIX):
        raise ValueError("adresse de telechargement inattendue")
    req = urllib.request.Request(
        info["url"], headers={"User-Agent": USER_AGENT}
    )
    sha = hashlib.sha256()
    done = 0
    with (
        urllib.request.urlopen(req, timeout=timeout) as r,
        open(dest, "wb") as f,
    ):
        total = info["size"] or int(r.headers.get("Content-Length") or 0)
        while True:
            chunk = r.read(256 * 1024)
            if not chunk:
                break
            f.write(chunk)
            sha.update(chunk)
            done += len(chunk)
            if progress and total:
                progress(min(1.0, done / total))
    with open(dest, "rb") as f:
        head = f.read(len(release.magic))
    if head != release.magic or done < release.min_size:
        raise ValueError("le fichier telecharge n'est pas un programme valide")
    if info["size"] and done != info["size"]:
        raise ValueError("telechargement incomplet")
    if info["sha256"] and sha.hexdigest() != info["sha256"]:
        raise ValueError(
            "le fichier telecharge ne correspond pas a celui publie"
        )


def swap(exe, new):
    old = exe + ".old"
    if os.path.exists(old):
        os.remove(old)
    os.chmod(new, os.stat(exe).st_mode)
    os.replace(exe, old)
    try:
        os.replace(new, exe)
    except Exception:
        os.replace(old, exe)
        raise


def relaunch(session, exe, new_version):
    session.spawn_detached(
        [exe, "--updated", new_version],
        os.path.dirname(exe),
        startup.child_environment(drop=("FTL_FAKE_VERSION",)),
    )


def cleanup_leftovers():
    if not settings.FROZEN:
        return True
    ok = True
    for suffix in (".old", ".new"):
        path = sys.executable + suffix
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                ok = False
    return ok




WINDOWS_HELPER = r'''param(
    [string]$TargetExe,
    [string]$NewExe,
    [int]$ParentPid,
    [string]$InstalledVersion
)
$ErrorActionPreference = 'Stop'
$backup = "$TargetExe.old"
try {
    try { Wait-Process -Id $ParentPid -Timeout 90 -ErrorAction Stop }
    catch { if (Get-Process -Id $ParentPid -ErrorAction SilentlyContinue) { throw 'Application did not exit in time' } }
    $complete = $false
    for ($attempt = 0; $attempt -lt 25; $attempt++) {
        try {
            if (Test-Path -LiteralPath $backup) { Remove-Item -LiteralPath $backup -Force }
            Move-Item -LiteralPath $TargetExe -Destination $backup -Force
            try {
                Move-Item -LiteralPath $NewExe -Destination $TargetExe -Force
                $complete = $true
                break
            } catch {
                Move-Item -LiteralPath $backup -Destination $TargetExe -Force
                throw
            }
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
    if (-not $complete) { throw 'Cannot replace the application executable' }
    # Restart as a new PyInstaller onefile process, never as a worker that
    # reuses the previous process's deleted _MEI extraction directory.
    $env:PYINSTALLER_RESET_ENVIRONMENT = '1'
    Start-Process -FilePath $TargetExe -ArgumentList @('--updated', $InstalledVersion) -WorkingDirectory (Split-Path -Parent $TargetExe)
    # Keep backup for the application to remove on its next startup.
} catch {
    Add-Content -LiteralPath (Join-Path $env:TEMP 'FollowTheLyrics-update-error.log') -Value "$(Get-Date -Format o) $_"
    if (-not (Test-Path -LiteralPath $TargetExe) -and (Test-Path -LiteralPath $backup)) {
        Move-Item -LiteralPath $backup -Destination $TargetExe -Force
    }
    exit 1
}
'''


def apply_windows_update(exe, new, installed_version):
    """Launch a separate updater, then the caller must exit the GUI process."""
    if sys.platform != "win32":
        raise RuntimeError("Windows updater only")
    if not os.path.isfile(new):
        raise FileNotFoundError(new)
    helper_dir = tempfile.mkdtemp(prefix="ftl-update-")
    helper_path = os.path.join(helper_dir, "apply.ps1")
    with open(helper_path, "w", encoding="utf-8-sig") as file:
        file.write(WINDOWS_HELPER)
    # No shell interpolation: executable paths and version are positional args.
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.Popen(
        [
            "powershell.exe", "-NoProfile", "-NonInteractive",
            "-ExecutionPolicy", "Bypass", "-File", helper_path,
            "-TargetExe", exe, "-NewExe", new,
            "-ParentPid", str(os.getpid()),
            "-InstalledVersion", installed_version,
        ],
        creationflags=flags,
        close_fds=True,
    )


class UpdateCheck(QThread):
    found = pyqtSignal(dict)
    nothing = pyqtSignal(bool)

    def __init__(self, release):
        super().__init__()
        self.release = release

    def run(self):
        try:
            info = fetch_latest(self.release.asset)
            if (
                info
                and info["version"]
                and is_newer(info["version"], version.current())
            ):
                self.found.emit(info)
            else:
                self.nothing.emit(False)
        except Exception:
            logger.warning("run failed", exc_info=True)
            self.nothing.emit(True)


class UpdateInstall(QThread):
    progress = pyqtSignal(float)
    failed = pyqtSignal(str)
    installed = pyqtSignal(str)

    def __init__(self, info, release):
        super().__init__()
        self.info = info
        self.release = release

    def run(self):
        exe = sys.executable
        new = exe + ".new"
        try:
            download(self.info, new, self.release, self.progress.emit)
            if sys.platform != "win32":
                swap(exe, new)
        except PermissionError:
            self._clean(new)
            self.failed.emit(
                i18n.tr(
                    "Impossible d'écrire dans le dossier du programme. Déplace "
                    "{} dans un dossier à toi (Bureau, Documents…) puis "
                    "réessaie."
                ).format(self.release.asset)
            )
            return
        except Exception as e:
            logger.warning("run failed", exc_info=True)
            self._clean(new)
            self.failed.emit(
                i18n.tr(
                    "La mise à jour a échoué ({}). Réessaie plus tard."
                ).format(e)
            )
            return
        self.installed.emit(self.info["version"])

    @staticmethod
    def _clean(path):
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass
