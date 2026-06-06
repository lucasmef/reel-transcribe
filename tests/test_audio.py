from pathlib import Path
from types import SimpleNamespace

import pytest

from reel_transcribe.audio import FfmpegAudioExtractor
from reel_transcribe.errors import AudioExtractionError


def test_extracts_compact_mono_mp3(monkeypatch, tmp_path: Path):
    video_path = tmp_path / "reel.mp4"
    video_path.write_bytes(b"video")
    captured = {}

    monkeypatch.setattr(
        "reel_transcribe.audio.shutil.which",
        lambda _: "C:/ffmpeg.exe",
    )

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        Path(command[-1]).write_bytes(b"audio")
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr("reel_transcribe.audio.subprocess.run", fake_run)

    result = FfmpegAudioExtractor().extract(video_path, tmp_path)

    assert result == tmp_path / "reel-audio.mp3"
    assert captured["command"] == [
        "C:/ffmpeg.exe",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-b:a",
        "64k",
        str(result),
    ]
    assert captured["kwargs"]["capture_output"] is True


def test_requires_ffmpeg(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("reel_transcribe.audio.shutil.which", lambda _: None)

    with pytest.raises(AudioExtractionError, match="ffmpeg"):
        FfmpegAudioExtractor().extract(tmp_path / "reel.mp4", tmp_path)


def test_reports_ffmpeg_failure(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "reel_transcribe.audio.shutil.which",
        lambda _: "C:/ffmpeg.exe",
    )
    monkeypatch.setattr(
        "reel_transcribe.audio.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=1,
            stderr="arquivo sem faixa de audio",
        ),
    )

    with pytest.raises(AudioExtractionError, match="sem faixa de audio"):
        FfmpegAudioExtractor().extract(tmp_path / "reel.mp4", tmp_path)
