from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .errors import AudioExtractionError


class FfmpegAudioExtractor:
    def extract(self, video_path: Path, work_dir: Path) -> Path:
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg is None:
            raise AudioExtractionError(
                "O ffmpeg e necessario para extrair o audio antes do envio ao Gemini."
            )

        audio_path = work_dir / "reel-audio.mp3"
        command = [
            ffmpeg,
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
            str(audio_path),
        ]

        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as exc:
            raise AudioExtractionError(f"Falha ao executar o ffmpeg: {exc}") from exc

        if completed.returncode != 0 or not audio_path.is_file():
            detail = completed.stderr.strip()
            message = "O ffmpeg nao conseguiu extrair o audio do Reel."
            if detail:
                message = f"{message} {detail}"
            raise AudioExtractionError(message)

        if audio_path.stat().st_size == 0:
            raise AudioExtractionError("O ffmpeg produziu um arquivo de audio vazio.")

        return audio_path
