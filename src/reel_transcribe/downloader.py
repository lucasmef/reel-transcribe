from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Callable

from .errors import DownloadError
from .urls import ReelUrl

Progress = Callable[[str], None]


class ReelDownloader:
    def download(
        self,
        reel: ReelUrl,
        work_dir: Path,
        progress: Progress | None = None,
    ) -> Path:
        try:
            import yt_dlp
        except ImportError as exc:
            raise DownloadError(
                "Dependencia yt-dlp ausente. Reinstale o pacote reel-transcribe."
            ) from exc

        def hook(status: dict[str, Any]) -> None:
            if progress and status.get("status") == "downloading":
                percent = str(status.get("_percent_str", "")).strip()
                if percent:
                    progress(f"Baixando Reel: {percent}")

        ffmpeg_available = shutil.which("ffmpeg") is not None
        if progress and not ffmpeg_available:
            progress(
                "ffmpeg nao encontrado; tentando baixar um MP4 ja combinado."
            )

        output_template = str(work_dir / "reel.%(ext)s")
        options: dict[str, Any] = {
            "format": (
                "bestvideo*+bestaudio/best"
                if ffmpeg_available
                else "best[ext=mp4]/best"
            ),
            "merge_output_format": "mp4",
            "outtmpl": output_template,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [hook],
            "retries": 3,
            "fragment_retries": 3,
        }

        try:
            with yt_dlp.YoutubeDL(options) as downloader:
                downloader.download([reel.url])
        except Exception as exc:
            raise DownloadError(self._friendly_error(str(exc))) from exc

        candidates = [
            path
            for path in work_dir.glob("reel.*")
            if path.is_file()
            and path.suffix.lower() not in {".part", ".ytdl", ".json"}
        ]
        if not candidates:
            raise DownloadError("O download terminou sem produzir um arquivo de video.")

        mp4 = next((path for path in candidates if path.suffix.lower() == ".mp4"), None)
        if mp4 is None:
            raise DownloadError(
                "O Instagram nao forneceu um MP4 pronto. Instale o ffmpeg e tente "
                "novamente para converter ou combinar o video."
            )
        return mp4

    @staticmethod
    def _friendly_error(raw_message: str) -> str:
        message = raw_message.lower()
        login_markers = (
            "login required",
            "private",
            "cookies",
            "not available",
            "requested content is not available",
        )
        if any(marker in message for marker in login_markers):
            return (
                "Nao foi possivel acessar o Reel. A primeira versao aceita somente "
                "Reels publicos que nao exigem login."
            )
        return f"Falha ao baixar o Reel: {raw_message}"
