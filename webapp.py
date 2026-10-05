"""Web app for the media downloader: paste a link, pick quality, download.

Serves a single-page UI and a JSON/SSE API backed by downloader.py.
Supports single videos, playlists (zipped), audio bitrate choice, subtitles,
job cancellation, and optional proxy.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
import uuid
import zipfile
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel

import downloader

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("webapp")

STATIC_DIR = Path(__file__).parent / "static"
JOB_TTL = int(os.getenv("JOB_TTL", "3600"))  # seconds to keep finished files
MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT", "3"))

_sem = threading.Semaphore(MAX_CONCURRENT)
_lock = threading.Lock()
_jobs: dict[str, "Job"] = {}


@dataclass
class Job:
    id: str
    url: str
    quality: str
    audio_bitrate: int = 192
    subtitles: bool = False
    playlist: bool = False
    status: str = "queued"  # queued|downloading|ready|error|cancelled
    progress: float = 0.0
    speed: str = ""
    eta: str = ""
    item: int = 0
    total_items: int = 0
    title: str = ""
    filename: str = ""
    path: str = ""
    error: str = ""
    created: float = field(default_factory=time.time)
    cancel: bool = False


async def _janitor() -> None:
    while True:
        await asyncio.sleep(60)
        cutoff = time.time() - JOB_TTL
        with _lock:
            stale = [j for j in _jobs.values() if j.created < cutoff]
            for job in stale:
                if job.path:
                    downloader.cleanup(job.path)
                _jobs.pop(job.id, None)


@asynccontextmanager
async def lifespan(_: FastAPI):
    task = asyncio.create_task(_janitor())
    try:
        yield
    finally:
        task.cancel()


app = FastAPI(title="Downloader", docs_url=None, redoc_url=None, lifespan=lifespan)


class ProbeRequest(BaseModel):
    url: str


class DownloadRequest(BaseModel):
    url: str
    quality: str = "best"  # "best" | "audio" | a height like "1080"
    audio_bitrate: int = 192
    subtitles: bool = False
    playlist: bool = False


def _parse_quality(quality: str) -> tuple[int | None, bool]:
    if quality == "audio":
        return None, True
    if quality in ("best", "", None):
        return None, False
    return int(quality), False


def _snapshot(job: Job) -> dict[str, Any]:
    data = asdict(job)
    data.pop("path", None)
    data.pop("cancel", None)
    data["ready"] = job.status == "ready"
    return data


def _run_download(job: Job) -> None:
    """Worker thread: download the media and update the job as it goes."""
    height, audio_only = _parse_quality(job.quality)
    tmp = Path(downloader.make_temp_dir())
    last = [0.0]

    def hook(d: dict) -> None:
        if job.cancel:
            raise RuntimeError("cancelled by user")
        if d.get("status") != "downloading":
            return
        now = time.time()
        if now - last[0] < 0.5:
            return
        last[0] = now
        total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
        done = d.get("downloaded_bytes") or 0
        with _lock:
            job.status = "downloading"
            job.progress = round(done / total * 100, 1) if total else job.progress
            job.speed = (d.get("_speed_str") or "").strip()
            job.eta = (d.get("_eta_str") or "").strip()
            job.item = int(d.get("playlist_index") or 0)
            job.total_items = int(d.get("playlist_count") or job.total_items or 0)
            if d.get("info_dict", {}).get("title"):
                job.title = d["info_dict"]["title"]

    try:
        with _sem:
            with _lock:
                job.status = "downloading"
            if job.playlist:
                files = downloader.download_playlist(
                    job.url, tmp, height=height, audio_only=audio_only,
                    audio_bitrate=job.audio_bitrate, subtitles=job.subtitles,
                    progress_hook=hook,
                )
                if job.cancel:
                    raise RuntimeError("cancelled")
                zip_path = tmp / f"{_safe(job.title or 'playlist')}.zip"
                with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                    for f in files:
                        zf.write(f, arcname=f.name)
                result = zip_path
            else:
                result = downloader.download(
                    job.url, tmp, height=height, audio_only=audio_only,
                    audio_bitrate=job.audio_bitrate, subtitles=job.subtitles,
                    progress_hook=hook,
                )
        with _lock:
            job.path = str(result)
            job.filename = result.name
            job.progress = 100.0
            job.status = "ready"
    except Exception as exc:  # noqa: BLE001 - report any failure to the client
        cancelled = job.cancel or "cancel" in str(exc).lower()
        log.warning("download %s for %s: %s", "cancelled" if cancelled else "failed", job.url, exc)
        with _lock:
            job.status = "cancelled" if cancelled else "error"
            job.error = "" if cancelled else f"{type(exc).__name__}: {exc}"
        downloader.cleanup(tmp)


def _safe(name: str) -> str:
    keep = "".join(c for c in name if c.isalnum() or c in " -_")
    return (keep.strip() or "playlist")[:80]


@app.post("/api/probe")
async def probe(req: ProbeRequest) -> dict[str, Any]:
    url = downloader.extract_url(req.url) or req.url.strip()
    if not url.startswith("http"):
        raise HTTPException(400, "একটি বৈধ লিংক দিন।")
    try:
        info = await asyncio.wait_for(asyncio.to_thread(downloader.probe, url), timeout=120)
    except Exception as exc:  # noqa: BLE001
        detail = str(exc)
        unsupported = ("Unsupported URL" in detail or "[generic]" in detail
                       or "Unable to download webpage" in detail or "No video formats" in detail)
        if unsupported:
            raise HTTPException(422, "এই সাইটটি সাপোর্টেড নয়। YouTube, Facebook, Instagram, TikTok, X, Vimeo সহ জনপ্রিয় সাইটের লিংক দিন।")
        raise HTTPException(422, "লিংক থেকে তথ্য বের করা যায়নি। লিংকটি সঠিক কিনা দেখুন।")

    heights = downloader.available_heights(info)
    picks = sorted({h for h in downloader.QUALITY_PRESETS if h in heights}, reverse=True)[:5]
    return {
        "title": info.title,
        "uploader": info.uploader,
        "duration": info.duration,
        "thumbnail": info.thumbnail,
        "webpage_url": info.webpage_url,
        "is_playlist": info.is_playlist,
        "entry_count": len(info.entries),
        "qualities": picks,
        "audio_bitrates": list(downloader.AUDIO_BITRATES),
    }


@app.post("/api/download")
async def start_download(req: DownloadRequest) -> dict[str, str]:
    url = downloader.extract_url(req.url) or req.url.strip()
    if not url.startswith("http"):
        raise HTTPException(400, "একটি বৈধ লিংক দিন।")
    job = Job(
        id=uuid.uuid4().hex[:12], url=url, quality=req.quality,
        audio_bitrate=req.audio_bitrate, subtitles=req.subtitles, playlist=req.playlist,
    )
    with _lock:
        _jobs[job.id] = job
    threading.Thread(target=_run_download, args=(job,), daemon=True).start()
    return {"job_id": job.id}


@app.post("/api/cancel/{job_id}")
async def cancel(job_id: str) -> dict[str, bool]:
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "job পাওয়া যায়নি")
    with _lock:
        job.cancel = True
    return {"cancelled": True}


@app.get("/api/progress/{job_id}")
async def progress(job_id: str) -> StreamingResponse:
    if job_id not in _jobs:
        raise HTTPException(404, "job পাওয়া যায়নি")

    async def stream() -> AsyncIterator[str]:
        last_payload = ""
        while True:
            with _lock:
                job = _jobs.get(job_id)
                data = _snapshot(job) if job else None
            if data is None:
                yield "event: error\ndata: {}\n\n"
                return
            payload = json.dumps(data, ensure_ascii=False)
            if payload != last_payload:
                yield f"data: {payload}\n\n"
                last_payload = payload
            if data["status"] in ("ready", "error", "cancelled"):
                return
            await asyncio.sleep(0.4)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/file/{job_id}")
async def get_file(job_id: str) -> FileResponse:
    job = _jobs.get(job_id)
    if not job or job.status != "ready" or not job.path:
        raise HTTPException(404, "ফাইল এখনো তৈরি হয়নি")
    path = Path(job.path)
    if not path.exists():
        raise HTTPException(410, "ফাইল মুছে গেছে (সময় শেষ)")
    return FileResponse(path, filename=job.filename)


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    return HTMLResponse((STATIC_DIR / "index.html").read_text(encoding="utf-8"))


@app.get("/manifest.webmanifest", include_in_schema=False)
async def manifest() -> FileResponse:
    return FileResponse(STATIC_DIR / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/icon.svg", include_in_schema=False)
async def icon() -> FileResponse:
    return FileResponse(STATIC_DIR / "icon.svg", media_type="image/svg+xml")


@app.get("/sw.js", include_in_schema=False)
async def service_worker() -> FileResponse:
    return FileResponse(STATIC_DIR / "sw.js", media_type="application/javascript")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "12000")))
