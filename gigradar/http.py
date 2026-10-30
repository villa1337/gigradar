"""Tiny stdlib-only HTTP helper.

We deliberately avoid ``requests`` to keep GigRadar dependency-free and truly
click-and-run. ``urllib`` with a sane User-Agent and timeout is all we need.
"""

from __future__ import annotations

import gzip
import json
import urllib.error
import urllib.request
from typing import Any

# Some public APIs (RemoteOK, Reddit) reject requests without a UA.
USER_AGENT = "GigRadar/1.0 (+https://github.com/villa1337/gigradar)"
DEFAULT_TIMEOUT = 20


def _open(url: str, timeout: int = DEFAULT_TIMEOUT) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Encoding": "gzip",
            "Accept": "application/json, text/xml, */*",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        if resp.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        return raw


def get_text(url: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    """GET a URL and return decoded text. Raises on network error."""
    return _open(url, timeout).decode("utf-8", errors="replace")


def get_json(url: str, timeout: int = DEFAULT_TIMEOUT) -> Any:
    """GET a URL and parse JSON."""
    return json.loads(get_text(url, timeout))
