# Decisions

Newest first. One paragraph each: what, why, what it rules out.

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
