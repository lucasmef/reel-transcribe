from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from .errors import InvalidReelUrlError

_MEDIA_PATH = re.compile(
    r"^/(?:[A-Za-z0-9_.]+/)?(reel|p)/([A-Za-z0-9_-]+)/?$"
)
_ALLOWED_HOSTS = {"instagram.com", "www.instagram.com"}


@dataclass(frozen=True)
class ReelUrl:
    url: str
    code: str
    kind: str = "reel"


def parse_reel_url(value: str) -> ReelUrl:
    candidate = value.strip()
    parsed = urlparse(candidate)

    if parsed.scheme not in {"http", "https"} or parsed.hostname not in _ALLOWED_HOSTS:
        raise InvalidReelUrlError(
            "Informe uma URL valida do Instagram, como "
            "https://www.instagram.com/reel/CODIGO/ ou "
            "https://www.instagram.com/p/CODIGO/."
        )

    match = _MEDIA_PATH.fullmatch(parsed.path)
    if not match:
        raise InvalidReelUrlError(
            "A URL precisa apontar diretamente para um Reel ou post publico do "
            "Instagram."
        )

    kind, code = match.groups()
    canonical = f"https://www.instagram.com/{kind}/{code}/"
    return ReelUrl(url=canonical, code=code, kind=kind)
