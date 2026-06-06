from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from .errors import InvalidReelUrlError

_REEL_PATH = re.compile(r"^/reel/([A-Za-z0-9_-]+)/?$")
_ALLOWED_HOSTS = {"instagram.com", "www.instagram.com"}


@dataclass(frozen=True)
class ReelUrl:
    url: str
    code: str


def parse_reel_url(value: str) -> ReelUrl:
    candidate = value.strip()
    parsed = urlparse(candidate)

    if parsed.scheme not in {"http", "https"} or parsed.hostname not in _ALLOWED_HOSTS:
        raise InvalidReelUrlError(
            "Informe uma URL valida de Reel, como "
            "https://www.instagram.com/reel/CODIGO/."
        )

    match = _REEL_PATH.fullmatch(parsed.path)
    if not match:
        raise InvalidReelUrlError(
            "A URL precisa apontar diretamente para um Reel publico do Instagram."
        )

    code = match.group(1)
    canonical = f"https://www.instagram.com/reel/{code}/"
    return ReelUrl(url=canonical, code=code)

