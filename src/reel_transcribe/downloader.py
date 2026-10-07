from __future__ import annotations

import shutil
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal

from .errors import DownloadError
from .http import (
    API_DOMAINS,
    MEDIA_DOMAINS,
    MAX_IMAGE_BYTES,
    MAX_METADATA_BYTES,
    read_limited,
    safe_opener,
    validate_url,
)
from .urls import ReelUrl

Progress = Callable[[str], None]

_IMAGE_EXTENSIONS = {".avif", ".heic", ".jpeg", ".jpg", ".png", ".webp"}
_VIDEO_EXTENSIONS = {".m4v", ".mov", ".mp4", ".webm"}


@dataclass(frozen=True)
class DownloadedMedia:
    kind: Literal["video", "image"]
    paths: tuple[Path, ...]
    caption: str | None = None

    @classmethod
    def video(cls, path: Path) -> "DownloadedMedia":
        return cls(kind="video", paths=(path,))

    @classmethod
    def images(cls, paths: tuple[Path, ...], caption: str | None = None) -> "DownloadedMedia":
        return cls(kind="image", paths=paths, caption=caption)


class ReelDownloader:
    def __init__(self, *, cookies_from_browser: str | None = None) -> None:
        self.cookies_from_browser = cookies_from_browser

    def download(
        self,
        reel: ReelUrl,
        work_dir: Path,
        progress: Progress | None = None,
    ) -> DownloadedMedia:
        try:
            import yt_dlp
        except ImportError as exc:
            raise DownloadError(
                "Dependencia yt-dlp ausente. Reinstale o pacote reel-transcribe."
            ) from exc

        if reel.kind == "p":
            return self._download_images(yt_dlp, reel, work_dir, progress)
        return self._download_video(yt_dlp, reel, work_dir, progress)

    def _download_video(
        self,
        yt_dlp: Any,
        reel: ReelUrl,
        work_dir: Path,
        progress: Progress | None,
    ) -> DownloadedMedia:
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

        quicktime_format = (
            "bestvideo[ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a]/"
            "bestvideo[ext=mp4][vcodec^=avc1]+bestaudio/"
            "best[ext=mp4][vcodec^=avc1]/best[ext=mp4]/best"
        )
        output_template = str(work_dir / "reel.%(ext)s")
        options: dict[str, Any] = {
            "format": (
                quicktime_format
                if ffmpeg_available
                else "best[ext=mp4][vcodec^=avc1]/best[ext=mp4]/best"
            ),
            "merge_output_format": "mp4",
            "outtmpl": output_template,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [hook],
            "retries": 3,
            "fragment_retries": 3,
            "socket_timeout": 30,
            "max_filesize": 512 * 1024 * 1024,
        }
        if self.cookies_from_browser:
            options["cookiesfrombrowser"] = (self.cookies_from_browser, None, None, None)

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
        return DownloadedMedia.video(mp4)

    def _download_images(
        self,
        yt_dlp: Any,
        reel: ReelUrl,
        work_dir: Path,
        progress: Progress | None,
    ) -> DownloadedMedia:
        options: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "ignore_no_formats_error": True,
            "noplaylist": False,
            "retries": 3,
            "fragment_retries": 3,
            "socket_timeout": 30,
        }
        if self.cookies_from_browser:
            options["cookiesfrombrowser"] = (self.cookies_from_browser, None, None, None)

        info: dict[str, Any] | None = None
        extract_error: Exception | None = None
        try:
            with yt_dlp.YoutubeDL(options) as downloader:
                info = downloader.extract_info(reel.url, download=False)
        except Exception as exc:
            extract_error = exc

        image_urls = self._image_urls(info) if info else ()
        caption = self._caption(info) if info else None
        if not image_urls or caption is None:
            try:
                api_urls, api_caption = self._instagram_api_images(reel)
                image_urls = api_urls or image_urls
                if api_caption is not None:
                    caption = api_caption
            except DownloadError:
                if not image_urls:
                    raise
                if progress:
                    progress("Fotos disponiveis, mas nao foi possivel recuperar a legenda.")
        if not image_urls:
            if extract_error is not None:
                raise DownloadError(self._friendly_error(str(extract_error))) from extract_error
            raise DownloadError(
                "O post nao parece conter imagens baixaveis. Se for video, envie o "
                "link do Reel correspondente."
            )

        image_paths: list[Path] = []
        for index, image_url in enumerate(image_urls, start=1):
            if progress:
                progress(f"Baixando imagem {index} de {len(image_urls)}...")
            image_paths.append(
                self._download_image_url(
                    image_url,
                    work_dir / f"image-{index}",
                )
            )

        return DownloadedMedia.images(tuple(image_paths), caption=caption)

    @classmethod
    def _caption(cls, info: dict[str, Any]) -> str | None:
        description = info.get("description")
        if isinstance(description, str):
            return description
        for entry in info.get("entries") or []:
            if isinstance(entry, dict):
                caption = cls._caption(entry)
                if caption is not None:
                    return caption
        return None

    @classmethod
    def _image_urls(cls, info: dict[str, Any]) -> tuple[str, ...]:
        urls: list[str] = []

        def visit(item: dict[str, Any]) -> None:
            entries = item.get("entries")
            if entries:
                for entry in entries:
                    if isinstance(entry, dict):
                        visit(entry)
                return

            if cls._has_video_format(item):
                return

            direct_url = item.get("url")
            if isinstance(direct_url, str) and cls._is_image_url(direct_url):
                urls.append(direct_url)
                return

            thumbnail = cls._best_thumbnail_url(item)
            if thumbnail:
                urls.append(thumbnail)

        visit(info)
        return tuple(dict.fromkeys(urls))

    def _instagram_api_images(self, reel: ReelUrl) -> tuple[tuple[str, ...], str | None]:
        media_pk = self._shortcode_to_media_pk(reel.code)
        request = urllib.request.Request(
            f"https://i.instagram.com/api/v1/media/{media_pk}/info/",
            headers={
                "Accept": "*/*",
                "Origin": "https://www.instagram.com",
                "Referer": reel.url,
                "User-Agent": "Mozilla/5.0",
                "X-ASBD-ID": "198387",
                "X-IG-App-ID": "936619743392459",
                "X-IG-WWW-Claim": "0",
            },
        )

        try:
            handlers = []
            if self.cookies_from_browser:
                from yt_dlp.cookies import extract_cookies_from_browser

                cookie_jar = extract_cookies_from_browser(self.cookies_from_browser)
                handlers.append(urllib.request.HTTPCookieProcessor(cookie_jar))
            validate_url(request.full_url, API_DOMAINS)
            opener = safe_opener(API_DOMAINS, *handlers)
            with opener.open(request, timeout=30) as response:
                import json

                data = json.loads(read_limited(response, MAX_METADATA_BYTES))
        except DownloadError:
            raise
        except Exception as exc:
            raise DownloadError(
                "Falha ao consultar imagens do post no Instagram."
            ) from exc

        if not isinstance(data, dict):
            raise DownloadError("O Instagram retornou metadados invalidos.")
        item = next(
            (entry for entry in data.get("items", []) if isinstance(entry, dict)),
            {},
        )
        if not item:
            raise DownloadError("O Instagram nao retornou os dados do post.")
        return self._images_from_api_item(item)

    @classmethod
    def _images_from_api_item(cls, item: dict[str, Any]) -> tuple[tuple[str, ...], str]:
        medias = item.get("carousel_media") or [item]
        urls: list[str] = []
        for media in medias:
            if not isinstance(media, dict):
                continue
            if media.get("media_type") == 2 or media.get("video_versions"):
                continue
            image_versions = media.get("image_versions2") or {}
            candidates = image_versions.get("candidates") or []
            candidate = cls._largest_image_candidate(candidates)
            if candidate:
                urls.append(candidate)
        caption = item.get("caption")
        caption_text = caption.get("text", "") if isinstance(caption, dict) else ""
        return tuple(dict.fromkeys(urls)), caption_text if isinstance(caption_text, str) else ""

    @classmethod
    def _largest_image_candidate(cls, candidates: Any) -> str | None:
        if not isinstance(candidates, list):
            return None
        images = [
            candidate
            for candidate in candidates
            if isinstance(candidate, dict) and isinstance(candidate.get("url"), str)
        ]
        if not images:
            return None

        def score(candidate: dict[str, Any]) -> int:
            return cls._dimension(candidate.get("width")) * cls._dimension(
                candidate.get("height")
            )

        return max(images, key=score)["url"]

    @staticmethod
    def _shortcode_to_media_pk(shortcode: str) -> int:
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        media_pk = 0
        for char in shortcode:
            media_pk = media_pk * 64 + alphabet.index(char)
        return media_pk

    @staticmethod
    def _has_video_format(info: dict[str, Any]) -> bool:
        formats = info.get("formats")
        if isinstance(formats, list) and formats:
            return True
        extension = f".{str(info.get('ext', '')).lower().lstrip('.')}"
        return extension in _VIDEO_EXTENSIONS

    @staticmethod
    def _best_thumbnail_url(info: dict[str, Any]) -> str | None:
        thumbnails = [
            thumbnail
            for thumbnail in info.get("thumbnails") or []
            if isinstance(thumbnail, dict) and isinstance(thumbnail.get("url"), str)
        ]
        if not thumbnails:
            thumbnail = info.get("thumbnail")
            return thumbnail if isinstance(thumbnail, str) else None

        def score(thumbnail: dict[str, Any]) -> int:
            return ReelDownloader._dimension(thumbnail.get("width")) * ReelDownloader._dimension(
                thumbnail.get("height")
            )

        return max(thumbnails, key=score)["url"]

    @staticmethod
    def _dimension(value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _download_image_url(url: str, destination_base: Path) -> Path:
        validate_url(url, MEDIA_DOMAINS)
        request = urllib.request.Request(
            url,
            headers={
                "Referer": "https://www.instagram.com/",
                "User-Agent": "Mozilla/5.0",
            },
        )
        try:
            with safe_opener(MEDIA_DOMAINS).open(request, timeout=30) as response:
                content_type = response.headers.get("Content-Type", "")
                extension = ReelDownloader._extension_from_content_type(content_type)
                if extension is None:
                    raise DownloadError("O servidor nao retornou um tipo de imagem permitido.")
                data = read_limited(response, MAX_IMAGE_BYTES)
        except DownloadError:
            raise
        except Exception as exc:
            raise DownloadError("Falha ao baixar imagem do post.") from exc

        if not data:
            raise DownloadError("O Instagram retornou uma imagem vazia.")

        destination = destination_base.with_suffix(extension)
        destination.write_bytes(data)
        return destination

    @staticmethod
    def _extension_from_content_type(content_type: str) -> str | None:
        normalized = content_type.split(";", 1)[0].strip().lower()
        return {
            "image/avif": ".avif",
            "image/heic": ".heic",
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
        }.get(normalized)

    @staticmethod
    def _extension_from_url(url: str) -> str | None:
        path = urllib.parse.urlparse(url).path
        extension = Path(path).suffix.lower()
        return extension if extension in _IMAGE_EXTENSIONS else None

    @staticmethod
    def _is_image_url(url: str) -> bool:
        return ReelDownloader._extension_from_url(url) is not None

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
                "Nao foi possivel acessar o conteudo. A ferramenta aceita somente "
                "links publicos que nao exigem login."
            )
        return f"Falha ao baixar o conteudo: {raw_message}"
