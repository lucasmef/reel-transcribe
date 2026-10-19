from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Sequence

from . import __version__
from .app import process_reel
from .audio import FfmpegAudioExtractor
from .downloader import ReelDownloader
from .errors import ReelTranscribeError
from .gemini import GeminiTranscriber
from .naming import default_image_output_directory, default_output_directory

DEFAULT_MODEL = "gemini-3.5-flash"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reel-transcribe",
        description=(
            "Baixa um Reel publico com transcricao ou fotos e legenda de um post publico "
            "do Instagram."
        ),
    )
    parser.add_argument("url", help="URL publica de Reel ou post no Instagram")
    parser.add_argument(
        "--output",
        type=Path,
        default=default_output_directory(),
        help="diretorio de saida (padrao: REEL_TRANSCRIBE_OUTPUT ou ~/Videos/reel-transcribe)",
    )
    parser.add_argument(
        "--image-output",
        type=Path,
        default=default_image_output_directory(),
        help="diretorio de saida para fotos e legendas (padrao: pasta Downloads)",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=(
            f"modelo Gemini inicial (padrao: {DEFAULT_MODEL}; "
            "fallback automatico: gemini-3.1-flash-lite)"
        ),
    )
    parser.add_argument(
        "--cookies-from-browser",
        choices=("safari", "chrome", "firefox", "edge", "brave", "chromium", "opera", "vivaldi"),
        help="usa a sessao do navegador escolhido; desativado por padrao",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        result = process_reel(
            args.url,
            output_dir=args.output.expanduser().resolve(),
            image_output_dir=args.image_output.expanduser().resolve(),
            model=args.model,
            downloader=ReelDownloader(cookies_from_browser=args.cookies_from_browser),
            audio_extractor=FfmpegAudioExtractor(),
            transcriber=_LazyGeminiTranscriber(
                os.environ.get("GEMINI_API_KEY", "")
            ),
            progress=print,
        )
    except ReelTranscribeError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Erro ao gravar os arquivos: {exc}", file=sys.stderr)
        return 1

    if result.image_paths:
        label = "Imagem" if len(result.image_paths) == 1 else "Imagens"
        print(f"{label}:")
        for image_path in result.image_paths:
            print(image_path)
        if result.caption_path is not None:
            print(f"Legenda: {result.caption_path}")
        else:
            print("Legenda: indisponivel; nenhuma legenda foi inventada.")
    else:
        print(f"Video: {result.video_path}")
        print(f"Transcricao: {result.transcript_path}")
    return 0


class _LazyGeminiTranscriber:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def transcribe(self, audio_path: Path, model: str, progress=None):
        return GeminiTranscriber(self._api_key).transcribe(
            audio_path,
            model,
            progress,
        )


if __name__ == "__main__":
    raise SystemExit(main())
