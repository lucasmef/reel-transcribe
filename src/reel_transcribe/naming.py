from __future__ import annotations

import os
import re
import unicodedata
from datetime import date
from pathlib import Path

_INVALID_WINDOWS_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WHITESPACE = re.compile(r"\s+")
_WINDOWS_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def default_output_directory() -> Path:
    configured = os.environ.get("REEL_TRANSCRIBE_OUTPUT", "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path.home() / "Videos" / "reel-transcribe"


def default_image_output_directory() -> Path:
    return Path.home() / "Downloads"


def sanitize_title(value: str, *, max_length: int = 100) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    cleaned = _INVALID_WINDOWS_CHARS.sub(" ", normalized)
    cleaned = _WHITESPACE.sub(" ", cleaned).strip(" .")

    if cleaned.upper() in _WINDOWS_RESERVED:
        cleaned = f"_{cleaned}"

    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rstrip(" .")
    return cleaned


def base_name(first_sentence: str, *, processed_on: date | None = None) -> str:
    date_prefix = (processed_on or date.today()).isoformat()
    title = sanitize_title(first_sentence)
    if not title:
        return f"{date_prefix}-reel"
    return f"{date_prefix}-{title}"


def image_base_name(post_code: str, index: int) -> str:
    title = sanitize_title(f"{post_code}-{index}")
    return title or f"image-{index}"


def available_pair(output_dir: Path, desired_base: str) -> tuple[Path, Path]:
    counter = 1
    while True:
        suffix = "" if counter == 1 else f" ({counter})"
        video = output_dir / f"{desired_base}{suffix}.mp4"
        transcript = output_dir / f"{desired_base}{suffix}.txt"
        if not video.exists() and not transcript.exists():
            return video, transcript
        counter += 1


def available_file(output_dir: Path, desired_base: str, extension: str) -> Path:
    counter = 1
    normalized_extension = extension if extension.startswith(".") else f".{extension}"
    while True:
        suffix = "" if counter == 1 else f" ({counter})"
        candidate = output_dir / f"{desired_base}{suffix}{normalized_extension}"
        if not candidate.exists():
            return candidate
        counter += 1


def available_video(output_dir: Path, desired_base: str) -> Path:
    counter = 1
    while True:
        suffix = "" if counter == 1 else f" ({counter})"
        candidate = output_dir / f"{desired_base}{suffix}.mp4"
        if not candidate.exists():
            return candidate
        counter += 1
