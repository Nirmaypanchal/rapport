# Backlog

Ordered. The Build agent takes the first unchecked item under **Now**. See [README.md](README.md) for conventions.

## Now (ready to build)

- [ ] **Ask: index the summaries too** — a question about what a meeting decided is often best answered by the summary that already says so, but only `segments` are in the FTS index, so Ask never sees one. _Why:_ found while building Ask; the retrieval is otherwise good and this is the obvious next gain. _Size:_ S.
  - Acceptance: summaries are searchable and can be cited as sources by Ask. Build's note: this means a second FTS index (or a `source` column on the existing one), migration in `rapport/db.py`, and a decision about what a "moment" is for a summary, which has no timestamp — the UI's citation jumps to a second in a recording.
- [ ] **Signed, notarized releases** — DMG that opens without right-click. _Why:_ the biggest install-time drop-off for any unsigned Mac app. _Size:_ M, blocked on the owner's Apple Developer credentials (see `needs-human/`).
  - Acceptance: `release.yml` signs with `APPLE_CERTIFICATE`/`APPLE_CERTIFICATE_PASSWORD`/`APPLE_ID`/`APPLE_TEAM_ID`/`APPLE_APP_PASSWORD` secrets when present and skips cleanly when absent; `docs/getting-started.md` updated.

## Next (needs a spec)

- [ ] **MCP server, slice 2: write-back** — an assistant can write a note, a tag or a summary back to a recording. _Why:_ slice 1 (read-only) shipped 2026-09-11; write-back is what turns Rapport into the assistant's memory rather than its library. _Size:_ M. **Needs a spec from Research:** what an assistant may write (a note appended to `notes`? a tag? a summary that replaces the one Rapport wrote?), and what the confirmation in the UI looks like — the decision on 2026-09-11 was that nothing writes without one. Build should not invent that flow.
  - Note from Build: the tool table and handler pattern are in `rapport/mcp.py`; a write tool is an entry in `TOOLS` plus a `tool_*` function, but `annotations.readOnlyHint` and the test `test_no_tool_writes_to_the_library` both have to be revisited deliberately, not quietly.
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
- [ ] **An `ask` tool for MCP** — the MCP `search` tool returns excerpts; `ask` would return the written answer too, which is one call to `rapport.ask.ask()` on top of what is already there. _Why:_ deliberately left out of slice 1 — the client is itself a model, so making it read the excerpts is usually better and always faster than making a local 3B model summarize them first. Worth doing only for clients that want a cheap local answer, or once people ask. _Size:_ S.
- [ ] **MCP: audio for the assistant** — no tool returns audio today, so an assistant cannot play or re-transcribe a moment, only read it. Needs a view on how a stdio server hands over a file (a path? a resource?). _Size:_ M.
- [ ] **Interactive model calls should run in the worker process** — Ask generates in the API process, so an MLX user loads the 2 GB model twice (once there, once in the worker). Ollama users pay nothing, since it is a separate app either way. Needs a request/response channel to the worker; today it only polls the database. _Why:_ found while building Ask. _Size:_ M.
- [ ] **Stream the answer while Ask is thinking** — a large Ollama model takes tens of seconds and the UI shows only a blinking dot. Both providers can stream. _Why:_ found while building Ask. _Size:_ S.
- [ ] **Make `sprint-merge` fail loudly** — drop the `|| true` after `gh pr create` (or assert a PR exists afterwards) so the workflow cannot report success having merged nothing. _Why:_ it silently swallowed "Actions is not permitted to create pull requests" twice on 2026-09-09; see `needs-human/2026-09-09-actions-cannot-open-prs.md`. _Size:_ S.
  - Note from Build 2026-09-12: `sprint-merge.yml` is now the last workflow with real logic in inline shell, which is exactly the shape of the bug fixed in [#11](https://github.com/Nirmaypanchal/rapport/pull/11) — untested `gh` plumbing that reports success while doing the wrong thing. Worth moving into `scripts/` beside `needs_human_issues.py` and testing the decision (open? merge? hold on `needs-human`?) rather than only dropping the `|| true`.
- [ ] **The nightly has not run since 2026-09-10** — no `sprint/log/*-nightly.md` for 09-11 or 09-12, so nothing since the MCP server has met the real pipeline and Release is holding the tag. Escalated on 2026-09-12 (`needs-human/2026-09-12-nightly-has-not-run.md`); nothing to build until the owner's Mac reports back. _Size:_ —, blocked on the owner.

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
- [x] Fix the end-to-end harness: `scripts/e2e.py` exited 0 without running anything (2026-09-11, [#9](https://github.com/Nirmaypanchal/rapport/pull/9))
- [x] MCP server, slice 1: six read-only tools over stdio, `rapport-core --mcp` (2026-09-11, [#10](https://github.com/Nirmaypanchal/rapport/pull/10))
- [x] File each escalation once: the dedupe check asks the list API and a marker, not the issue search index (2026-09-12, [#11](https://github.com/Nirmaypanchal/rapport/pull/11))
