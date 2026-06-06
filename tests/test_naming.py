from datetime import date
from pathlib import Path

from reel_transcribe.naming import available_pair, base_name, sanitize_title


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
