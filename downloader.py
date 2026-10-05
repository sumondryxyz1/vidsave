"""yt-dlp wrapper: probing, quality/audio selection, subtitles, playlists, proxy.

Shared by the Telegram bot (bot.py) and the web app (webapp.py).
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import static_ffmpeg
from yt_dlp import YoutubeDL

# static-ffmpeg ships both ffmpeg and ffprobe (ffprobe is required for MP3
# post-processing); it downloads the binaries on first import.
static_ffmpeg.add_paths()
_ffmpeg_bin = shutil.which("ffmpeg")
# Point yt-dlp at the directory so it can find ffprobe next to ffmpeg.
FFMPEG_PATH = str(Path(_ffmpeg_bin).parent) if _ffmpeg_bin else None

URL_RE = re.compile(r"https?://[^\s<>\"']+")

# Optional proxy for geo-blocked content or datacenter-IP 403s.
PROXY = os.getenv("PROXY", "")

# Cap a single download so a free host's disk does not fill up (0 = unlimited).
MAX_FILESIZE_MB = int(os.getenv("MAX_FILESIZE_MB", "500"))

# Cookies (optional) let yt-dlp access age/region-restricted or logged-in content.
# Point these at a Netscape-format cookie file exported from your browser.
COOKIE_FILES: dict[str, str] = {
    "youtube": os.getenv("YT_COOKIES", ""),
    "facebook": os.getenv("FB_COOKIES", ""),
    "instagram": os.getenv("IG_COOKIES", ""),
}

# YouTube serves different results per "player client". Datacenter IPs (Render,
# Fly, AWS) often fail the default one with "not a bot"/"No video formats", while
# another client still works — so try each in turn before giving up.
PLAYER_CLIENTS: tuple[str, ...] = tuple(
    c.strip() for c in os.getenv("YT_PLAYER_CLIENTS", "default,android_vr,tv,web_safari").split(",") if c.strip()
)

QUALITY_PRESETS = (2160, 1440, 1080, 720, 480, 360, 240)
AUDIO_BITRATES = (128, 192, 320)


@dataclass
class Entry:
    """A single downloadable item (a video, or one playlist entry)."""

    id: str
    title: str
    url: str
    duration: int | None = None
    thumbnail: str | None = None


@dataclass
class MediaInfo:
    url: str
    title: str
    uploader: str
    duration: int | None
    thumbnail: str | None
    webpage_url: str
    formats: list[dict[str, Any]] = field(default_factory=list)
    is_playlist: bool = False
    entries: list[Entry] = field(default_factory=list)


def extract_url(text: str) -> str | None:
    match = URL_RE.search(text or "")
    return match.group(0) if match else None


def _base_opts() -> dict[str, Any]:
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
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
    if PROXY:
        opts["proxy"] = PROXY
    return opts


def _cookie_opts(url: str) -> dict[str, Any]:
    lowered = url.lower()
    for key, path in COOKIE_FILES.items():
        if path and key in lowered and Path(path).exists():
            return {"cookiefile": path}
    return {}


def _is_youtube(url: str) -> bool:
    lowered = url.lower()
    return "youtube.com" in lowered or "youtu.be" in lowered


def _attempts(url: str) -> list[dict[str, Any]]:
    """Extra yt-dlp options to try in order; YouTube gets one per player client."""
    if not _is_youtube(url):
        return [{}]
    return [{"extractor_args": {"youtube": {"player_client": [c]}}} for c in PLAYER_CLIENTS]


def probe(url: str) -> MediaInfo:
    """Fetch metadata without downloading. Detects playlists and lists entries."""
    info = None
    last: Exception | None = None
    for extra in _attempts(url):
        try:
            with YoutubeDL({**_base_opts(), **_cookie_opts(url), **extra}) as ydl:
                info = ydl.extract_info(url, download=False)
            break
        except Exception as exc:  # noqa: BLE001 — try the next client
            last = exc
    if info is None:
        raise last if last else RuntimeError("probe failed")

    if info.get("_type") == "playlist":
        entries = []
        for e in (info.get("entries") or [])[:200]:
            if not e:
                continue
            entries.append(
                Entry(
                    id=str(e.get("id") or ""),
                    title=e.get("title") or "media",
                    url=e.get("webpage_url") or e.get("url") or "",
                    duration=e.get("duration"),
                    thumbnail=e.get("thumbnail"),
                )
            )
        return MediaInfo(
            url=url,
            title=info.get("title") or "playlist",
            uploader=info.get("uploader") or info.get("channel") or "",
            duration=None,
            thumbnail=info.get("thumbnail") or (entries[0].thumbnail if entries else None),
            webpage_url=info.get("webpage_url") or url,
            formats=[],
            is_playlist=True,
            entries=entries,
        )

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


def _build_opts(
    out_dir: Path,
    url: str,
    height: int | None,
    audio_only: bool,
    audio_bitrate: int,
    subtitles: bool,
    playlist: bool,
    progress_hook: Callable[[dict[str, Any]], None] | None,
) -> dict[str, Any]:
    opts: dict[str, Any] = {
        **_base_opts(),
        **_cookie_opts(url),
        "format": _format_selector(height, audio_only),
        "outtmpl": str(out_dir / "%(title).150B.%(ext)s"),
        "restrictfilenames": False,
        "windowsfilenames": True,
        "noplaylist": not playlist,
        "ignoreerrors": playlist,  # keep going if one playlist item fails
        "concurrent_fragment_downloads": 4,
    }

    if audio_only:
        opts["postprocessors"] = [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3",
             "preferredquality": str(audio_bitrate)}
        ]
    else:
        opts["merge_output_format"] = "mp4"

    if subtitles and not audio_only:
        opts["writesubtitles"] = True
        opts["writeautomaticsub"] = True
        opts["subtitleslangs"] = ["en", "bn"]
        opts["postprocessors"] = opts.get("postprocessors", []) + [
            {"key": "FFmpegEmbedSubtitle", "already_have_subtitle": False}
        ]

    if progress_hook:
        opts["progress_hooks"] = [progress_hook]

    if MAX_FILESIZE_MB > 0:
        opts["max_filesize"] = MAX_FILESIZE_MB * 1024 * 1024

    return opts


def _final_path(ydl: YoutubeDL, info: dict[str, Any], out_dir: Path, audio_only: bool) -> Path:
    path = Path(ydl.prepare_filename(info))
    if audio_only:
        path = path.with_suffix(".mp3")
    if not path.exists():
        candidates = sorted(out_dir.glob(path.stem + ".*"), key=lambda p: p.stat().st_mtime)
        if candidates:
            path = candidates[-1]
    return path


def download(
    url: str,
    out_dir: str | Path,
    height: int | None = None,
    audio_only: bool = False,
    audio_bitrate: int = 192,
    subtitles: bool = False,
    progress_hook: Callable[[dict[str, Any]], None] | None = None,
) -> Path:
    """Download a single item into ``out_dir`` and return the resulting file path."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    opts = _build_opts(out_dir, url, height, audio_only, audio_bitrate, subtitles, False, progress_hook)
    path: Path | None = None
    last: Exception | None = None
    for extra in _attempts(url):
        try:
            with YoutubeDL({**opts, **extra}) as ydl:
                info = ydl.extract_info(url, download=True)
                if info.get("_type") == "playlist":
                    info = (info.get("entries") or [{}])[0]
                path = _final_path(ydl, info, out_dir, audio_only)
            break
        except Exception as exc:  # noqa: BLE001 — try the next client
            last = exc
    if path is None:
        raise last if last else RuntimeError("download failed")
    if not path.exists():
        raise FileNotFoundError("Download finished but no output file was found.")
    return path


