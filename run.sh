#!/bin/zsh
# Start the DJI Mic Library app. First run installs everything (needs `uv`, `ffmpeg`, and `node` for the UI).
set -e
cd "$(dirname "$0")"
command -v uv >/dev/null 2>&1 || { echo "uv is required: brew install uv"; exit 1; }
command -v ffmpeg >/dev/null 2>&1 || { echo "ffmpeg is required: brew install ffmpeg"; exit 1; }
[ -d .venv ] || uv sync
# Build the Next.js UI once (or after `git pull`); the Python server serves frontend/out.
if command -v npm >/dev/null 2>&1 && [ -d frontend ]; then
  if [ ! -f frontend/out/index.html ] || [ -n "$(find frontend/src -newer frontend/out/index.html -type f 2>/dev/null | head -1)" ]; then
    echo "Building UI…"; (cd frontend && [ -d node_modules ] || npm install --no-audit --no-fund; npm run build >/dev/null)
  fi
fi
exec .venv/bin/python -m dji_mic_app.main "$@"
