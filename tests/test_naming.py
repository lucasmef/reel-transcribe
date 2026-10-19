from datetime import date
from pathlib import Path

from reel_transcribe.naming import (
    available_file,
    available_pair,
    base_name,
    default_image_output_directory,
    default_output_directory,
    image_base_name,
    sanitize_title,
)


def test_sanitizes_windows_filename():
    assert sanitize_title('  Ola: "mundo" / teste?  ') == "Ola mundo teste"


def test_limits_title_length():
    assert len(sanitize_title("a" * 150)) == 100


def test_fallback_name_without_speech():
    assert base_name("", processed_on=date(2026, 6, 6)) == "2026-06-06-reel"


def test_adds_date_without_reel_code():
    assert (
        base_name("Primeira frase.", processed_on=date(2026, 6, 6))
        == "2026-06-06-Primeira frase"
    )


def test_avoids_pair_collision(tmp_path: Path):
    (tmp_path / "2026-06-06-Titulo.txt").write_text("existente", encoding="utf-8")
    video, text = available_pair(tmp_path, "2026-06-06-Titulo")
    assert video.name == "2026-06-06-Titulo (2).mp4"
    assert text.name == "2026-06-06-Titulo (2).txt"


def test_avoids_single_file_collision(tmp_path: Path):
    (tmp_path / "2026-06-06-IMG.jpg").write_bytes(b"existente")
    image = available_file(tmp_path, "2026-06-06-IMG", ".jpg")
    assert image.name == "2026-06-06-IMG (2).jpg"


def test_default_image_output_is_downloads_folder():
    assert default_image_output_directory() == Path.home() / "Downloads"


def test_image_base_name_uses_post_code_and_index_without_date():
    assert image_base_name("DaNVOJbGcUP", 3) == "DaNVOJbGcUP-3"


def test_output_directory_can_be_configured(monkeypatch):
    monkeypatch.setenv("REEL_TRANSCRIBE_OUTPUT", "~/custom-output")
    assert default_output_directory() == Path.home() / "custom-output"
