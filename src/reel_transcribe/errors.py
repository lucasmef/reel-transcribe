from __future__ import annotations

from pathlib import Path


class ReelTranscribeError(Exception):
    """Erro esperado que pode ser apresentado diretamente ao usuario."""


class InvalidReelUrlError(ReelTranscribeError):
    pass


class DownloadError(ReelTranscribeError):
    pass


class AudioExtractionError(ReelTranscribeError):
    pass


class GeminiError(ReelTranscribeError):
    pass


class MediaProcessingError(ReelTranscribeError):
    def __init__(self, message: str, preserved_video: Path | None = None) -> None:
        super().__init__(message)
        self.preserved_video = preserved_video


class GeminiProcessingError(MediaProcessingError, GeminiError):
    pass
