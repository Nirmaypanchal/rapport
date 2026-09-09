# Backlog

Ordered. The Build agent takes the first unchecked item under **Now**. See [README.md](README.md) for conventions.

## Now (ready to build)

- [ ] **Summary templates** — pick Meeting notes, Interview, Lecture, Sales call, Journal or a custom prompt per recording. _Why:_ roadmap; every competitor (Granola, Otter, MacWhisper) ships templates and it is the most requested feature in this category. _Size:_ M.
  - Story: as a user I choose what kind of recording this was and get a summary shaped for it.
  - Acceptance: a `summary_template` per recording (default from settings); templates live in `rapport/templates/*.md` with a name, description and prompt; the Summary tab shows a template picker and "Regenerate"; custom prompt saved in settings; existing summaries untouched until regenerated; tests cover template loading and prompt assembly.
  - UI: a small select in the Summary tab header, Cue Sheet styling; picker also in Settings under Summaries.
  - Files: `rapport/summarize.py`, `rapport/db.py` (column + migration), `rapport/server.py`, `frontend/src/components/recordings/summary-tab.tsx`, `frontend/src/components/settings-view.tsx`, `docs/how-it-works.md`.
- [ ] **Ask your library (local RAG-lite)** — a question box on the Search page that answers from transcript snippets using the local model, with the moments linked. _Why:_ roadmap "Later" but the landing page promises a second brain; the MCP server below needs the same retrieval. _Size:_ M.
  - Acceptance: `POST /api/ask {q}` returns `{answer, sources:[{recording_id,start,snippet}]}` built from FTS top hits plus the local model; UI shows the answer with clickable sources; works when no model is available by returning sources only; tests for retrieval assembly.
- [ ] **MCP server** — Claude, ChatGPT, Cursor and other MCP clients can search recordings, read transcripts and summaries, and write notes back. _Why:_ roadmap and landing page promise; differentiator no competitor has locally. _Size:_ L (split: read-only first).
  - Slice 1 acceptance: `rapport/mcp.py` exposing tools `search`, `get_recording`, `get_transcript`, `get_summary`, `list_people` over stdio; `uv run python -m rapport.mcp` works against the library folder; documented in `docs/integrations.md` with a Claude Desktop config snippet; tests with a fake library.
- [ ] **Signed, notarized releases** — DMG that opens without right-click. _Why:_ the biggest install-time drop-off for any unsigned Mac app. _Size:_ M, blocked on the owner's Apple Developer credentials (see `needs-human/`).
  - Acceptance: `release.yml` signs with `APPLE_CERTIFICATE`/`APPLE_CERTIFICATE_PASSWORD`/`APPLE_ID`/`APPLE_TEAM_ID`/`APPLE_APP_PASSWORD` secrets when present and skips cleanly when absent; `docs/getting-started.md` updated.

## Next (needs a spec)

- [ ] **People memory** — facts people mention (extracted locally) filed under the person with date and source. _Why:_ roadmap headline. _Size:_ L.
- [ ] **Connector verification** — Granola, Omi and Notion sync have never been run against real APIs. Needs recorded fixtures or the owner's keys. _Size:_ M.
- [ ] **Smaller bundle** — the frozen backend is 1.3 GB, mostly torch; move speaker embeddings to MLX. _Size:_ L.
- [ ] **Auto-updater** — Tauri updater fed by GitHub Releases; depends on signing. _Size:_ M.
- [ ] **Homebrew cask** — after the first signed release. _Size:_ S.
- [ ] **Zoom / Google Meet local recordings** — watch their default folders. _Size:_ S.
- [ ] **Obsidian and Markdown export of the whole library** — one folder of `.md` per recording. _Size:_ S.
- [ ] **Onboarding** — first-run screen that picks sources and explains the model download. _Size:_ M.

## Later (ideas)

- Calendar and Contacts matching; Omi BLE streaming; iPhone companion; Windows/Linux backend; real-time captions.

## Done

- [x] Import from DJI Mic, USB recorders, mic/Bluetooth, Voice Memos, Omi, Granola, Notion, folders, files (2026-09-08)
- [x] On-device transcription, diarization, cross-recording speaker recognition, in-place corrections (2026-09-07)
- [x] Local summaries, search, skip silences, exports (2026-09-08)
- [x] Native macOS app, worker process, progress bars, Voice Memos picker, speaker reset (2026-09-09)
- [x] Open source: MIT, docs, community files, CI, release workflow (2026-09-09)
- [x] Sprint infrastructure: manual, board, tests, e2e, auto-merge, escalation (2026-09-09)
