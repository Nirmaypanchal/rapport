# Reddit (Last verified: 2026-09-12, fourth Community run)

## The block

**This cloud environment cannot reach reddit.com at all.** Every request to `www.reddit.com`, `old.reddit.com` and
`api.reddit.com` — via `curl` and via `WebFetch` — is rejected before it reaches Reddit: `CONNECT tunnel failed,
response 403`, and `$HTTPS_PROXY/__agentproxy/status` shows `connect_rejected` / "policy denial" for each host. This is
the session's network policy blocking the domain, **not** a Reddit rate limit and **not** a missing User-Agent — those
would come back as a real HTTP response, not a rejected CONNECT.

Escalated in `sprint/needs-human/2026-09-09-cloud-environment-blocks-reddit.md` (issue #5), still open.

**Do not re-run the curl every run.** Check whether that escalation file is still in `needs-human/` (not moved to
`done/`) and skip straight to the GitHub part of listening. Re-probe only after several quiet days, so the claim in
this file is evidence rather than habit. Verified unchanged on 09-10, 09-11 (by file check), 09-12 (by re-probe) and
09-13 (by file check) — four days, no movement, nothing learned from the repeats.

## How to read it, once the policy allows it

- Public read, no auth: `https://www.reddit.com/r/rapport/new.json?limit=50`, `.../comments.json?limit=100`,
  `https://www.reddit.com/comments/<id>.json` for a thread, `https://www.reddit.com/search.json?q=<query>&sort=new`.
- Always send `User-Agent: rapport-sprint/1.0 (by u/<owner account>)`; without it Reddit returns 429 or 403. Keep under
  one request per two seconds.
- Fullnames: posts are `t3_<id>`, comments `t1_<id>`. Replies go to the fullname you answer.
- `sprint/reddit/state.json` holds `seen` (fullnames read) and `answered` (fullnames replied to). Update it every run.

## How to post

Only the `reddit-post` workflow posts, from `sprint/reddit/outbox/` (format in `sprint/agents/community.md`). The
script hard-codes r/rapport and refuses any other subreddit. It needs the secrets `REDDIT_CLIENT_ID`,
`REDDIT_CLIENT_SECRET`, `REDDIT_USERNAME`, `REDDIT_PASSWORD` — a "script" app on the bot account, password grant, and
the account must not have 2FA. Not configured yet: `sprint/needs-human/2026-09-09-reddit-bot-credentials.md` (issue #3).

New accounts are rate-limited and their posts may land in the spam filter until the account has karma or is a moderator
of r/rapport.

## Worth knowing

r/rapport had no readers to lose during the week this was blocked — the product has never been released, so there was
nothing to announce and nobody arriving. The block is a real problem for later, not the reason the subreddit is quiet
now. Don't let fixing it feel like fixing the community.