def download_playlist(
    url: str,
    out_dir: str | Path,
    height: int | None = None,
    audio_only: bool = False,
    audio_bitrate: int = 192,
    subtitles: bool = False,
    progress_hook: Callable[[dict[str, Any]], None] | None = None,
) -> list[Path]:
    """Download every entry of a playlist/channel and return the file paths."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    opts = _build_opts(out_dir, url, height, audio_only, audio_bitrate, subtitles, True, progress_hook)
    done = False
    last: Exception | None = None
    for extra in _attempts(url):
        try:
            with YoutubeDL({**opts, **extra}) as ydl:
                ydl.extract_info(url, download=True)
            done = True
            break
        except Exception as exc:  # noqa: BLE001 — try the next client
            last = exc
    if not done and last is not None:
        raise last

    ext = ".mp3" if audio_only else None
    files = [p for p in sorted(out_dir.iterdir()) if p.is_file()]
    if ext:
        files = [p for p in files if p.suffix == ext]
    if not files:
        raise FileNotFoundError("Playlist download produced no files.")
    return files


def make_temp_dir() -> str:
    return tempfile.mkdtemp(prefix="dlbot-")


def cleanup(path: str | Path) -> None:
    p = Path(path)
    if p.is_dir():
        shutil.rmtree(p, ignore_errors=True)
    elif p.exists():
        p.unlink(missing_ok=True)
