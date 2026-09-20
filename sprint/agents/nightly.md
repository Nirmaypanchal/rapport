# Nightly on-device QA

Runs on the owner's Mac as a local scheduled task (its prompt is stored on that Mac, not here). It clones the repository to
`~/.rapport-sprint/repo`, checks out main, runs `uv sync`, builds the UI, runs `pytest`, runs `scripts/e2e.py` against the real
pipeline, builds the sidecar and the app, runs `scripts/e2e.py --core …` against the frozen core, writes
`sprint/log/YYYY-MM-DD-nightly.md`, and opens an issue labeled `sprint,bug` on failure. It never touches the owner's real library
or /Applications/Rapport.app. The other agents read its log: Build fixes failures first; Release does not ship on a red nightly
(unless the gate has expired — see `sprint/agents/release.md` step 1).

When it runs, two things are worth more than another green pytest line, because nothing else in the loop can do them:

- **Drive a real `tools/call` against the installed `rapport-core --mcp` binary**, not the pytest suite. The MCP server has
  never been touched by a real client; Build flagged that as the one open gap on [#10](https://github.com/Nirmaypanchal/rapport/pull/10).
  A Claude Desktop handshake is better still.
- **Read a summary a real local model actually wrote.** Summary templates, Ask, and the summary index all shipped against
  synthetic text. `summarize.split_summary()` in particular guesses at what small models emit (`**Decisions**` as well as
  `## Decisions`); the first real one it meets will be on that Mac.

**Silence is a failure mode of its own.** A run that never starts leaves no log and no issue, and looked identical to "nothing
to report" for a day in week 37 (last run 2026-09-10; escalated on 09-12 as
[#12](https://github.com/Nirmaypanchal/rapport/issues/12) after Build noticed the absence). `nightly-watchdog.yml` now files
one issue after 48 silent hours and closes it when a log lands, so nobody has to remember to look.

**When this task is silent, these are the things to check first** (it is a Desktop scheduled task on the owner's Mac, per
[the docs](https://code.claude.com/docs/en/desktop-scheduled-tasks); a cloud agent cannot see any of them):

1. Is the task still **enabled**? Open the Desktop app → Code → Routines and look at its last run and status.
2. Did the runs happen and **do nothing**? A green run means the session started and exited, not that the task succeeded —
   open the run and read the transcript.
3. Is the **GitHub connection** live? A routine whose GitHub access has expired skips runs for up to 72 hours and then turns
   itself off; reconnecting inside that window resumes it, after it the owner must switch it back on.
4. Was the **daily run cap** or the subscription limit reached? Runs past the cap are rejected, silently as far as this
   repository can tell. Check `claude.ai/settings/usage`.

None of this is diagnosed: the task went quiet after 2026-09-10 and no one has looked. Whichever it was, say so in the first
log after it comes back, so the next silence is diagnosed in a minute instead of a fortnight.

## Changelog

- 2026-09-20 (retro, week 38): four named things to check when this task is silent, and an instruction to say which one it was
  in the first log after it returns. Eleven silent nights and nobody has a theory; "start it again" is not a diagnosis.
- 2026-09-13 (retro, week 37): named the two things only this machine can do (a real MCP `tools/call`, a real model's summary),
  and recorded that silence is indistinguishable from idleness without a watchdog. Its single run on 09-10 found the
  `scripts/e2e.py` bug that every Linux test and CI run was structurally incapable of finding; it then went quiet for three nights.
- 2026-09-09: created (interactive bootstrap session).
