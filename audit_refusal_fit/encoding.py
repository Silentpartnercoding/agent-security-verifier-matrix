"""Canonical encoding and digest helpers shared only as wire primitives."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_identifier(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value)).hexdigest()
