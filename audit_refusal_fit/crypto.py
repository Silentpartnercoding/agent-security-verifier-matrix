"""Small OpenSSL adapter for the experiment's frozen Ed25519 test vectors."""

from __future__ import annotations

import base64
import subprocess
import tempfile
from pathlib import Path


class CryptoError(RuntimeError):
    """The test-vector signer or verifier could not run."""


def sign_ed25519(payload: bytes, private_key: Path) -> str:
    with tempfile.NamedTemporaryFile(prefix="audit-refusal-payload-") as payload_file:
        payload_file.write(payload)
        payload_file.flush()
        completed = subprocess.run(
            [
                "openssl",
                "pkeyutl",
                "-sign",
                "-rawin",
                "-inkey",
                str(private_key),
                "-in",
                payload_file.name,
            ],
            capture_output=True,
            check=False,
        )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise CryptoError(f"OpenSSL Ed25519 signing failed: {detail}")
    encoded = base64.urlsafe_b64encode(completed.stdout).rstrip(b"=").decode("ascii")
    return f"ed25519:{encoded}"


def verify_ed25519(payload: bytes, signature: str, public_key: Path) -> bool:
    prefix, separator, encoded = signature.partition(":")
    if not separator or prefix != "ed25519" or not encoded:
        return False
    try:
        raw_signature = base64.urlsafe_b64decode(
            encoded + "=" * (-len(encoded) % 4)
        )
    except (ValueError, UnicodeEncodeError):
        return False

    with tempfile.NamedTemporaryFile(prefix="audit-refusal-payload-") as payload_file, tempfile.NamedTemporaryFile(
        prefix="audit-refusal-signature-"
    ) as signature_file:
        payload_file.write(payload)
        payload_file.flush()
        signature_file.write(raw_signature)
        signature_file.flush()
        completed = subprocess.run(
            [
                "openssl",
                "pkeyutl",
                "-verify",
                "-pubin",
                "-rawin",
                "-inkey",
                str(public_key),
                "-in",
                payload_file.name,
                "-sigfile",
                signature_file.name,
            ],
            capture_output=True,
            check=False,
        )
    return completed.returncode == 0
