# The cloud environment (Last verified: 2026-09-13, retro week 37)

- Linux, repository cloned at `/home/user/rapport`, Python 3.12 and Node available; the first `npm ci` takes about 30 s, `scripts/test-light.sh` about 10 s.
- GitHub access: the run used the GitHub MCP tools (`mcp__github__create_pull_request`, `merge_pull_request`, `actions_list`,
  `get_job_logs`, `list_pull_requests`) and the public REST API through `curl`. `gh` may not be authenticated; try it once, fall back to those.
- No Apple silicon, no Metal, no MLX. `uv sync` works because `mlx-whisper` and `mlx-lm` carry `sys_platform == 'darwin'` markers;
  `scripts/test-light.sh` avoids even that by creating `.venv-light` with only the light dependencies.
- Frontend: `cd frontend && npm ci && npx tsc --noEmit && npm run build`.
- CI on a `sprint/*` push takes 3 to 6 minutes. The Sprint merge workflow runs right after CI. If the repository setting
  "Allow GitHub Actions to create and approve pull requests" is off, the workflow's `gh pr create` fails and nothing merges;
  then open and merge the PR yourself with the GitHub tools once CI is green (PR #1 was merged that way).
- Pushes by the merge workflow do not trigger other workflows; pushes by agents do.
- `git reset --hard` throws away uncommitted work; commit or stash before switching branches.
- How this repository's own workflows behave — the merge bot, the escalation filer, the red ghost run left by every
  auto-merge — is in `sprint/skills/all-sprint-automation.md`. Read it before believing a red CI run.
- **WebFetch reads public GitHub pages that no API tool here exposes** — Discussions, for one. Verified 2026-09-13. When
  an API is closed to you, try the public page before recording the gap as permanent; see `sprint/skills/community-listening.md`.
- The GitHub MCP list tools accept a `fields` array. Use it: the default response includes every issue and PR body, and
  `actions_list` without a narrow `perPage` returns ~94 KB that will not fit in one read.
