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
  summarize.py           Ollama / MLX summaries, the templates, splitting a summary into citable blocks, `chat()`
  ask.py                 Ask your library: FTS retrieval over turns and summaries, excerpts, the prompt, citations
  mcp.py                 MCP server over stdio (read-only): search, recordings, transcripts, summaries, people
  connectors.py          Granola, Omi, Notion (read-only)
  recorder.py            live recording via ffmpeg avfoundation
  voicememos.py          Apple Voice Memos database and files
  dji.py                 DJI and removable-volume detection, file-name parsing
  db.py                  SQLite schema, migrations, queries (FTS5 over turns and summary blocks)
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
| POST | `/api/ask` | `{q}` → `{answer, sources, model, reason}`: retrieval plus the local model |
| GET/POST | `/api/sources`, `/api/sources/{name}/sync`, `/api/voicememos`, `/api/voicememos/import` | sources |
| POST | `/api/import/upload` (multipart) · `/api/import/path` | bring files in |
| POST | `/api/record/start` · `/api/record/stop` | live recording |
| GET/PUT | `/api/settings` | settings |

Read `rapport/server.py` for the complete list; every route is a few lines.

## The MCP server

`rapport/mcp.py` is a second, separate way in: an MCP client (Claude Desktop, Cursor, anything that speaks the
protocol) starts it as a child process and talks JSON-RPC 2.0 over stdio, one message per line. It opens the SQLite
library directly, so it needs no HTTP server, no token and no port, and it works whether or not the app is running.

```bash
uv run python -m rapport.mcp --library ~/Rapport   # from a checkout
rapport-core --mcp                                 # the same code, from the frozen app
```

- The protocol is implemented in the standard library — `initialize`, `tools/list`, `tools/call`, and notifications,
  which is all a tool server needs. No SDK, so the 1.3 GB bundle does not grow (`sprint/decisions.md`).
- **Every tool is read-only.** No handler writes, and `tests/test_mcp.py` asserts that every table is unchanged after
  all of them have run. Keep it that way until write-back ships with a confirmation in the UI.
- A new tool is an entry in `TOOLS` (name, description, JSON Schema) and a `tool_*` function in `HANDLERS`; the two
  are checked against each other by a test. Handlers return a plain dict and raise `ToolError` for anything the
  caller got wrong — that comes back as a failed tool result the model can read, not a protocol error.
- Retrieval is not duplicated: `search` is `rapport/ask.py`'s keyword extraction and `retrieve()` in an MCP
  envelope. Fix retrieval there and both features improve. Its results carry a `kind`: a `moment` has a timestamp,
  a `summary` block does not.
- **Nothing but protocol may be written to stdout** (`print(..., file=sys.stderr)` for anything else), or the client
  will see a parse error and drop the connection.

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

`rapport/summarize.py` holds the shared rules (`PREAMBLE`) and two providers. A new provider is a function
`(model, system, user) -> str` dispatched from `chat()`. Summaries and Ask both go through `chat()`, so one
provider serves both.

A template is one Markdown file in `rapport/templates/`. The file name is its id; the front matter names it and the body
is appended to `PREAMBLE` to make the system prompt:

```markdown
---
name: Stand-up
description: Yesterday, today, blockers.
order: 60
---
Output Markdown with exactly these sections:
## Yesterday
…
```

Whatever shape a template asks for, keep the summary in Markdown blocks — headings, bullets, paragraphs.
`split_summary()` cuts it there, and `db.index_summary()` (called from `insert_recording`/`update_recording`, so no
writer has to remember) stores the blocks in `summary_chunks` for Ask and the MCP `search` tool to cite. A summary
written as one 5,000-character wall still works: blocks longer than `MAX_BLOCK_CHARS` are cut on sentence ends.

Drop the file in and it appears in the Summary tab and in Settings; nothing else to register. A recording remembers the
template it was summarized with in `recordings.summary_template`, and users can write their own prompt instead
(the `custom` template, stored in settings). The files are read from disk at runtime; the PyInstaller spec copies the
whole folder into the frozen sidecar, so a new template needs no packaging change.

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

When an agent needs a human it writes a file in `sprint/needs-human/`, and `scripts/needs_human_issues.py` (run by the
`Needs human` workflow on every push and every six hours) opens one issue per file, assigned to the owner. It recognises the
issues it has already opened by a `<!-- needs-human-file: … -->` marker in the body, so a file is never filed twice however
often the cron runs. Try it with `scripts/needs_human_issues.py --dry-run`.

## Ideas that would be great contributions

- CUDA/Linux backend with faster-whisper.
- MCP write-back: `rapport/mcp.py` reads today; letting an assistant add a note, a tag or a summary is the next slice.
- Omi BLE streaming, Zoom/Meet local recording pickup, Obsidian export.
- A Homebrew cask, signed releases, an auto-updater.
