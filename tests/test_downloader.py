import sys
from io import BytesIO
import json
from http.cookiejar import CookieJar
from pathlib import Path
from types import SimpleNamespace

import pytest

from reel_transcribe.downloader import ReelDownloader
from reel_transcribe.errors import DownloadError
from reel_transcribe.urls import ReelUrl


def fake_ytdlp(monkeypatch, *, extension="mp4", error=None, info=None):
    captured = {}

    class FakeYoutubeDL:
        def __init__(self, options):
            captured.update(options)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def download(self, urls):
            if error:
                raise RuntimeError(error)
            output = Path(captured["outtmpl"].replace("%(ext)s", extension))
            output.write_bytes(b"video")

        def extract_info(self, url, download=False):
            if error:
                raise RuntimeError(error)
            return info

    monkeypatch.setitem(
        sys.modules,
        "yt_dlp",
        SimpleNamespace(YoutubeDL=FakeYoutubeDL),
    )
    return captured


def test_downloads_combined_mp4_without_ffmpeg(monkeypatch, tmp_path: Path):
    captured = fake_ytdlp(monkeypatch)
    monkeypatch.setattr("reel_transcribe.downloader.shutil.which", lambda _: None)

    result = ReelDownloader().download(
        ReelUrl("https://instagram.com/reel/ABC/", "ABC"),
        tmp_path,
    )

    assert result.kind == "video"
    assert result.paths == (tmp_path / "reel.mp4",)
    assert captured["format"] == "best[ext=mp4][vcodec^=avc1]/best[ext=mp4]/best"
    assert "cookiesfrombrowser" not in captured


def test_browser_session_is_only_used_when_requested(monkeypatch, tmp_path):
    captured = fake_ytdlp(monkeypatch)
    ReelDownloader(cookies_from_browser="safari").download(
        ReelUrl("https://instagram.com/reel/ABC/", "ABC"), tmp_path
    )
    assert captured["cookiesfrombrowser"] == ("safari", None, None, None)


@pytest.mark.parametrize("browser", [None, "safari"])
def test_api_fallback_respects_cookie_choice(monkeypatch, browser):
    reads = []
    def extract(name):
        reads.append(name)
        return CookieJar()
    monkeypatch.setitem(sys.modules, "yt_dlp.cookies", SimpleNamespace(extract_cookies_from_browser=extract))
    class Response:
        headers = {"Content-Type": "application/json"}
        def __init__(self):
            self.body = BytesIO(json.dumps({"items": [{"media_type": 1}]}).encode())
        def read(self, size):
            return self.body.read(size)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
    monkeypatch.setattr("reel_transcribe.downloader.safe_opener", lambda *a: SimpleNamespace(open=lambda *a, **k: Response()))
    ReelDownloader(cookies_from_browser=browser)._instagram_api_images(
        ReelUrl("https://instagram.com/p/ABC/", "ABC", "p")
    )
    assert reads == ([browser] if browser else [])


def test_image_download_rejects_local_files_without_network(monkeypatch, tmp_path):
    source = tmp_path / "private.txt"
    source.write_text("harmless audit marker")
    def fail_open(*args):
        raise AssertionError("Network must not be used")
    monkeypatch.setattr("reel_transcribe.downloader.safe_opener", fail_open)
    with pytest.raises(DownloadError, match="URL"):
        ReelDownloader._download_image_url(source.as_uri(), tmp_path / "image-1")
    assert not (tmp_path / "image-1.jpg").exists()


def test_image_download_rejects_html_disguised_as_jpeg(monkeypatch, tmp_path):
    class Response:
        headers = {"Content-Type": "text/html"}
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self, size):
            raise AssertionError("Should reject before downloading HTML")
    monkeypatch.setattr("reel_transcribe.downloader.safe_opener", lambda *a: SimpleNamespace(open=lambda *a, **k: Response()))
    with pytest.raises(DownloadError, match="tipo de imagem"):
        ReelDownloader._download_image_url("https://scontent.cdninstagram.com/photo.jpg", tmp_path / "image-1")
    assert not list(tmp_path.iterdir())


def test_uses_separate_streams_when_ffmpeg_exists(monkeypatch, tmp_path: Path):
    captured = fake_ytdlp(monkeypatch)
    monkeypatch.setattr(
        "reel_transcribe.downloader.shutil.which",
        lambda _: "C:/ffmpeg.exe",
    )

    ReelDownloader().download(
        ReelUrl("https://instagram.com/reel/ABC/", "ABC"),
        tmp_path,
    )

    assert captured["format"].startswith("bestvideo[ext=mp4][vcodec^=avc1]+")


def test_rejects_non_mp4_result(monkeypatch, tmp_path: Path):
    fake_ytdlp(monkeypatch, extension="webm")
    monkeypatch.setattr("reel_transcribe.downloader.shutil.which", lambda _: None)

    with pytest.raises(DownloadError, match="ffmpeg"):
        ReelDownloader().download(
            ReelUrl("https://instagram.com/reel/ABC/", "ABC"),
            tmp_path,
        )


def test_explains_private_reel_error(monkeypatch, tmp_path: Path):
    fake_ytdlp(monkeypatch, error="Login required: private video")
    monkeypatch.setattr("reel_transcribe.downloader.shutil.which", lambda _: None)

    with pytest.raises(DownloadError, match="links publicos"):
        ReelDownloader().download(
            ReelUrl("https://instagram.com/reel/ABC/", "ABC"),
            tmp_path,
        )


