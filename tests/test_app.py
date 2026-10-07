from pathlib import Path
from unittest.mock import patch

import pytest

from reel_transcribe.app import process_reel
from reel_transcribe.downloader import DownloadedMedia
from reel_transcribe.errors import (
    AudioExtractionError,
    DownloadError,
    GeminiError,
    GeminiProcessingError,
    MediaProcessingError,
)
from reel_transcribe.gemini import Transcription


class FakeDownloader:
    def __init__(self, error=None, media=None):
        self.error = error
        self.media = media

    def download(self, reel, work_dir, progress=None):
        if self.error:
            raise self.error
        if self.media:
            return self.media(work_dir)
        path = work_dir / "reel.mp4"
        path.write_bytes(b"video")
        return DownloadedMedia.video(path)


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


def test_image_post_is_published_to_imgs_without_transcription(tmp_path: Path):
    def media(work_dir: Path):
        image = work_dir / "image-1.jpg"
        image.write_bytes(b"image")
        return DownloadedMedia.images((image,))

    with patch("reel_transcribe.naming.date") as mocked_date:
        mocked_date.today.return_value.isoformat.return_value = "2026-06-06"
        result = process_reel(
            "https://instagram.com/p/IMG123/",
            output_dir=tmp_path,
            image_output_dir=tmp_path / "assets",
            model="model",
            downloader=FakeDownloader(media=media),
            audio_extractor=FakeAudioExtractor(
                error=AssertionError("audio extractor should not run")
            ),
            transcriber=FakeTranscriber(
                error=AssertionError("transcriber should not run")
            ),
        )

    assert result.video_path is None
    assert result.transcript_path is None
    assert [path.name for path in result.image_paths] == ["IMG123-1.jpg"]
    assert result.image_paths[0].parent == tmp_path / "assets"
    assert result.image_paths[0].read_bytes() == b"image"


def test_multiple_images_are_numbered(tmp_path: Path):
    def media(work_dir: Path):
        first = work_dir / "image-1.jpg"
        second = work_dir / "image-2.webp"
        first.write_bytes(b"first")
        second.write_bytes(b"second")
        return DownloadedMedia.images((first, second), caption="Legenda 📷\n\n#foto @autor  ")

    with patch("reel_transcribe.naming.date") as mocked_date:
        mocked_date.today.return_value.isoformat.return_value = "2026-06-06"
        result = process_reel(
            "https://instagram.com/p/IMG123/",
            output_dir=tmp_path,
            image_output_dir=tmp_path / "assets",
            model="model",
            downloader=FakeDownloader(media=media),
            audio_extractor=FakeAudioExtractor(),
            transcriber=FakeTranscriber(),
        )

    assert [path.name for path in result.image_paths] == [
        "IMG123-1.jpg",
        "IMG123-2.webp",
    ]
    assert result.caption_path == tmp_path / "assets" / "IMG123-legenda.txt"
    assert result.caption_path.read_text(encoding="utf-8") == "Legenda 📷\n\n#foto @autor  "
    assert not list((tmp_path / "assets").glob("*.part"))


def test_image_post_reuses_same_file_names_on_repeated_runs(tmp_path: Path):
    def media(work_dir: Path):
        image = work_dir / "image-1.jpg"
        image.write_bytes(b"new image")
        return DownloadedMedia.images((image,))

    image_output = tmp_path / "assets"
    existing = image_output / "IMG123-1.jpg"
    image_output.mkdir()
    existing.write_bytes(b"old image")

    result = process_reel(
        "https://instagram.com/p/IMG123/",
        output_dir=tmp_path,
        image_output_dir=image_output,
        model="model",
        downloader=FakeDownloader(media=media),
        audio_extractor=FakeAudioExtractor(),
        transcriber=FakeTranscriber(),
    )

    assert result.image_paths == (existing,)
    assert existing.read_bytes() == b"new image"
    assert not list(image_output.glob("*(*).jpg"))


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
