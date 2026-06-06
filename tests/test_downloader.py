import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from reel_transcribe.downloader import ReelDownloader
from reel_transcribe.errors import DownloadError
from reel_transcribe.urls import ReelUrl


def fake_ytdlp(monkeypatch, *, extension="mp4", error=None):
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

    assert result == tmp_path / "reel.mp4"
    assert captured["format"] == "best[ext=mp4]/best"


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

    assert captured["format"] == "bestvideo*+bestaudio/best"


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

    with pytest.raises(DownloadError, match="somente Reels publicos"):
        ReelDownloader().download(
            ReelUrl("https://instagram.com/reel/ABC/", "ABC"),
            tmp_path,
        )
