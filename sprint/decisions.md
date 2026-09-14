# Decisions

Newest first. One paragraph each: what, why, what it rules out.

- **2026-09-14 · A source is the place, and the `source` column stays the mechanism.** The Sources page names tiles by
  where a recording came from (`icloud`, `dropbox`, `googledrive`, plus a generic `folder`); the `recording.source`
  column names the *mechanism* Rapport used to get it (`folder`, `usb`, `microphone`, `file`, `voicememos`, …), which
  is what import dedup and connector logic need and must not change. The fix is not to rename the column; it's to
  resolve the *place* only where the user actually chooses one — `summary_template_by_source`, the Settings picker,
  and the Sources page counts — the same way `server.py`'s `/api/fs/roots` already resolves iCloud/Dropbox/Google
  Drive from a folder path, and the same way `sources-view.tsx`'s `rootOf`/`watching` already do it client-side for
  the page it was built for. A `folder`-sourced recording's `source_volume` already holds the exact watched path
  (`importer.py`), so nothing new needs storing — a lookup was always possible, just not written. Backend gains one
  small helper that maps `(source, source_volume)` to the place-level id (`icloud`/`dropbox`/`googledrive`/`folder`
  for folders, and the existing 1:1 names — `mic` for `microphone`, `files` for `file` — for everything else) using
  the same roots list `/api/fs/roots` returns, and every place that offers a per-source choice to a user calls that
  helper instead of reading `source` raw. Rules out: renaming or migrating the `source` column, and exposing the
  tile's naming inconsistency (`mic`/`microphone`, `files`/`file`) to the database schema. See the Ready spec in
  `backlog.md`.
