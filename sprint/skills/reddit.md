# Reddit (Last verified: 2026-09-10, second Community run)

- **Still blocked as of 2026-09-11 (third Community run) — not re-tested, per this file's own advice.** Checked
  `sprint/needs-human/2026-09-09-cloud-environment-blocks-reddit.md`: still open. Skipped the curl entirely this
  run and went straight to GitHub-only listening, as this file says to. If a fourth run finds the escalation still
  open, keep doing the same — there is no new information to gain from repeating a network probe whose cause
  (an environment-level policy) nothing in this session can change.
- **Still blocked as of 2026-09-10.** Re-ran the same `curl -A "rapport-sprint/1.0 …" .../new.json` request; still
  `CONNECT tunnel failed, response 403`, and `$HTTPS_PROXY/__agentproxy/status` still logs `connect_rejected` for
  `www.reddit.com:443`. No change since the escalation below was filed. Don't re-test this every run — check
  `sprint/needs-human/2026-09-09-cloud-environment-blocks-reddit.md` is still open (not moved to `done/`) instead;
  only retry the curl once that file is gone.
- **This cloud environment cannot reach reddit.com at all (2026-09-09, first Community run).** Every request to
  `www.reddit.com`, `old.reddit.com` and `api.reddit.com` — via `curl` and via `WebFetch` — fails before it reaches
  Reddit: `curl` reports `CONNECT tunnel failed, response 403` and `$HTTPS_PROXY/__agentproxy/status` shows
  `connect_rejected` / "gateway answered 403 to CONNECT (policy denial or upstream failure)" for each host. This is
  the session's network policy blocking the domain outright, not a Reddit rate limit, not a missing User-Agent — the
  429/403-from-Reddit case below is a different failure mode and would show a real HTTP response, not a rejected
  CONNECT. Escalated in `sprint/needs-human/2026-09-09-cloud-environment-blocks-reddit.md`. Until that is resolved
  (or a run finds a route that works), skip straight to the GitHub-only part of Listen (issues, PRs, Discussions)
  and say so in the log — don't burn time retrying the same curl.
- Public read, no auth (works once the network policy allows it): `https://www.reddit.com/r/rapport/new.json?limit=50`,
  `.../comments.json?limit=100`, `https://www.reddit.com/comments/<id>.json` for a thread,
  `https://www.reddit.com/search.json?q=<query>&sort=new`. Always send
  `User-Agent: rapport-sprint/1.0 (by u/<owner account>)`; without it Reddit returns 429 or 403. Keep under one request per two seconds.
- Fullnames: posts are `t3_<id>`, comments `t1_<id>`. Replies go to the fullname you answer.
- Posting is done only by the `reddit-post` workflow from `sprint/reddit/outbox/` (see `sprint/agents/community.md`). The script hard-codes
  r/rapport and refuses other subreddits. It needs the secrets `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USERNAME`,
  `REDDIT_PASSWORD` (a "script" app on the bot account, password grant; the account must not have 2FA).
- New accounts are rate-limited and their posts may land in the spam filter until the account has karma or is a moderator of r/rapport.
- `sprint/reddit/state.json` holds `seen` (fullnames read) and `answered` (fullnames replied to). Update it every run.
