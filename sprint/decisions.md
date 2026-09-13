# Decisions

Newest first. One paragraph each: what, why, what it rules out.

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
