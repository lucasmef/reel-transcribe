from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from .errors import (
    AudioExtractionError,
    GeminiError,
    GeminiProcessingError,
    MediaProcessingError,
)
from .naming import available_pair, available_video, base_name
from .urls import ReelUrl, parse_reel_url

Progress = Callable[[str], None]


class Downloader(Protocol):
    def download(
        self,
        reel: ReelUrl,
        work_dir: Path,
        progress: Progress | None = None,
    ) -> Path: ...


class Transcriber(Protocol):
    def transcribe(
        self,
        audio_path: Path,
        model: str,
        progress: Progress | None = None,
    ): ...


class AudioExtractor(Protocol):
    def extract(self, video_path: Path, work_dir: Path) -> Path: ...


@dataclass(frozen=True)
class Result:
    video_path: Path
    transcript_path: Path


def process_reel(
    url: str,
    *,
    output_dir: Path,
    model: str,
    downloader: Downloader,
    audio_extractor: AudioExtractor,
    transcriber: Transcriber,
    progress: Progress | None = None,
) -> Result:
    reel = parse_reel_url(url)
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="reel-transcribe-") as temp:
        work_dir = Path(temp)
        if progress:
            progress("Iniciando download do Reel...")
        downloaded = downloader.download(reel, work_dir, progress)

        try:
            if progress:
                progress("Extraindo audio do video...")
            audio_path = audio_extractor.extract(downloaded, work_dir)
            transcription = transcriber.transcribe(audio_path, model, progress)
        except AudioExtractionError as exc:
            preserved = _publish_video(
                downloaded,
                available_video(output_dir, base_name("")),
            )
            raise MediaProcessingError(
                f"{exc} O video foi preservado em: {preserved}",
                preserved_video=preserved,
            ) from exc
        except GeminiError as exc:
            preserved = _publish_video(
                downloaded,
                available_video(output_dir, base_name("")),
            )
            raise GeminiProcessingError(
                f"{exc} O video foi preservado em: {preserved}",
                preserved_video=preserved,
            ) from exc

        desired = base_name(transcription.first_sentence)
        video_path, transcript_path = available_pair(output_dir, desired)
        _publish_pair(
            downloaded,
            transcription.portuguese_text,
            video_path,
            transcript_path,
        )

    if progress:
        progress("Concluido.")
    return Result(video_path=video_path, transcript_path=transcript_path)


def _publish_video(source: Path, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.part")
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def _publish_pair(
    source_video: Path,
    text: str,
    video_destination: Path,
    text_destination: Path,
) -> None:
    token = uuid.uuid4().hex
    video_temp = video_destination.with_name(
        f".{video_destination.name}.{token}.part"
    )
    text_temp = text_destination.with_name(f".{text_destination.name}.{token}.part")

    try:
        shutil.copy2(source_video, video_temp)
        text_temp.write_text(text.rstrip() + "\n", encoding="utf-8")
        os.replace(video_temp, video_destination)
        try:
            os.replace(text_temp, text_destination)
        except Exception:
            video_destination.unlink(missing_ok=True)
            raise
    finally:
        video_temp.unlink(missing_ok=True)
        text_temp.unlink(missing_ok=True)
