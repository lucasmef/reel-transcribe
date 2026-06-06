import pytest

from reel_transcribe.errors import InvalidReelUrlError
from reel_transcribe.urls import parse_reel_url


@pytest.mark.parametrize(
    ("url", "code"),
    [
        ("https://www.instagram.com/reel/ABC_123-x/", "ABC_123-x"),
        ("https://instagram.com/reel/xyz?utm_source=test", "xyz"),
    ],
)
def test_accepts_reel_urls(url, code):
    parsed = parse_reel_url(url)
    assert parsed.code == code
    assert parsed.url == f"https://www.instagram.com/reel/{code}/"


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example/reel/ABC/",
        "https://instagram.com/p/ABC/",
        "https://instagram.com/reels/audio/ABC/",
        "not-a-url",
    ],
)
def test_rejects_invalid_urls(url):
    with pytest.raises(InvalidReelUrlError):
        parse_reel_url(url)

