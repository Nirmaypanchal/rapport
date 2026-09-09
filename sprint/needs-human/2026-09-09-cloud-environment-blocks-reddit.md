# Allow the cloud environment's network policy to reach reddit.com, or move Community's listening off Reddit

**Why:** the Community agent's first job every run is to read r/rapport (`sprint/agents/community.md` step 1: `new.json`,
`comments.json`, `search.json`). Today every request to any reddit.com host from this cloud session is rejected before
it reaches Reddit at all — not a Reddit rate limit or a missing header. `curl` gets `CONNECT tunnel failed, response
403` and the agent proxy status (`$HTTPS_PROXY/__agentproxy/status`) logs it plainly:
```
"kind": "connect_rejected", "detail": "gateway answered 403 to CONNECT (policy denial or upstream failure)", "host": "www.reddit.com:443"
```
Tried `www.reddit.com`, `old.reddit.com` and `api.reddit.com` — all three rejected the same way. `WebFetch` fails on
the same URL with a generic "unable to fetch" error, so it is not a curl-specific problem. This is an organization-level
network policy choice made when the environment was created (see the docs at
https://code.claude.com/docs/en/claude-code-on-the-web), separate from the Reddit bot credentials already tracked in
issue #3 — even once those credentials exist, the `reddit-post` **workflow** runs on a GitHub Actions runner and can
still post, but this session still cannot *read* Reddit to decide what to answer.

**What to do (pick one):**
1. Preferred: when configuring this scheduled environment (wherever the Community routine's environment/network policy was
   chosen — see the "Environment configuration" section of the docs above), switch its network policy to one that allows
   `reddit.com` and its subdomains, then re-run the Community routine once to confirm `sprint/skills/reddit.md` reports
   success instead of a block.
2. If Reddit cannot be allowed at the environment level, tell Community (via `sprint/messages.md` or by editing
   `sprint/agents/community.md`) to rely on GitHub only (issues, PRs, Discussions) for listening, and to leave the
   Reddit "Listen" step to whatever channel can reach it — for instance, doing the read via the same GitHub Actions
   runner that posts, if that is scriptable, or a manual weekly pull the owner pastes in.

**Blocked:** the "Listen" and "Answer" steps of every Community run cannot see new posts, comments or questions on
r/rapport, so replies, bug/feature triage from Reddit, and the "This week in Rapport" update are running blind. GitHub-side
listening (issues, PRs, Discussions) is unaffected and is being done every run in the meantime.
