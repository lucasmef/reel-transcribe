from io import BytesIO
from types import SimpleNamespace
from urllib.request import Request

import pytest

from reel_transcribe.errors import DownloadError
from reel_transcribe.http import MEDIA_DOMAINS, SafeRedirectHandler, read_limited, validate_url


@pytest.mark.parametrize("url", [
    "file:///tmp/local-file.jpg",
    "http://scontent.cdninstagram.com/photo.jpg",
    "https://127.0.0.1/photo.jpg",
    "https://[::1]/photo.jpg",
    "https://169.254.169.254/latest/meta-data/",
    "https://cdninstagram.com.evil.example/photo.jpg",
    "https://evilcdninstagram.com/photo.jpg",
    "https://cdninstagram.com@evil.example/photo.jpg",
    "https://user:password@scontent.cdninstagram.com/photo.jpg",
    "https://scontent.cdninstagram.com:8443/photo.jpg",
    "https://scontent.cdninstagram.com:invalid/photo.jpg",
    "https://scontent.cdninstagram.com\n/photo.jpg",
])
def test_rejects_untrusted_media_url(url):
    with pytest.raises(DownloadError):
        validate_url(url, MEDIA_DOMAINS)


@pytest.mark.parametrize("url", [
    "https://scontent.cdninstagram.com/photo.jpg?sig=example",
    "https://scontent.xx.fbcdn.net/photo.jpg",
    "https://scontent.cdninstagram.com:443/photo.jpg",
])
def test_accepts_instagram_https_media(url):
    validate_url(url, MEDIA_DOMAINS)


@pytest.mark.parametrize("target", ["file:///tmp/test", "https://127.0.0.1/image.jpg", "http://scontent.cdninstagram.com/a.jpg"])
def test_rejects_redirect_before_request(target):
    handler = SafeRedirectHandler(MEDIA_DOMAINS)
    req = Request("https://scontent.cdninstagram.com/photo.jpg")
    with pytest.raises(DownloadError):
        handler.redirect_request(req, None, 302, "Found", {}, target)


def test_accepts_redirect_to_another_instagram_cdn():
    handler = SafeRedirectHandler(MEDIA_DOMAINS)
    req = Request("https://scontent.cdninstagram.com/photo.jpg")
    target = "https://scontent.xx.fbcdn.net/photo.jpg"
    assert handler.redirect_request(req, None, 302, "Found", {}, target).full_url == target


@pytest.mark.parametrize("headers", [{}, {"Content-Length": "1"}])
def test_rejects_oversized_body_even_with_missing_or_false_length(headers):
    response = SimpleNamespace(headers=headers, read=BytesIO(b"123456").read)
    with pytest.raises(DownloadError, match="tamanho"):
        read_limited(response, 5)


def test_rejects_large_content_length_before_reading():
    def fail_read(size):
        raise AssertionError("Should not read an oversized response")
    response = SimpleNamespace(headers={"Content-Length": "6"}, read=fail_read)
    with pytest.raises(DownloadError, match="tamanho"):
        read_limited(response, 5)


def test_reads_body_at_limit():
    response = SimpleNamespace(headers={}, read=BytesIO(b"12345").read)
    assert read_limited(response, 5) == b"12345"


def test_stops_slow_response(monkeypatch):
    times = iter([0, 61])
    monkeypatch.setattr("reel_transcribe.http.time.monotonic", lambda: next(times))
    response = SimpleNamespace(headers={}, read=BytesIO(b"12345").read)
    with pytest.raises(DownloadError, match="tempo"):
        read_limited(response, 5)
