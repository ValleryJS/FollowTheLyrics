"""Use the host Linux CA store when the bundled OpenSSL default is absent."""

import os
import ssl
import sys
from collections.abc import MutableMapping

LINUX_CA_BUNDLES = (
    "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem",
    "/etc/pki/tls/certs/ca-bundle.crt",
    "/etc/ssl/certs/ca-certificates.crt",
    "/etc/ssl/cert.pem",
)


def configure_linux_ca_bundle(
    environ: MutableMapping[str, str] | None = None,
) -> bool:
    """Provide a system CA bundle if OpenSSL has no usable default cafile."""
    if sys.platform != "linux":
        return False
    if environ is None:
        environ = os.environ
    if "SSL_CERT_FILE" in environ or "SSL_CERT_DIR" in environ:
        return False
    if ssl.get_default_verify_paths().cafile:
        return False
    for candidate in LINUX_CA_BUNDLES:
        if os.path.isfile(candidate):
            environ["SSL_CERT_FILE"] = candidate
            return True
    return False
