#!/usr/bin/env bash
# VidSave: ensure deps + server are running. Safe to run repeatedly.
cd "$(dirname "$0")"

if ! python3 -c "import fastapi, uvicorn, yt_dlp" >/dev/null 2>&1; then
  echo "[vidsave] installing dependencies..."
  pip install -q -r requirements.txt || exit 1
fi

if curl -s -o /dev/null --max-time 3 "http://127.0.0.1:${PORT:-12000}/"; then
  echo "[vidsave] server already running on :${PORT:-12000}"
  exit 0
fi

echo "[vidsave] starting server on :${PORT:-12000}"
setsid nohup python3 webapp.py > /tmp/vidsave.log 2>&1 < /dev/null &
disown
sleep 4
curl -s -o /dev/null -w "[vidsave] local=%{http_code}\n" "http://127.0.0.1:${PORT:-12000}/" --max-time 8
