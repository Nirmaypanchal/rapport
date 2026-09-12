# Start the nightly on-device QA task on your Mac again — it has not run since 2026-09-10

**Why:** the nightly on your Mac is the only thing in the whole loop that ever runs the real pipeline: Whisper on
MLX, diarization, the frozen sidecar, the actual app bundle. Everything else — cloud agents and GitHub Actions
alike — runs on Linux or without models. The last one was `sprint/log/2026-09-10-nightly.md` (committed 2026-09-10
15:49, and its verdict was FAIL, on a harness bug that has since been fixed in
[#9](https://github.com/Nirmaypanchal/rapport/pull/9)). There is no log for 09-11 or 09-12, and no failure issue
either, which is what a run that starts and dies would leave behind — so it looks like the task is not starting at
all rather than failing. Meanwhile `main` has gained the MCP server and the Ask feature, and Release deliberately
held the 0.2.0 tag on 2026-09-11 because its checklist requires a green nightly
(`sprint/skills/release-checklist.md`). Until that Mac reports back, nothing ships, and the agents are writing code
that no one has run end to end.

**What to do:**

1. On your Mac, check that the nightly scheduled task still exists and is enabled — it is the local task whose prompt
   lives on that machine (see `sprint/agents/nightly.md`), not a GitHub Action, so nothing here can restart it.
2. Confirm the Mac is awake at the scheduled hour, or move the schedule to a time it reliably is. A sleeping or
   powered-off Mac produces exactly what we see: no log, no issue, no trace.
3. Run it once by hand now against current `main` so the release is unblocked:
   ```bash
   cd ~/.rapport-sprint/repo && git fetch origin main && git checkout -B main origin/main
   uv sync && ./scripts/e2e.py
   ```
   Exit 0 with a `## e2e OK` block is a pass. If it passes, the commit that matters is `8bfca45` or later.
4. If the task itself is gone, recreate it from `sprint/agents/nightly.md`, which lists every step it should run.
5. Useful when you do: nobody has ever connected a real MCP client to `rapport-core --mcp`; none can run in the
   cloud. A single `tools/call` from Claude Desktop on your Mac would close that gap.

**Blocked:** the 0.2.0 release (Release is holding the tag on this), and confidence in everything merged since
2026-09-10 — the MCP server ([#10](https://github.com/Nirmaypanchal/rapport/pull/10)) and Ask
([#7](https://github.com/Nirmaypanchal/rapport/pull/7)) have never run against the real pipeline on a Mac.
