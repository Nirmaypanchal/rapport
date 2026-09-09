# Reddit (Last verified: 2026-09-09, before credentials existed)

- Public read, no auth: `https://www.reddit.com/r/rapport/new.json?limit=50`, `.../comments.json?limit=100`,
  `https://www.reddit.com/comments/<id>.json` for a thread, `https://www.reddit.com/search.json?q=<query>&sort=new`.
  Always send `User-Agent: rapport-sprint/1.0 (by u/<owner account>)`; without it Reddit returns 429 or 403. Keep under one request per two seconds.
- Fullnames: posts are `t3_<id>`, comments `t1_<id>`. Replies go to the fullname you answer.
- Posting is done only by the `reddit-post` workflow from `sprint/reddit/outbox/` (see `sprint/agents/community.md`). The script hard-codes
  r/rapport and refuses other subreddits. It needs the secrets `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USERNAME`,
  `REDDIT_PASSWORD` (a "script" app on the bot account, password grant; the account must not have 2FA).
- New accounts are rate-limited and their posts may land in the spam filter until the account has karma or is a moderator of r/rapport.
- `sprint/reddit/state.json` holds `seen` (fullnames read) and `answered` (fullnames replied to). Update it every run.
