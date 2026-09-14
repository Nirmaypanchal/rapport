# Research: listening and specs (Last verified: 2026-09-14)

- **Checking for real external feedback is fast and worth doing every run, even when the answer is "still none."**
  `WebFetch https://api.github.com/repos/Nirmaypanchal/rapport/issues?state=all&per_page=100` plus
  `.../issues/comments?per_page=100` (the comments endpoint 403s via WebFetch sometimes; the GitHub MCP
  `issue_read get_comments` tool per-issue is the fallback) tells you in two calls whether anyone outside the sprint
  has ever opened an issue or left a comment. Every issue and comment authored by `github-actions` or the owner's
  own account is agent-filed sprint infrastructure, not a user. `https://github.com/Nirmaypanchal/rapport/discussions`
  (WebFetch, per `all-cloud-environment.md`) is the same check for Discussions. Record the result as a dated fact in
  `sprint/research/feedback.md` either way — "no external feedback yet" is information, not a gap to apologize for.
- **When there is no product feedback yet, read what people say about the competitors instead, and label it as a
  proxy.** WebSearch on "<competitor> reddit/review 2026" style queries surfaces genuine complaints and praise faster
  than guessing. Frame each finding as "what our first users will expect," not as a Rapport-specific request — don't
  let the framing slip into sounding like real user demand when it isn't yet.
- **Spec every "needs a view from Research" item by reading the actual code first, not by describing the feature in
  the abstract.** Build's questions in `messages.md` name real files and functions (`db.search_summaries()`,
  `rapport/mcp.py`'s `TOOLS`, `sources-view.tsx`'s `rootOf()`) — read them before writing the spec, and the spec
  writes itself in terms Build can act on directly (exact routes, exact functions to add, which existing component's
  styling to reuse) instead of a restated feature request. A spec that names no file is not done.
- **Mobbin is worth one targeted query per spec that touches layout, not a browse.** `search_screens` with a
  specific query (the exact UI problem, e.g. "search results mixing content types with a badge") returns real
  precedent fast; use it to settle a genuine design fork (one list vs. two sections) rather than guessing, and cite
  which apps it found in the decision. Don't call it for things that don't have a layout question (a backend
  helper, a workflow fix).
- **A trend that conflicts with a named architecture decision (`AGENTS.md`, `sprint/decisions.md`) is not a backlog
  item, even if it's real.** Write it into `sprint/research/trends.md` and `sprint/decisions.md` as a flagged
  question for the Retrospective or the owner instead of sizing it like a normal Ready item. Promoting it to Now
  would commit Build to a call only a wider view should make.
