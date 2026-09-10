# Backlog

Ordered. The Build agent takes the first unchecked item under **Now**. See [README.md](README.md) for conventions.

## Now (ready to build)

- [ ] **MCP server** — Claude, ChatGPT, Cursor and other MCP clients can search recordings, read transcripts and summaries, and write notes back. _Why:_ roadmap and landing page promise; differentiator no competitor has locally. _Size:_ L (split: read-only first).
  - Slice 1 acceptance: `rapport/mcp.py` exposing tools `search`, `get_recording`, `get_transcript`, `get_summary`, `list_people` over stdio; `uv run python -m rapport.mcp` works against the library folder; documented in `docs/integrations.md` with a Claude Desktop config snippet; tests with a fake library.
  - Note from Build (2026-09-10): `rapport/ask.py` now holds the retrieval half — `keywords`, `db.search(match="any")`, `pick_hits`, `passages`. An `ask` tool is one more line on top of it; do not write a second retriever.
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
- [ ] **Templates the user can edit in the app** — add, rename and edit a summary template from Settings, saved in the library folder. _Why:_ the shipped templates are read from `rapport/templates/` inside the app bundle, so today "custom" is one prompt and editing a built-in means editing the source. _Size:_ M.
- [ ] **Summary template per source** — a Granola sync is a meeting, a Voice Memo usually is not; default the template from where the recording came. _Why:_ noticed while building templates; would remove most of the picking. _Size:_ S.
- [ ] **Ask: index the summaries too** — a question about what a meeting decided is often best answered by the summary that already says so, but only `segments` are in the FTS index, so Ask never sees one. _Why:_ found while building Ask; the retrieval is otherwise good and this is the obvious next gain. _Size:_ S.
- [ ] **Interactive model calls should run in the worker process** — Ask generates in the API process, so an MLX user loads the 2 GB model twice (once there, once in the worker). Ollama users pay nothing, since it is a separate app either way. Needs a request/response channel to the worker; today it only polls the database. _Why:_ found while building Ask. _Size:_ M.
- [ ] **Stream the answer while Ask is thinking** — a large Ollama model takes tens of seconds and the UI shows only a blinking dot. Both providers can stream. _Why:_ found while building Ask. _Size:_ S.
- [ ] **Make `sprint-merge` fail loudly** — drop the `|| true` after `gh pr create` (or assert a PR exists afterwards) so the workflow cannot report success having merged nothing. _Why:_ it silently swallowed "Actions is not permitted to create pull requests" twice on 2026-09-09; see `needs-human/2026-09-09-actions-cannot-open-prs.md`. _Size:_ S.

## Later (ideas)

- Calendar and Contacts matching; Omi BLE streaming; iPhone companion; Windows/Linux backend; real-time captions.

## Done

- [x] Import from DJI Mic, USB recorders, mic/Bluetooth, Voice Memos, Omi, Granola, Notion, folders, files (2026-09-08)
- [x] On-device transcription, diarization, cross-recording speaker recognition, in-place corrections (2026-09-07)
- [x] Local summaries, search, skip silences, exports (2026-09-08)
- [x] Native macOS app, worker process, progress bars, Voice Memos picker, speaker reset (2026-09-09)
- [x] Open source: MIT, docs, community files, CI, release workflow (2026-09-09)
- [x] Sprint infrastructure: manual, board, tests, e2e, auto-merge, escalation (2026-09-09)
- [x] Summary templates: meeting, interview, lecture, sales call, journal, custom, per recording (2026-09-09, [#1](https://github.com/Nirmaypanchal/rapport/pull/1))
- [x] Ask your library: a question answered from your transcripts, every claim linked to the moment (2026-09-10, [#7](https://github.com/Nirmaypanchal/rapport/pull/7))
