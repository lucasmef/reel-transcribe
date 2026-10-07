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
from .downloader import DownloadedMedia
from .naming import (
    available_pair,
    available_video,
    base_name,
    image_base_name,
)
from .urls import ReelUrl, parse_reel_url

Progress = Callable[[str], None]


class Downloader(Protocol):
    def download(
        self,
        reel: ReelUrl,
        work_dir: Path,
        progress: Progress | None = None,
    ) -> DownloadedMedia: ...


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
    video_path: Path | None = None
    transcript_path: Path | None = None
    image_paths: tuple[Path, ...] = ()
    caption_path: Path | None = None


def process_reel(
    url: str,
    *,
    output_dir: Path,
    image_output_dir: Path | None = None,
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
            progress("Iniciando download do Instagram...")
        downloaded = downloader.download(reel, work_dir, progress)

        if downloaded.kind == "image":
            image_directory = image_output_dir or output_dir / "imgs"
            image_paths = _publish_images(
                downloaded.paths,
                image_directory,
                reel.code,
            )
            caption_path = None
            if downloaded.caption is not None:
                caption_source = work_dir / "caption.txt"
                caption_source.write_text(downloaded.caption, encoding="utf-8")
                caption_path = _publish_file(
                    caption_source, image_directory / f"{reel.code}-legenda.txt"
                )
            if progress:
                progress("Concluido.")
            return Result(image_paths=image_paths, caption_path=caption_path)

        video = downloaded.paths[0]
        try:
            if progress:
                progress("Extraindo audio do video...")
            audio_path = audio_extractor.extract(video, work_dir)
            transcription = transcriber.transcribe(audio_path, model, progress)
        except AudioExtractionError as exc:
            preserved = _publish_video(
                video,
                available_video(output_dir, base_name("")),
            )
            raise MediaProcessingError(
                f"{exc} O video foi preservado em: {preserved}",
                preserved_video=preserved,
            ) from exc
        except GeminiError as exc:
            preserved = _publish_video(
                video,
                available_video(output_dir, base_name("")),
            )
            raise GeminiProcessingError(
                f"{exc} O video foi preservado em: {preserved}",
                preserved_video=preserved,
            ) from exc

        desired = base_name(transcription.first_sentence)
        video_path, transcript_path = available_pair(output_dir, desired)
        _publish_pair(
            video,
            transcription.portuguese_text,
            video_path,
            transcript_path,
        )

    if progress:
        progress("Concluido.")
    return Result(video_path=video_path, transcript_path=transcript_path)


def _publish_images(
    sources: tuple[Path, ...],
    output_dir: Path,
    code: str,
) -> tuple[Path, ...]:
    published: list[Path] = []
    for index, source in enumerate(sources, start=1):
        desired = image_base_name(code, index)
        destination = output_dir / f"{desired}{source.suffix or '.jpg'}"
        published.append(_publish_file(source, destination))
    return tuple(published)


def _publish_video(source: Path, destination: Path) -> Path:
    return _publish_file(source, destination)


def _publish_file(source: Path, destination: Path) -> Path:
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
