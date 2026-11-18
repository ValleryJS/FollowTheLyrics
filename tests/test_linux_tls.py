from types import SimpleNamespace

from followthelyrics.system import tls


def test_fedora_trust_store_selected_without_default_bundle(monkeypatch):
    env = {}
    monkeypatch.setattr(tls.sys, "platform", "linux")
    monkeypatch.setattr(
        tls.ssl,
        "get_default_verify_paths",
        lambda: SimpleNamespace(cafile=None),
    )
    monkeypatch.setattr(
        tls.os.path,
        "isfile",
        lambda path: path == (
            "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem"
        ),
    )
    assert tls.configure_linux_ca_bundle(env) is True
    assert env["SSL_CERT_FILE"] == (
        "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem"
    )


def test_explicit_certificate_override_is_preserved(monkeypatch):
    env = {"SSL_CERT_FILE": "/custom/company-roots.pem"}
    monkeypatch.setattr(tls.sys, "platform", "linux")
    assert tls.configure_linux_ca_bundle(env) is False
    assert env["SSL_CERT_FILE"] == "/custom/company-roots.pem"


def test_ubuntu_default_bundle_is_not_overridden(monkeypatch):
    env = {}
    monkeypatch.setattr(tls.sys, "platform", "linux")
    monkeypatch.setattr(
        tls.ssl,
        "get_default_verify_paths",
        lambda: SimpleNamespace(cafile="/etc/ssl/certs/ca-certificates.crt"),
    )
    assert tls.configure_linux_ca_bundle(env) is False
    assert "SSL_CERT_FILE" not in env


def test_windows_does_not_use_linux_ca_paths(monkeypatch):
    env = {}
    monkeypatch.setattr(tls.sys, "platform", "win32")
    assert tls.configure_linux_ca_bundle(env) is False
    assert "SSL_CERT_FILE" not in env
