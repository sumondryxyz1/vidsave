"""yt-dlp wrapper for downloading media from YouTube, Facebook and other sites."""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import shutil

import static_ffmpeg
from yt_dlp import YoutubeDL

# static-ffmpeg ships both ffmpeg and ffprobe (ffprobe is required for MP3
# post-processing); it downloads the binaries on first import.
static_ffmpeg.add_paths()
_ffmpeg_bin = shutil.which("ffmpeg")
# Point yt-dlp at the directory so it can find ffprobe next to ffmpeg.
FFMPEG_PATH = str(Path(_ffmpeg_bin).parent) if _ffmpeg_bin else None

URL_RE = re.compile(r"https?://[^\s<>\"']+")

# Cookies (optional) let yt-dlp access age/region-restricted or logged-in content.
# Point these at a Netscape-format cookie file exported from your browser.
COOKIE_FILES: dict[str, str] = {
    "youtube": os.getenv("YT_COOKIES", ""),
    "facebook": os.getenv("FB_COOKIES", ""),
    "instagram": os.getenv("IG_COOKIES", ""),
}


@dataclass
class MediaInfo:
    url: str
    title: str
    uploader: str
    duration: int | None
    thumbnail: str | None
    webpage_url: str
    formats: list[dict[str, Any]] = field(default_factory=list)


def extract_url(text: str) -> str | None:
    match = URL_RE.search(text or "")
    return match.group(0) if match else None


def _base_opts() -> dict[str, Any]:
    return {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "ffmpeg_location": FFMPEG_PATH,
        "retries": 3,
        "socket_timeout": 30,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            )
        },
    }


def _cookie_opts(url: str) -> dict[str, Any]:
    lowered = url.lower()
    for key, path in COOKIE_FILES.items():
        if path and key in lowered and Path(path).exists():
            return {"cookiefile": path}
    return {}


def probe(url: str) -> MediaInfo:
    """Fetch metadata (title, duration, available formats) without downloading."""
    with YoutubeDL({**_base_opts(), **_cookie_opts(url)}) as ydl:
        info = ydl.extract_info(url, download=False)

    if info.get("_type") == "playlist":
        info = info["entries"][0]

    return MediaInfo(
        url=url,
        title=info.get("title") or "media",
        uploader=info.get("uploader") or info.get("channel") or "",
        duration=info.get("duration"),
        thumbnail=info.get("thumbnail"),
        webpage_url=info.get("webpage_url") or url,
        formats=info.get("formats") or [],
    )


def available_heights(info: MediaInfo) -> list[int]:
    heights = {
        f.get("height")
        for f in info.formats
        if f.get("height") and f.get("vcodec") not in (None, "none")
    }
    return sorted(h for h in heights if h)


def _format_selector(height: int | None, audio_only: bool) -> str:
    if audio_only:
        return "bestaudio/best"
    if height is None:
        return "bestvideo+bestaudio/best"
    # Prefer mp4 streams at the requested height, fall back gracefully.
    return (
        f"bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/"
        f"bestvideo[height<={height}]+bestaudio/best[height<={height}]/best"
    )


def download(
    url: str,
    out_dir: str | Path,
    height: int | None = None,
    audio_only: bool = False,
    progress_hook: Callable[[dict[str, Any]], None] | None = None,
) -> Path:
    """Download media into ``out_dir`` and return the resulting file path."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    opts: dict[str, Any] = {
        **_base_opts(),
        **_cookie_opts(url),
        "format": _format_selector(height, audio_only),
        "outtmpl": str(out_dir / "%(title).150B.%(ext)s"),
        "restrictfilenames": False,
        "windowsfilenames": True,
    }

    if audio_only:
        opts["postprocessors"] = [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
        ]
    else:
        opts["merge_output_format"] = "mp4"

    if progress_hook:
        opts["progress_hooks"] = [progress_hook]

    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        if info.get("_type") == "playlist":
            info = info["entries"][0]
        path = Path(ydl.prepare_filename(info))

    if audio_only:
        path = path.with_suffix(".mp3")

    if not path.exists():
        candidates = sorted(out_dir.glob(path.stem + ".*"), key=lambda p: p.stat().st_mtime)
        if not candidates:
            raise FileNotFoundError("Download finished but no output file was found.")
        path = candidates[-1]

    return path


def make_temp_dir() -> str:
    return tempfile.mkdtemp(prefix="dlbot-")


def cleanup(path: str | Path) -> None:
    p = Path(path)
    if p.is_dir():
        shutil.rmtree(p, ignore_errors=True)
    elif p.exists():
        p.unlink(missing_ok=True)
