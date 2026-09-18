# The cloud environment (Last verified: 2026-09-18, Build)

- Linux, repository cloned at `/home/user/rapport`, Python 3.12 and Node available; the first `npm ci` takes about 30 s, `scripts/test-light.sh` about 10 s.
- GitHub access: the run used the GitHub MCP tools (`mcp__github__create_pull_request`, `merge_pull_request`, `actions_list`,
  `get_job_logs`, `list_pull_requests`) and the public REST API through `curl`. **`gh` is not installed at all** (2026-09-16:
  `command -v gh` finds nothing), so anything that shells out to it can only be tested here with its call injected — which is a
  reason `scripts/*.py` take a `fetch`/`delete` argument the tests replace, and `gh` only inside the default.
- **Pushing a branch works; deleting one does not.** `git push origin --delete <branch>` and `git push origin :<branch>` both
  return `RPC failed; HTTP 403` from this environment (2026-09-16, twice, on a branch this agent had just created), and no
  GitHub MCP tool deletes a ref. Anything that has to remove a branch belongs in a workflow, where the token can do it.
- **GitHub access is scoped to `Nirmaypanchal/rapport` and nothing else.** Any other repository — including an action
  this project depends on — answers `GitHub access to this repository is not enabled for this session` (2026-09-18,
  trying to read `actions/checkout`'s releases to find the current major). So a run cannot confirm an upstream version
  from here: either leave it as a marked guess for the next run, or find the answer in something already vendored
  (`node_modules/`, `uv.lock`). This applies to `curl` through the proxy as well as to the GitHub MCP tools.
- The public REST API answers without a token for this repository, which is how a script that normally calls `gh` can still be
  driven against real data here: point its `fetch` at `https://api.github.com/repos/Nirmaypanchal/rapport/…` and leave the
  side effects stubbed. That is what caught two wrong diagnoses of the ghost run on 2026-09-16.
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
