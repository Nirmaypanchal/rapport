# Backlog

Ordered. The Build agent takes the first unchecked item under **Now**. See [README.md](README.md) for conventions.

## Now (ready to build)

> **Week 37 retro, 2026-09-13:** Now holds exactly one item and it is blocked on the owner, so the daily Build has nothing
> unblocked at the top of the board. Per `sprint/agents/build.md` step 2, a blocked Now is not a reason to stop: take the first
> specified item from Next — **Summary template per source** (S) is the one — and say so in the log. Research runs Monday and
> must leave seven unblocked Ready items here.

- [ ] **Signed, notarized releases** — DMG that opens without right-click. _Why:_ the biggest install-time drop-off for any unsigned Mac app. _Size:_ M, blocked on the owner's Apple Developer credentials (`needs-human/2026-09-13-apple-developer-credentials.md`, filed by the retro on 2026-09-13 — until then this item had pointed at an escalation that did not exist).
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
- [ ] **The Search page should find summaries too** — the index now holds every summary block ([#13](https://github.com/Nirmaypanchal/rapport/pull/13)) but only Ask looks at it; typing "pricing" into Search still searches turns only, and misses the summary that says it. _Why:_ the retrieval half is already built and tested, so this is a UI question, not a backend one. _Size:_ S. **Needs a view from Research/design:** the results list is a list of moments with a timestamp each, and a summary block has none — one mixed list with a "Summary" badge, or a second group under the moments? Build should not decide that alone. `db.search_summaries(q, match="all")` is the call; `/api/search` is the route.
- [ ] **Stream the answer while Ask is thinking** — a large Ollama model takes tens of seconds and the UI shows only a blinking dot. Both providers can stream. _Why:_ found while building Ask. _Size:_ S.
- [ ] **Make `sprint-merge` fail loudly** — drop the `|| true` after `gh pr create` (or assert a PR exists afterwards) so the workflow cannot report success having merged nothing. _Why:_ it silently swallowed "Actions is not permitted to create pull requests" twice on 2026-09-09; see `needs-human/2026-09-09-actions-cannot-open-prs.md`. _Size:_ S.
  - Note from Build 2026-09-12: `sprint-merge.yml` is now the last workflow with real logic in inline shell, which is exactly the shape of the bug fixed in [#11](https://github.com/Nirmaypanchal/rapport/pull/11) — untested `gh` plumbing that reports success while doing the wrong thing. Worth moving into `scripts/` beside `needs_human_issues.py` and testing the decision (open? merge? hold on `needs-human`?) rather than only dropping the `|| true`.
- [ ] **The nightly has not run since 2026-09-10** — no `sprint/log/*-nightly.md` for 09-11, 09-12 or 09-13, so nothing since the MCP server has met the real pipeline and Release is holding the tag. Escalated on 2026-09-12 (`needs-human/2026-09-12-nightly-has-not-run.md`); nothing to build until the owner's Mac reports back. _Size:_ —, blocked on the owner.
- [ ] **Notice when the nightly goes quiet** — a scheduled workflow that opens (or updates) one issue when the newest `sprint/log/*-nightly.md` is more than 48 hours old. _Why:_ a nightly that never starts leaves no log and no failure issue, so silence looked exactly like "nothing to report" for a day in week 37; it took an agent noticing an absence on day 2 and escalating on day 3 ([#12](https://github.com/Nirmaypanchal/rapport/issues/12)). Nothing in the loop detects it automatically, and the one machine that tests the real product is the one that can go quiet. _Size:_ S.
  - Acceptance: the decision lives in `scripts/nightly_watchdog.py` (stdlib only, a `main()`, a `--dry-run`) with the YAML as checkout plus one `run:` line, per the pattern `scripts/needs_human_issues.py` established; `tests/` covers "fresh log → nothing", "stale log → one issue", "stale log and the issue already exists → no second issue", "no logs at all → nothing, this is a new repo". Reuse the `<!-- needs-human-file: … -->` marker idea for dedupe, and ask the issue *list* API, never the search index. Daily cron is enough.
- [ ] **Stop CI leaving a red ghost run after every auto-merge** — `ci.yml`'s bare `pull_request:` trigger starts a second run when `sprint-merge` opens a PR, which dies when the PR squash-merges three seconds later: zero jobs, nothing run, permanently red in the history. _Why:_ four of the 17 CI runs in week 37 are these, every Build run pays attention to check the job count, and a run history where red means nothing is a history nobody reads. _Size:_ S.
  - Acceptance: same-repo `sprint/*` and `draft/*` branches are covered by the `push` trigger alone; PRs from forks (where `push` does not fire on this repo) still get CI. The guard is `if: github.event_name != 'pull_request' || github.event.pull_request.head.repo.full_name != github.repository` on each job, or an equivalent workflow-level condition — note that `pull_request: { branches: … }` filters the *base* branch, which is always `main`, so it cannot do this. Verify by opening one PR and checking no ghost appears.
- [ ] **Evaluate Parakeet on MLX beside Whisper** — `parakeet-mlx` runs NVIDIA's Parakeet transducer on Apple silicon; reports through 2026 put it at lower word error rate on clean English for a fraction of the compute, and it emits tokens as audio arrives, which Whisper cannot. _Why:_ transcription speed and bundle size are two of the three things anyone compares local note takers on, and this touches both — the frozen backend is 1.3 GB mostly because of torch ("Smaller bundle", below), and a streaming transducer is the only route to the "real-time captions" idea in Later. _Size:_ M for a measured comparison, not a swap. **Needs Research to size the move, not just the model**: whether it is an alternative engine the user picks, a replacement, or nothing yet. Evidence: [parakeet-mlx](https://lobehub.com/skills/openclaw-skills-parakeet-mlx), [Whisper vs Parakeet on MLX benchmarks](https://contracollective.com/blog/local-speech-to-text-whisper-parakeet-mlx-m5-max-2026), [Whisper → Parakeet on the Neural Engine](https://macparakeet.com/blog/whisper-to-parakeet-neural-engine/). Nothing here has been verified on the owner's Mac; treat the numbers as claims until it has.

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
- [x] Ask: index the summaries too — summaries are searchable block by block and cited as sources; a cited summary opens the recording's Summary tab, since a summary has no timestamp (2026-09-13, [#13](https://github.com/Nirmaypanchal/rapport/pull/13))
