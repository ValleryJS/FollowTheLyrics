import hashlib
import io
import types

import pytest

from followthelyrics import version
from followthelyrics.desktop import ports
from followthelyrics.system import updater


def test_windows_helper_restarts_with_fresh_pyinstaller_environment():
    helper = updater.WINDOWS_HELPER
    restart = helper.index('Start-Process -FilePath $TargetExe')
    reset = helper.index("$env:PYINSTALLER_RESET_ENVIRONMENT = '1'")
    assert reset < restart


def test_release_workflow_can_publish_packaged_version():
    from pathlib import Path

    workflow = (Path(__file__).resolve().parents[1] / '.github/workflows/release.yml').read_text()
    assert 'if updater.is_newer(cur, new):' in workflow
    assert 'git diff --cached --quiet || git commit' in workflow


@pytest.mark.parametrize(
    ("text", "parsed"),
    [
        ("1.7.1", (1, 7, 1)),
        ("v2.0", (2, 0)),
        ("V1.2.3-beta", (1, 2, 3)),
        ("1.x", (1, 0)),
    ],
)
def test_parse_version(text, parsed):
    assert updater.parse_version(text) == parsed


@pytest.mark.parametrize(
    ("candidate", "current", "newer"),
    [
        ("1.7.2", "1.7.1", True),
        ("1.10.0", "1.9.9", True),
        ("v1.7", "1.7.0", False),
        ("1.7.0.1", "1.7", True),
        ("1.6.9", "1.7.0", False),
    ],
)
def test_is_newer(candidate, current, newer):
    assert updater.is_newer(candidate, current) is newer


def test_current_version_reads_the_packaged_file():
    assert updater.parse_version(version.current()) > (0,)


def test_current_version_can_be_faked(monkeypatch):
    monkeypatch.setenv("FTL_FAKE_VERSION", "9.9.9")

    assert version.current() == "9.9.9"


class FakeResponse(io.BytesIO):
    headers = types.MappingProxyType({})


RELEASE = ports.ReleaseFormat(
    asset="FollowTheLyrics.exe", magic=b"MZ", min_size=4
)


def _download(monkeypatch, tmp_path, payload):
    monkeypatch.setattr(
        updater.urllib.request,
        "urlopen",
        lambda *_a, **_k: FakeResponse(payload),
    )
    info = {
        "url": updater.DOWNLOAD_PREFIX + "v9/FollowTheLyrics.exe",
        "size": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    dest = tmp_path / "new.exe"
    updater.download(info, str(dest), RELEASE)
    return dest


def test_download_accepts_a_release_with_the_expected_header(
    monkeypatch, tmp_path
):
    dest = _download(monkeypatch, tmp_path, b"MZ" + b"\0" * 10)

    assert dest.read_bytes().startswith(b"MZ")


def test_download_rejects_a_file_without_the_release_header(
    monkeypatch, tmp_path
):
    with pytest.raises(ValueError, match="programme valide"):
        _download(monkeypatch, tmp_path, b"<html>" + b"\0" * 10)
