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
from .naming import default_output_directory

DEFAULT_MODEL = "gemini-3.5-flash"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reel-transcribe",
        description=(
            "Baixa um Reel publico e salva o video e sua transcricao integral "
            "em portugues."
        ),
    )
    parser.add_argument("url", help="URL publica do Reel no Instagram")
    parser.add_argument(
        "--output",
        type=Path,
        default=default_output_directory(),
        help="diretorio de saida (padrao: Google Drive/VIDEOS/MODEL)",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"modelo Gemini (padrao: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        print(
            "Erro: defina a variavel de ambiente GEMINI_API_KEY antes de executar.",
            file=sys.stderr,
        )
        return 2

    try:
        result = process_reel(
            args.url,
            output_dir=args.output.expanduser().resolve(),
            model=args.model,
            downloader=ReelDownloader(),
            audio_extractor=FfmpegAudioExtractor(),
            transcriber=GeminiTranscriber(api_key),
            progress=print,
        )
    except ReelTranscribeError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Erro ao gravar os arquivos: {exc}", file=sys.stderr)
        return 1

    print(f"Video: {result.video_path}")
    print(f"Transcricao: {result.transcript_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
