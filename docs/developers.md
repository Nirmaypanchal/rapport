# For developers

Rapport is small on purpose: a Python backend with no framework beyond FastAPI, a Next.js static UI, and a thin Tauri shell.
You can read the whole thing in an afternoon. This page is the map.

## Layout

```
rapport/                 Python backend
  main.py                dev entry: API + worker, opens the browser
  sidecar.py             desktop entry: token, READY handshake, parent watchdog
  server.py              FastAPI routes (the whole HTTP API)
  workerproc.py          worker process supervisor; heavy work runs here
  pipeline.py            one recording: convert → transcribe → diarize → match → save
  importer.py            devices, folders, connectors, Voice Memos, transcript imports
  transcribe.py          Whisper on MLX (progress via its tqdm hook)
  diarize.py             built-in diarizer (Silero + WeSpeaker + clustering) and pyannote wrapper
  speakers.py            voice embeddings, people matching, reset/re-match
  summarize.py           Ollama / MLX summaries and the prompt
  connectors.py          Granola, Omi, Notion (read-only)
  recorder.py            live recording via ffmpeg avfoundation
  voicememos.py          Apple Voice Memos database and files
  dji.py                 DJI and removable-volume detection, file-name parsing
  db.py                  SQLite schema, migrations, queries (FTS5 search)
  config.py              settings, library paths
frontend/                Next.js 16 app (static export), Tailwind v4, shadcn/ui on Base UI
desktop/sidecar/         PyInstaller spec and build script → rapport-core
desktop/app/             Tauri 2 shell (Rust), build script that assembles Rapport.app
site/                    landing page (single HTML file)
docs/                    this documentation
```

## Running for development

```bash
RAPPORT_LIBRARY=/tmp/rapport-dev ./run.sh      # API + worker on :8765 with a scratch library
cd frontend && npm run dev                      # UI with hot reload on :3000
```

The UI talks to the API through `NEXT_PUBLIC_API_BASE` (set in `frontend/.env.development`). CORS allows localhost:3000.

## The HTTP API

All routes are under `/api`, JSON, on 127.0.0.1. In the desktop app every call needs `Authorization: Bearer <token>`
(or `?token=` for media URLs). The most useful ones:

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/status` | importer/worker state, stats, settings |
| GET | `/api/recordings` | list with speakers |
| GET | `/api/recordings/{id}` | full recording: segments with word timings, speakers, peaks |
| PATCH | `/api/recordings/{id}` | title, notes |
| POST | `/api/recordings/{id}/reprocess` · `/summarize` | queue work |
| PATCH | `/api/recordings/{id}/segments/{sid}` | change speaker, person, or text of a turn |
| POST | `/api/recordings/{id}/segments/{sid}/split` · `/merge_prev` | edit turns |
| POST | `/api/recordings/{id}/speakers/{label}/assign` | link a speaker to a person |
| GET | `/api/recordings/{id}/audio` · `/original` · `/transcript.txt` · `/condensed` · `/speech` | media and derived data |
| GET/POST | `/api/people`, `/api/people/{id}`, `/merge/{other}`, `/api/people/reset` | people |
| GET | `/api/search?q=` | full-text search with snippets |
| GET/POST | `/api/sources`, `/api/sources/{name}/sync`, `/api/voicememos`, `/api/voicememos/import` | sources |
| POST | `/api/import/upload` (multipart) · `/api/import/path` | bring files in |
| POST | `/api/record/start` · `/api/record/stop` | live recording |
| GET/PUT | `/api/settings` | settings |

Read `rapport/server.py` for the complete list; every route is a few lines.

## Adding a source connector

A connector is one function that returns normalized items. Look at `rapport/connectors.py`:

```python
def my_service_items(api_key: str, known: set[str]) -> list[dict]:
    return [{
        "uid": "unique-id-in-that-service",
        "title": "Weekly sync",
        "recorded_at": "2026-09-08T14:09:00",     # ISO, local time, or None
        "duration_sec": 1810.0,                   # or None
        "segments": [{"speaker": "Me", "text": "…", "start": 0.0, "end": 4.2}],  # start/end optional
        "summary": "## Summary\n…",               # markdown or None
    }]
```

Then: add the key and auto flag to `Settings` in `config.py`, a branch in `Importer.sync_connector`, an entry in
`/api/sources`, and a tile in `frontend/src/components/sources-view.tsx`. Items without audio become text-only recordings;
if your service has audio, download it and call `importer.import_file()` instead.

Devices that mount as drives or save to folders need no code at all.

## Adding a summary provider or template

`rapport/summarize.py` holds the prompt (`SYSTEM`) and two providers. A new provider is a function
`(model, system, user) -> str`. Templates are a planned feature; today the prompt is fixed and easy to edit.

## Swapping models

- Whisper: any `mlx-community/whisper-*` repo in Settings.
- Speaker embeddings: `embedding_model` in settings (any pyannote-loadable embedding model; re-matching is needed after a change).
- Diarization: `diarizer = auto | pyannote | builtin`.
- Summaries: any Ollama model name, or an `mlx-community/*-Instruct-4bit` repo.

## Desktop app

```bash
desktop/sidecar/build.sh        # PyInstaller one-dir bundle with static ffmpeg → desktop/sidecar/dist/rapport-core
desktop/app/build.sh            # tauri build, then copies the core with symlinks intact → Rapport.app
desktop/app/build.sh --install  # also replaces /Applications/Rapport.app
```

Rust via rustup is required (`export PATH="$HOME/.cargo/bin:$PATH"`). The shell is about 100 lines in
`desktop/app/src-tauri/src/lib.rs`: spawn the sidecar with a token, wait for `READY <port>`, navigate the window there.
Keep it that thin; OS integration only.

Gotcha: Tauri's resource copier dereferences symlinks, which breaks MLX's Metal library lookup. `build.sh` handles it.

## Testing

```bash
scripts/test-light.sh                  # backend tests that need no models; runs on Linux too (this is what CI's ubuntu job runs)
uv run python -m pytest -q tests       # the same tests in the full environment (CI's macOS job)
scripts/e2e.py                         # macOS: real pipeline on a synthetic two-voice recording, about a minute with whisper-base
scripts/e2e.py --core desktop/sidecar/dist/rapport-core/rapport-core   # the same against a frozen sidecar
```

Tests live in `tests/` with fixtures in `tests/conftest.py` (a scratch library in a temp folder; your real library is never touched).
Keep new tests free of ML so they run everywhere; the pipeline is covered by `scripts/e2e.py`, which the sprint runs nightly on a Mac.

## The sprint

Rapport is developed by a continuous, mostly autonomous product sprint. `AGENTS.md` has the rules, `sprint/` has the board and
the logs. Branches named `sprint/*` are merged automatically when CI passes; use `draft/*` for anything that should wait for a person.

## Ideas that would be great contributions

- CUDA/Linux backend with faster-whisper.
- MCP server (`rapport/mcp.py`) exposing search, transcripts, summaries, and write-back for tags and summaries.
- Summary templates (meeting, interview, lecture, sales call) selectable per recording.
- Omi BLE streaming, Zoom/Meet local recording pickup, Obsidian export.
- A Homebrew cask, signed releases, an auto-updater.
