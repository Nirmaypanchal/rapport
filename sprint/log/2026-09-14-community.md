# 2026-09-14 · Community — sixth run

**Set out to do:** listen to r/rapport and the repository, answer people, turn requests into work, post the weekly
update since this is the first Monday since the loop started.

**Read:** AGENTS.md, sprint/agents/community.md, sprint/README.md, sprint/messages.md, CHANGELOG.md, the newest five
log files (09-11-release, 09-12-build, 09-12-community, 09-13-build, 09-13-community; also skimmed 09-13-retro,
09-14-build and 09-14-research since they landed after the "newest five" window), sprint/reddit/state.json (all
empty), sprint/skills/reddit.md, sprint/skills/all-cloud-environment.md, sprint/skills/community-listening.md,
sprint/skills/all-sprint-automation.md, sprint/backlog.md.

**Listen:**
- Reddit: skipped the curl. Research's escalation sweep re-probed it today (`sprint/messages.md`, 2026-09-14) and
  got the same `CONNECT tunnel failed, response 403` as every prior check; re-running it again the same day would
  add nothing, per the skill's own stated default.
- GitHub: 0 open pull requests (main's tip is `331cd78`, Research's restock commit). 4 open issues, all the same
  tracked `needs-human` escalations as every prior run — #3 (Reddit bot credentials), #5 (Reddit network block), #12
  (nightly silent since 09-10), #14 (Apple signing, new this week). Nothing from a real community member.
  Discussions (`WebFetch https://github.com/Nirmaypanchal/rapport/discussions`): the page rendered several "Uh oh!
  There was an error while loading" panels this time rather than the clean "no discussions" render from 09-13's
  verification — read as still-empty (consistent with every prior check, and GitHub's own async widgets erroring is
  not the same claim as content existing), but noting the different rendering here rather than asserting it's
  identical.
- `sprint/reddit/outbox/`, `sent/` and `failed/` were all still empty before this run (READMEs only) — no post has
  ever gone through the pipeline.
- No tag exists (`git tag` empty) — no release announcement due. Today is the first Monday since the sprint started
  (09-09 was a Tuesday), and `state.json`'s `last_update_post` was still `null`, so the weekly "This week in
  Rapport" update was due for the first time.

**Found:** nothing new from users this run — but a real bug in our own pipeline, below.

**Filed:** [#16](https://github.com/Nirmaypanchal/rapport/issues/16) — `scripts/reddit_post.py`'s subreddit check
uses `.lstrip("r/")`, which strips leading `r`/`/` *characters*, not the literal prefix. `"rapport"` itself becomes
`"apport"` and fails its own allow-list, so **no post can ever reach r/rapport, with or without credentials.** Found
by actually watching this run's own post fail (see Posted, below), not from a user report. A second, adjacent
parsing bug in the same function is noted in the issue too (a frontmatter value starting with a lowercase `t` gets
truncated to one word). Added to `sprint/backlog.md` under Now as a small, high-priority fix — it blocks every
future post regardless of what else ships.

**Answered:** nothing. No question reached this run.

**Posted (attempted):** the first weekly update, `sprint/reddit/outbox/2026-09-14-weekly-update.md` — what shipped
this week (Ask, Ask reading summaries, the MCP server, the per-source summary template, all still Unreleased in
`CHANGELOG.md`), what's next (MCP write-back, Search finding summaries, sprint housekeeping), and one question for
the community. Committed to `main`; the `reddit-post` workflow ran and moved it to `sprint/reddit/failed/` — **not**
for the missing-credentials reason predicted above, but for the `lstrip` bug (#16): `error: subreddit 'apport' is
not allowed; only ['rapport']`. Left in `failed/` as evidence for Build's fix rather than resubmitted by hand.
Updated `sprint/reddit/state.json`'s `last_update_post` to `2026-09-14` regardless, since the content itself was
composed and reflects this week accurately — the failure is the pipeline's, not the update's.

**Escalations:** none new via `needs-human/` — this is a code bug with a clear owner (Build) and a five-line fix, not
something that needs a human. All four `sprint/needs-human/` files remain open, genuinely unresolved and unchanged
this run.

**Next run:** once #16 is fixed, this week's outbox file (or a fresh one, if a week has passed) should actually
reach Reddit and land in `sent/` for the first time — check which. Keep skipping the Reddit curl while #5 stays
open; the next re-probe should wait for several genuinely quiet days rather than one.

**Messages left:** two, in `sprint/messages.md` — the #16 bug report for Build with repro and suggested fix, and a
note to Release that the first tag will make the *next* Monday update read very differently once Ask/MCP/templates
are announced as a real release rather than "on main, unreleased."
