"""Web app for the media downloader: paste a link, pick quality, download.

Serves a small single-page UI and exposes a JSON/SSE API backed by the same
yt-dlp wrapper used by the Telegram bot (see downloader.py).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
import uuid
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

_sem = threading.Semaphore(MAX_CONCURRENT)
_lock = threading.Lock()
_jobs: dict[str, "Job"] = {}


@dataclass
class Job:
    id: str
    url: str
    quality: str
    status: str = "queued"  # queued|downloading|ready|error
    progress: float = 0.0
    speed: str = ""
    eta: str = ""
    title: str = ""
    filename: str = ""
    path: str = ""
    error: str = ""
    created: float = field(default_factory=time.time)


class ProbeRequest(BaseModel):
    url: str


class DownloadRequest(BaseModel):
    url: str
    quality: str = "best"  # "best" | "audio" | a height like "1080"


def _parse_quality(quality: str) -> tuple[int | None, bool]:
    if quality == "audio":
        return None, True
    if quality in ("best", "", None):
        return None, False
    return int(quality), False


def _snapshot(job: Job) -> dict[str, Any]:
    data = asdict(job)
    data.pop("path", None)
    data["ready"] = job.status == "ready"
    return data


def _run_download(job: Job) -> None:
    """Worker thread: download the media and update the job as it goes."""
    height, audio_only = _parse_quality(job.quality)
    tmp = downloader.make_temp_dir()
    last = [0.0]

    def hook(d: dict) -> None:
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

    try:
        with _sem:
            with _lock:
                job.status = "downloading"
            path = downloader.download(
                job.url, tmp, height=height, audio_only=audio_only, progress_hook=hook
            )
        with _lock:
            job.path = str(path)
            job.filename = path.name
            job.progress = 100.0
            job.status = "ready"
    except Exception as exc:  # noqa: BLE001 - report any failure to the client
        log.warning("download failed for %s: %s", job.url, exc)
        with _lock:
            job.status = "error"
            job.error = f"{type(exc).__name__}: {exc}"
        downloader.cleanup(tmp)


@app.post("/api/probe")
async def probe(req: ProbeRequest) -> dict[str, Any]:
    url = downloader.extract_url(req.url) or req.url.strip()
    if not url.startswith("http"):
        raise HTTPException(400, "একটি বৈধ লিংক দিন।")
    try:
        info = await asyncio.wait_for(asyncio.to_thread(downloader.probe, url), timeout=120)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(422, f"লিংক থেকে তথ্য বের করা যায়নি: {type(exc).__name__}")

    heights = downloader.available_heights(info)
    picks = sorted({h for h in (2160, 1440, 1080, 720, 480, 360, 240) if h in heights},
                   reverse=True)[:5]
    return {
        "title": info.title,
        "uploader": info.uploader,
        "duration": info.duration,
        "thumbnail": info.thumbnail,
        "webpage_url": info.webpage_url,
        "qualities": picks,
    }


@app.post("/api/download")
async def start_download(req: DownloadRequest) -> dict[str, str]:
    url = downloader.extract_url(req.url) or req.url.strip()
    if not url.startswith("http"):
        raise HTTPException(400, "একটি বৈধ লিংক দিন।")
    job = Job(id=uuid.uuid4().hex[:12], url=url, quality=req.quality)
    with _lock:
        _jobs[job.id] = job
    threading.Thread(target=_run_download, args=(job,), daemon=True).start()
    return {"job_id": job.id}


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
            if data["status"] in ("ready", "error"):
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "12000")))
