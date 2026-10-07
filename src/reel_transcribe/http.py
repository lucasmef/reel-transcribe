"""Bounded HTTPS requests to Instagram and its media CDNs."""

from __future__ import annotations

import time
import urllib.parse
import urllib.request
from typing import Any

from .errors import DownloadError

MEDIA_DOMAINS = ("cdninstagram.com", "fbcdn.net")
API_DOMAINS = ("instagram.com",)
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_METADATA_BYTES = 5 * 1024 * 1024


def validate_url(url: str, domains: tuple[str, ...]) -> None:
    try:
        parsed = urllib.parse.urlsplit(url)
        host = parsed.hostname or ""
        valid = (
            parsed.scheme == "https"
            and parsed.username is None
            and parsed.password is None
            and parsed.port in (None, 443)
            and not any(ord(char) < 32 or ord(char) == 127 for char in url)
            and any(host == domain or host.endswith("." + domain) for domain in domains)
        )
    except ValueError:
        valid = False
    if not valid:
        raise DownloadError("URL de download recusada: use apenas HTTPS de dominios do Instagram.")


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, domains: tuple[str, ...]) -> None:
        self.domains = domains

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl, self.domains)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def safe_opener(domains: tuple[str, ...], *handlers: Any):
    return urllib.request.build_opener(SafeRedirectHandler(domains), *handlers)


def read_limited(response: Any, limit: int) -> bytes:
    length = response.headers.get("Content-Length")
    if length is not None:
        try:
            size = int(length)
        except (ValueError, TypeError) as exc:
            raise DownloadError("O servidor informou um tamanho de arquivo invalido.") from exc
        if size < 0 or size > limit:
            raise DownloadError("O download excede o tamanho permitido.")
    deadline = time.monotonic() + 60
    data = bytearray()
    while True:
        chunk = response.read(min(64 * 1024, limit + 1 - len(data)))
        data.extend(chunk)
        if len(data) > limit:
            raise DownloadError("O download excede o tamanho permitido.")
        if time.monotonic() > deadline:
            raise DownloadError("O download excedeu o tempo permitido.")
        if not chunk:
            return bytes(data)