def test_downloads_image_post_from_thumbnail(monkeypatch, tmp_path: Path):
    fake_ytdlp(
        monkeypatch,
        info={
            "description": "Legenda original 📷\n#fotos",
            "entries": [
                {
                    "thumbnails": [
                        {
                            "url": "https://scontent.cdninstagram.com/small.jpg",
                            "width": 100,
                            "height": 100,
                        },
                        {
                            "url": "https://scontent.cdninstagram.com/large.jpg",
                            "width": 1000,
                            "height": 1000,
                        },
                    ]
                }
            ]
        },
    )

    class FakeResponse:
        headers = {"Content-Type": "image/jpeg"}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def __init__(self):
            self.body = BytesIO(b"image")

        def read(self, size=-1):
            return self.body.read(size)

    requested = {}

    def fake_urlopen(request, timeout):
        requested["url"] = request.full_url
        requested["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("reel_transcribe.downloader.safe_opener", lambda *args: SimpleNamespace(open=fake_urlopen))

    result = ReelDownloader().download(
        ReelUrl("https://instagram.com/p/ABC/", "ABC", "p"),
        tmp_path,
    )

    assert requested == {
        "url": "https://scontent.cdninstagram.com/large.jpg",
        "timeout": 30,
    }
    assert result.kind == "image"
    assert result.paths == (tmp_path / "image-1.jpg",)
    assert result.paths[0].read_bytes() == b"image"
    assert result.caption == "Legenda original 📷\n#fotos"


def test_downloads_all_images_from_instagram_api_fallback(monkeypatch, tmp_path: Path):
    fake_ytdlp(monkeypatch, info={"entries": [{"formats": []}]})

    monkeypatch.setattr(
        ReelDownloader,
        "_instagram_api_images",
        classmethod(
            lambda cls, reel: (
                ("https://scontent.cdninstagram.com/first.jpg", "https://scontent.cdninstagram.com/second.jpg"),
                "Legenda do carrossel",
            )
        ),
    )

    class FakeResponse:
        headers = {"Content-Type": "image/jpeg"}

        def __init__(self, body):
            self._body = BytesIO(body)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self, size=-1):
            return self._body.read(size)

    def fake_urlopen(request, timeout):
        return FakeResponse(request.full_url.encode("utf-8"))

    monkeypatch.setattr("reel_transcribe.downloader.safe_opener", lambda *args: SimpleNamespace(open=fake_urlopen))

    result = ReelDownloader().download(
        ReelUrl("https://instagram.com/p/ABC/", "ABC", "p"),
        tmp_path,
    )

    assert result.kind == "image"
    assert [path.name for path in result.paths] == ["image-1.jpg", "image-2.jpg"]
    assert result.paths[0].read_bytes() == b"https://scontent.cdninstagram.com/first.jpg"
    assert result.paths[1].read_bytes() == b"https://scontent.cdninstagram.com/second.jpg"
    assert result.caption == "Legenda do carrossel"


def test_api_carousel_preserves_order_caption_and_skips_video_covers():
    def photo(url, **extra):
        return {
            "image_versions2": {"candidates": [
                {"url": "https://scontent.cdninstagram.com/small.jpg", "width": 100, "height": 100},
                {"url": url, "width": 1080, "height": 1350},
            ]},
            **extra,
        }

    urls, caption = ReelDownloader._images_from_api_item({
        "caption": {"text": "Original 🌎\n\n@autor #tag"},
        "carousel_media": [
            photo("https://scontent.cdninstagram.com/1.jpg", media_type=1),
            photo("https://scontent.cdninstagram.com/video.jpg", media_type=2),
            photo("https://scontent.cdninstagram.com/2.jpg", media_type=1),
        ],
    })
    assert urls == ("https://scontent.cdninstagram.com/1.jpg", "https://scontent.cdninstagram.com/2.jpg")
    assert caption == "Original 🌎\n\n@autor #tag"


def test_api_post_without_caption_returns_empty_text():
    assert ReelDownloader._images_from_api_item({"media_type": 1}) == ((), "")


def test_caption_can_come_from_playlist_entry():
    assert ReelDownloader._caption({"entries": [{"description": "Texto"}]}) == "Texto"


def test_caption_lookup_failure_does_not_lose_available_photos(monkeypatch, tmp_path):
    fake_ytdlp(monkeypatch, info={"url": "https://scontent.cdninstagram.com/photo.jpg"})

    def fail(cls, reel):
        raise DownloadError("Instagram indisponivel")

    monkeypatch.setattr(ReelDownloader, "_instagram_api_images", classmethod(fail))

    def download(url, base):
        path = base.with_suffix(".jpg")
        path.write_bytes(b"photo")
        return path

    monkeypatch.setattr(ReelDownloader, "_download_image_url", staticmethod(download))
    messages = []
    result = ReelDownloader().download(
        ReelUrl("https://instagram.com/p/ABC/", "ABC", "p"), tmp_path, messages.append
    )
    assert len(result.paths) == 1
    assert result.caption is None
    assert any("legenda" in message for message in messages)
