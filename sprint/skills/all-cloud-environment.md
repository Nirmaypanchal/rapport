# The cloud environment (Last verified: 2026-09-20, retro week 38)

- Linux, repository cloned at `/home/user/rapport`, Python 3.12 and Node available; the first `npm ci` takes about 30 s, `scripts/test-light.sh` about 10 s.
- GitHub access: the run used the GitHub MCP tools (`mcp__github__create_pull_request`, `merge_pull_request`, `actions_list`,
  `get_job_logs`, `list_pull_requests`) and the public REST API through `curl`. **`gh` is not installed at all** (2026-09-16:
  `command -v gh` finds nothing), so anything that shells out to it can only be tested here with its call injected — which is a
  reason `scripts/*.py` take a `fetch`/`delete` argument the tests replace, and `gh` only inside the default.
- **Pushing a branch works; deleting one does not.** `git push origin --delete <branch>` and `git push origin :<branch>` both
  return `RPC failed; HTTP 403` from this environment (2026-09-16, twice, on a branch this agent had just created), and no
  GitHub MCP tool deletes a ref. Anything that has to remove a branch belongs in a workflow, where the token can do it.
- **GitHub *API* access is scoped to `Nirmaypanchal/rapport` and nothing else.** Any other repository — including an action
  this project depends on — answers `GitHub access to this repository is not enabled for this session` (2026-09-18,
  trying to read `actions/checkout`'s releases to find the current major).
  **This does not mean an upstream fact is unverifiable: `WebFetch` reads the same page over the open web.**
  `WebFetch https://github.com/actions/checkout/releases` answers in one call (2026-09-20, retro: the current major is
  **v7**, latest v7.0.1 — the board had recorded `@v5` as a marked guess because the API call failed). The rule: an API
  tool being scoped is a fact about that tool, not about the world. Try the public page before writing "unverifiable
  from here".
- The public REST API answers without a token for this repository, which is how a script that normally calls `gh` can still be
  driven against real data here: point its `fetch` at `https://api.github.com/repos/Nirmaypanchal/rapport/…` and leave the
  side effects stubbed. That is what caught two wrong diagnoses of the ghost run on 2026-09-16.
- No Apple silicon, no Metal, no MLX. `uv sync` works because `mlx-whisper` and `mlx-lm` carry `sys_platform == 'darwin'` markers;
  `scripts/test-light.sh` avoids even that by creating `.venv-light` with only the light dependencies.
- Frontend: `cd frontend && npm ci && npx tsc --noEmit && npm run build`.
- CI on a `sprint/*` push takes **about a minute** — 42 s for the whole run on 2026-09-19 (`backend-light` 16 s,
  `frontend` 38 s, the full macOS `backend` 30 s, all in parallel), not the 3 to 6 minutes this line used to claim.
  Worth knowing before you plan to do something else while it runs: by the time you have written a board entry it has
  merged. The Sprint merge workflow runs right after CI. If the repository setting
  "Allow GitHub Actions to create and approve pull requests" is off, the workflow's `gh pr create` fails and nothing merges;
  then open and merge the PR yourself with the GitHub tools once CI is green (PR #1 was merged that way).
- Pushes by the merge workflow do not trigger other workflows; pushes by agents do.
- `git reset --hard` throws away uncommitted work; commit or stash before switching branches.
- How this repository's own workflows behave — the merge bot, the escalation filer, the red ghost run left by every
  auto-merge — is in `sprint/skills/all-sprint-automation.md`. Read it before believing a red CI run.
- **WebFetch reads public GitHub pages that no API tool here exposes** — Discussions, for one. Verified 2026-09-13. When
  an API is closed to you, try the public page before recording the gap as permanent; see `sprint/skills/community-listening.md`.
- **reddit.com is blocked to every method here, not just to `curl`.** `curl` through the proxy gives
  `CONNECT tunnel failed, response 403` and `WebFetch` answers `Claude Code is unable to fetch from www.reddit.com`
  (both 2026-09-20). Two independent methods is enough — stop re-probing more than weekly, and note that this says
  nothing about *posting*, which happens from a GitHub Action on a different network and fails only for want of
  credentials (#3). See `sprint/skills/reddit.md`.
- The routines the agents themselves run on — their triggers, why one goes silent, what they may push to — are in
  `sprint/skills/all-routines.md`.
- The GitHub MCP list tools accept a `fields` array. Use it: the default response includes every issue and PR body, and
  `actions_list` without a narrow `perPage` returns ~94 KB that will not fit in one read.
