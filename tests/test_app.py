from pathlib import Path
from unittest.mock import patch

import pytest

from reel_transcribe.app import process_reel
from reel_transcribe.errors import (
    AudioExtractionError,
    DownloadError,
    GeminiError,
    GeminiProcessingError,
    MediaProcessingError,
)
from reel_transcribe.gemini import Transcription


class FakeDownloader:
    def __init__(self, error=None):
        self.error = error

    def download(self, reel, work_dir, progress=None):
        if self.error:
            raise self.error
        path = work_dir / "reel.mp4"
        path.write_bytes(b"video")
        return path


class FakeTranscriber:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error

    def transcribe(self, video_path, model, progress=None):
        assert video_path.name == "reel-audio.mp3"
        if self.error:
            raise self.error
        return self.result


class FakeAudioExtractor:
    def __init__(self, error=None):
        self.error = error

    def extract(self, video_path, work_dir):
        if self.error:
            raise self.error
        path = work_dir / "reel-audio.mp3"
        path.write_bytes(b"audio")
        return path


def test_full_flow_publishes_matching_files(tmp_path: Path):
    transcription = Transcription(
        detected_language="portugues",
        first_sentence="Esta e a primeira frase.",
        portuguese_text="Esta e a primeira frase.\n\nTexto integral.",
    )

    with patch("reel_transcribe.naming.date") as mocked_date:
        mocked_date.today.return_value.isoformat.return_value = "2026-06-06"
        result = process_reel(
            "https://instagram.com/reel/ABC/",
            output_dir=tmp_path,
            model="gemini-3.5-flash",
            downloader=FakeDownloader(),
            audio_extractor=FakeAudioExtractor(),
            transcriber=FakeTranscriber(result=transcription),
        )

    assert result.video_path.name == "2026-06-06-Esta e a primeira frase.mp4"
    assert result.transcript_path.name == "2026-06-06-Esta e a primeira frase.txt"
    assert result.video_path.read_bytes() == b"video"
    assert result.transcript_path.read_text(encoding="utf-8") == (
        "Esta e a primeira frase.\n\nTexto integral.\n"
    )
    assert not list(tmp_path.glob("*.part"))


def test_preserves_video_with_fallback_name_on_gemini_failure(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setattr(
        "reel_transcribe.app.base_name",
        lambda _: "2026-06-06-reel",
    )
    with pytest.raises(GeminiProcessingError) as caught:
        process_reel(
            "https://instagram.com/reel/FAIL/",
            output_dir=tmp_path,
            model="model",
            downloader=FakeDownloader(),
            audio_extractor=FakeAudioExtractor(),
            transcriber=FakeTranscriber(error=GeminiError("API indisponivel.")),
        )

    assert caught.value.preserved_video == tmp_path / "2026-06-06-reel.mp4"
    assert caught.value.preserved_video.read_bytes() == b"video"
    assert not list(tmp_path.glob("*.txt"))


def test_download_failure_does_not_publish_files(tmp_path: Path):
    with pytest.raises(DownloadError):
        process_reel(
            "https://instagram.com/reel/FAIL/",
            output_dir=tmp_path,
            model="model",
            downloader=FakeDownloader(error=DownloadError("privado")),
            audio_extractor=FakeAudioExtractor(),
            transcriber=FakeTranscriber(),
        )
    assert not list(tmp_path.iterdir())


def test_preserves_video_when_audio_extraction_fails(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "reel_transcribe.app.base_name",
        lambda _: "2026-06-06-reel",
    )
    with pytest.raises(MediaProcessingError) as caught:
        process_reel(
            "https://instagram.com/reel/FAIL/",
            output_dir=tmp_path,
            model="model",
            downloader=FakeDownloader(),
            audio_extractor=FakeAudioExtractor(
                error=AudioExtractionError("ffmpeg falhou.")
            ),
            transcriber=FakeTranscriber(),
        )

    assert caught.value.preserved_video == tmp_path / "2026-06-06-reel.mp4"
    assert caught.value.preserved_video.read_bytes() == b"video"