- **2026-09-14 · Search results mix moments and summaries in one list, led by summaries, not two groups.** Mobbin
  precedent (Dropbox Dash's omnibox, Tana's unified library table) shows mixed-type result lists using an inline
  badge per row rather than splitting into separate sections — readers scan one list, not two. Rapport already
  solved this exact rendering problem for Ask (`ask-panel.tsx`'s `Source` component: a `FileText` icon and "Summary"
  badge for a summary excerpt, opening the recording's Summary tab instead of a timestamp), so Search reuses that
  same visual language rather than inventing a second one. Because a summary's bm25 score and a turn's bm25 score
  come from two different FTS tables and are not comparable, results are not merged onto one fake combined
  relevance rank: summary hits (capped, since a summary is denser evidence per the reasoning already written in
  `ask.py`) lead the list, moment hits fill the rest, and there is no section header — exactly one list. Rules out:
  a second tab or a visually separate "Summaries" panel, and pretending the two bm25 scores are on the same scale.
- **2026-09-14 · MCP write-back, slice 2: a note appended to a recording, confirmed per write, nothing else yet.**
  Answering Build's queued question (`messages.md`, 2026-09-11): the first writable thing is the smallest one
  already in the schema — appending to `recordings.notes` — not a tag (people/tag data model isn't settled) and not
  a summary (overwriting the summary Rapport wrote is a bigger, separate decision about trust in an assistant's
  words vs. the local model's). Every write is one tool call, one recording, one appended note; there is no bulk or
  "write to every recording matching X" tool. The confirmation lives where confirmations already live in this app —
  a native macOS dialog-style prompt via the same mechanism `useConfirm()` uses in the frontend is not reachable
  from a stdio MCP process with no UI of its own, so the confirmation must be a toast/notification the app raises
  when it sees a new note appear from an MCP write (distinguishable from a user-typed note by a source marker on the
  note, e.g. a `[via <client name>]` prefix or a dedicated column), not a blocking prompt the assistant waits on —
  MCP's hand-rolled server here has no elicitation support to block on (see the 2026-09-11 "hand-written, not an SDK"
  decision). Rules out: a write tool for tags or summaries in this slice, and any write tool that is not scoped to
  one recording by id. See the Ready spec in `backlog.md`; `test_no_tool_writes_to_the_library` becomes
  `test_only_notes_tool_writes_to_the_library` or equivalent, not deleted.
- **2026-09-14 · WhisperKit + SpeakerKit (the Swift diarization SDK) is not adopted, pending a real architecture
  decision.** Argmax shipped diarization inside the same Swift package as its Whisper engine; Rapport's diarizer does
  the same job in Python. Swapping it in either means a second Swift helper process alongside the Python backend
  (real IPC and packaging complexity) or reopening "Python backend, no ORM" (`AGENTS.md`, `sprint/decisions.md`
  2026-09-11 MCP entry references the same weight-budget reasoning). Neither is a Ready backlog item; both are the
  kind of call this file exists to record before anyone builds against it. See `sprint/research/trends.md`.
- **2026-09-13 · The nightly release gate expires after seven silent days.** Release still may not ship on a nightly that
  ran and failed — that part is absolute. But when the newest `sprint/log/*-nightly.md` is more than a week old, the machine
  is not reporting rather than failing, and a gate with no timeout is a gate that can close forever: week 37 ended with three
  user-visible features unreleased, no tag ever cut, and the landing page's three Download buttons pointing at an empty
  `/releases` page. From now on Release may tag a 0.x release in that case if macOS CI is green on the exact commit, an open
  `needs-human` issue already tracks the silent nightly, and the changelog and GitHub Release body say plainly that the
  on-device end-to-end test has not run since a named date. Reason: shipping unverified and saying so is honest; never
  shipping is not a safety property. Ruled out: using this to route around a red nightly, and using it above 0.x.
- **2026-09-13 · A weekly agent may not own a daily unblock.** Research now leaves seven unblocked Ready items rather than
  three (Build takes one a day and Research runs weekly — three days of work is starvation by Saturday, which is what
  happened), Build falls through to the first specified item in Next rather than starving on a blocked Now, and an agent
  that can prove an escalation is resolved closes it with the evidence instead of queueing a note for Research. Issue #2
  was resolved in fact on 2026-09-10 and sat open four days while three runs pointed at it. Ruled out: an agent closing an
  escalation it cannot verify — that stays the owner's, untouched. The Escalation section of AGENTS.md is unchanged; it
  assigns the file move to Research and describes the owner closing issues, and does not say the owner is the only one who may.
- **2026-09-11 · The MCP server is hand-written, not an SDK.** `rapport/mcp.py` implements the protocol's stdio transport
  (JSON-RPC 2.0, one message per line) in the standard library: `initialize`, `tools/list`, `tools/call` and
  notifications is the whole surface a read-only tool server needs, about 90 lines. Reason: the frozen backend is already
  1.3 GB and shrinking it is on the backlog, so a dependency has to earn its place, and this one would have bought
  request plumbing we can read in one sitting. Ruled out for now: resources, prompts, sampling, progress and
  cancellation, all of which an SDK would have given us free — if we want any of them, revisit this rather than
  hand-roll further. Also decided: the server reads SQLite directly instead of calling the local HTTP API, so it needs
  no port, no token and no running app.
- **2026-09-11 · An assistant reads, it does not write.** Every MCP tool in slice one is read-only, and a test asserts the
  database is unchanged after all of them run. Reason: "user data is sacred" means a confused or hostile client must not
  be able to lose someone's recordings, and MCP clients are driven by models reading text from the internet. Write-back
  ships when there is a confirmation in the UI behind it.
- **2026-09-09 · Agents merge their own work.** Branches named `sprint/*` are merged by GitHub Actions when CI is green.
  Reason: the owner asked for an autonomous loop and is emailed only for things a human must do. Ruled out: waiting for
  human review on every PR. Safety comes from guardrails in AGENTS.md, tests, the nightly on-device test, and the fact that
  releases are cut only weekly from a tag.
- **2026-09-09 · Escalations are files, not emails.** Agents write `sprint/needs-human/*.md`; an Action opens an issue
  assigned to the owner, and GitHub emails it. Reason: the cloud agents have no mail connector; GitHub notifications are
  reliable and leave a record. Ruled out: agents sending email directly.
- **2026-09-09 · Cloud agents cannot run the pipeline.** They run on Linux without Metal. Backend tests that need no ML
  run everywhere (`scripts/test-light.sh`); the pipeline, the desktop build and `scripts/e2e.py` run on macOS in CI and nightly on the owner's Mac.
- **2026-09-09 · Public posting is human-only.** Agents draft in `sprint/marketing/`; the owner posts. Reason: reputation.
- **2026-09-08 · Copy-only imports by default.** Devices are never cleared unless the user turns it on.
- **2026-09-08 · Worker runs in a separate process.** The GIL made the UI freeze during transcription.
- **2026-09-08 · Tauri 2 over Electron.** 10 MB shell instead of 200 MB; the weight is in the Python sidecar anyway.
- **2026-09-07 · Built-in diarizer first, pyannote optional.** pyannote's pipeline is gated on Hugging Face; the built-in
  Silero + WeSpeaker + clustering engine works with no account and is good for 1 to 4 clean voices.
