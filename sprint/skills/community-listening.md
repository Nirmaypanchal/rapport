# Listening from the cloud: what is reachable and what is not (Last verified: 2026-09-13, retro week 37)

The order to check things in, cheapest and most informative first. Everything here was run from a cloud session on the
date above.

## 1. Issues and pull requests — GitHub MCP tools

`mcp__github__list_issues` and `mcp__github__list_pull_requests` work without `gh` and without a token of your own. Pass
`fields` to keep the response small (`["number","title","state","labels","created_at","updated_at","comments"]`); the
default includes bodies and will blow up a context window on a busy repo. `state: "all"` matters for anything that asks
"has this already been filed" — a closed issue still counts.

Week 37's only real community finding came from reading the issue *list* and noticing #3 and #6 were the same request
filed three hours apart. Nothing in CI could have caught that. Read the list, don't just search it.

## 2. Discussions — WebFetch, not `gh`

```
WebFetch https://github.com/Nirmaypanchal/rapport/discussions
```

**This works.** No MCP tool exposes the Discussions API and `gh` is not authenticated here, and five Community runs in
week 37 concluded from that that Discussions were unverifiable — each log said "unverified, not assumed empty". One
WebFetch call disproved it (result: genuinely empty, which is a fact rather than a gap). The public HTML renders fine
for reading threads, titles, authors and reply counts. To *reply*, you still need the GitHub tools or the owner.

The general lesson, worth more than the specific call: when the API is closed, the public web page usually is not. Try
it once before writing "cannot be checked" in a log for the fifth time.

## 3. Reddit — blocked at the network layer

See `sprint/skills/reddit.md`. Short version: the cloud session's network policy rejects every reddit.com CONNECT, this
is not something a User-Agent or a retry fixes, and the escalation is open. Check that the escalation file still exists
rather than re-running the curl.

## 4. Anything else on the public web

WebFetch and WebSearch both work normally (Hacker News, competitor changelogs, App Store pages). Reddit is the specific
domain the policy blocks, not the open web in general — so a Reddit thread quoted on another site is still readable.

## When the answer is "nothing happened"

That is a legitimate result and it should cost three lines, not a page. `sprint/agents/community.md` now has a
quiet-run fast path: say what you checked, that it was quiet, and what would change that. Do not restate the standing
blocks or re-flag what the previous run already flagged — week 37 produced five near-identical logs and one finding.
If you flag the same thing into `sprint/messages.md` for a third run running, that is a signal the queue has no
consumer: raise it as its own item rather than repeating the note.
