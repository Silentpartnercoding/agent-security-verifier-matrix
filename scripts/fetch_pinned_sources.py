#!/usr/bin/env python3
"""Fetch every AIP source pin explicitly and verify it before installation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = ROOT / "sources.json"
DEFAULT_DESTINATION = ROOT / "vendor" / "sources"
MAX_SOURCE_BYTES = 20_000_000
COMMIT_RE = re.compile(r"[0-9a-f]{40}")


class FetchError(RuntimeError):
    """A source could not be resolved, fetched, or matched to its pin."""


def _source_url(pin: dict[str, Any]) -> str:
    source_url = pin.get("url")
    if source_url is not None:
        parsed = urllib.parse.urlparse(source_url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise FetchError(f"{pin.get('id', '<unknown>')}: source URL must use HTTPS")
        return source_url

    repository = pin.get("repository")
    commit = pin.get("commit")
    source_path = pin.get("path")
    if not isinstance(repository, str) or not repository.startswith("https://github.com/"):
        raise FetchError(f"{pin.get('id', '<unknown>')}: unsupported repository URL")
    if not isinstance(commit, str) or COMMIT_RE.fullmatch(commit) is None:
        raise FetchError(f"{pin.get('id', '<unknown>')}: git source needs a full commit pin")
    if not isinstance(source_path, str):
        raise FetchError(f"{pin.get('id', '<unknown>')}: git source needs a path")
    path = Path(source_path)
    if path.is_absolute() or ".." in path.parts:
        raise FetchError(f"{pin.get('id', '<unknown>')}: unsafe source path")

    repository_path = repository.removeprefix("https://github.com/").removesuffix(".git")
    repository_parts = repository_path.split("/")
    if len(repository_parts) != 2 or not all(repository_parts):
        raise FetchError(f"{pin.get('id', '<unknown>')}: unsupported repository URL")
    quoted = "/".join(
        urllib.parse.quote(part, safe="")
        for part in [*repository_parts, commit, *path.parts]
    )
    return f"https://raw.githubusercontent.com/{quoted}"


def _download(url: str, opener: Callable[..., Any]) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "aip-matrix-fit-fetch/1"})
    with opener(request, timeout=30) as response:
        data = response.read(MAX_SOURCE_BYTES + 1)
    if len(data) > MAX_SOURCE_BYTES:
        raise FetchError(f"source exceeds {MAX_SOURCE_BYTES} bytes")
    return data


def _verify(pin: dict[str, Any], data: bytes) -> None:
    source_id = pin.get("id", "<unknown>")
    expected_bytes = pin.get("bytes")
    if expected_bytes is not None and len(data) != expected_bytes:
        raise FetchError(
            f"{source_id}: byte count mismatch: expected {expected_bytes}, got {len(data)}"
        )
    expected_sha256 = pin.get("sha256")
    observed_sha256 = hashlib.sha256(data).hexdigest()
    if observed_sha256 != expected_sha256:
        raise FetchError(
            f"{source_id}: sha256 mismatch: expected {expected_sha256}, got {observed_sha256}"
        )


def fetch_all(
    manifest_path: Path,
    destination: Path,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> list[Path]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    pins = manifest.get("sources")
    if not isinstance(pins, list) or not pins:
        raise FetchError("sources manifest must contain a non-empty sources list")

    destination.parent.mkdir(parents=True, exist_ok=True)
    installed: list[Path] = []
    with tempfile.TemporaryDirectory(prefix=".aip-sources-", dir=destination.parent) as staging:
        staging_path = Path(staging)
        for pin in pins:
            if not isinstance(pin, dict) or not isinstance(pin.get("id"), str):
                raise FetchError("every source pin must have a string id")
            source_id = pin["id"]
            if Path(source_id).name != source_id:
                raise FetchError(f"{source_id}: unsafe source id")
            data = _download(_source_url(pin), opener)
            _verify(pin, data)
            (staging_path / source_id).write_bytes(data)

        destination.mkdir(parents=True, exist_ok=True)
        for pin in pins:
            target = destination / pin["id"]
            os.replace(staging_path / pin["id"], target)
            installed.append(target)
    return installed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch and verify all source bytes pinned by AIP-MATRIX-FIT-002"
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--destination", type=Path, default=DEFAULT_DESTINATION)
    args = parser.parse_args()
    try:
        installed = fetch_all(args.manifest, args.destination)
    except (FetchError, OSError, json.JSONDecodeError) as error:
        print(f"fetch failed: {error}", file=sys.stderr)
        return 1
    for path in installed:
        print(f"verified {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
