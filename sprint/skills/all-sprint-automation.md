# The sprint's own automation (Last verified: 2026-09-15, Build)

How this project's `.github/workflows/` behave, and what has already gone wrong in them. Every agent should read this,
not only Build: week 37's one real Community finding was a workflow bug spotted from the issue list, and Research and
Release both depend on these workflows doing what they claim.

- **The merge bot can merge a pull request that touches `.github/workflows/`.** Verified 2026-09-12: #11 changed
  `needs-human.yml` and `sprint-merge` squash-merged it unattended, and pushing the branch from a cloud agent was
  accepted too. The backlog carried a warning that this might be refused; it was a guess, and it was wrong. Fix
  workflows like any other code.
- **Logic in a workflow is untested logic.** Put the decision in `scripts/<thing>.py` (stdlib only, a `main()`, a
  `--dry-run`) and leave the YAML as checkout plus one `run:` line that passes `GH_TOKEN`. Then `tests/` can cover
  it, which is the difference between "#3 and #6 are the same request" being caught by CI and being caught by a
  human three weeks later. `scripts/needs_human_issues.py` is the shape to copy.
- **Never ask the GitHub *search* index whether something exists.** `gh issue list --search '"<title>" in:title'`
  is fuzzy and eventually consistent: on 2026-09-09 it found a two-and-a-half-hour-old issue for one file and
  missed one of the same age for another. Use `gh issue list --label … --state all --json …` (the list API is
  immediate and exact) and match in your own code, on a marker you wrote (`<!-- needs-human-file: … -->`), not on
  text a human may edit.
- `--state all`: a closed issue still means "already filed". Anything that files-once must look at closed ones too,
  or it re-files everything the owner has just finished.
- A guard test is cheap and stops the regression coming back through the back door:
  `assert "--search" not in WORKFLOW.read_text()`.
- Job logs are readable long after the fact and are the fastest way to find out what a workflow actually did —
  list the run's jobs, then read the job's log. That is how the #3/#6 cause was pinned down rather than guessed.
- **Do not trust `merged` from the pull request *list* API.** On 2026-09-13 it reported `merged: false` for #13,
  which `sprint-merge` had squash-merged a minute earlier; reading the pull request itself showed `merged: true` with
  a `merged_at`. Check the single-PR read, or just look for the commit on `main`.

- **Every auto-merge leaves one red CI run behind, and it is a ghost.** `ci.yml` has a bare `pull_request:` trigger, so
  `sprint-merge` opening a PR starts a second run that is killed when the PR squash-merges three seconds later: zero
  jobs, nothing run, permanently red. The identical SHA is green on the `push` event. Four of week 37's 17 CI runs are
  these. Check the job count before believing a red run; there is a backlog item to stop creating them.
- **The nightly's silence is watched** (`nightly-watchdog.yml` + `scripts/nightly_watchdog.py`, 2026-09-15). Daily: one
  issue when the newest `sprint/log/*-nightly.md` is more than 48 hours old, closed again when a log lands. So an agent
  no longer has to notice an absence by hand — but read what it decided before trusting it, because two of its choices
  are not obvious: it counts **open** issues only (a silence that returns after a fix is news again, unlike a
  needs-human file that waits), and [#12](https://github.com/Nirmaypanchal/rapport/issues/12) carries its
  `<!-- nightly-watchdog -->` marker so the escalation already open is not duplicated.
- **In a workflow, a file's mtime is the checkout time, not when it was written.** `actions/checkout` stamps every file
  as it clones, so anything reasoning about how old a file is must read a date out of its name or its content. The
  watchdog above would have reported a week-old log as seconds old.
- **A script whose real job is irreversible (posting, filing, merging) needs a `--dry-run` and a way to point it at a
  scratch folder**, or the only way to test it is to do the thing. `scripts/reddit_post.py` had neither, so the bug that
  made every post to r/rapport impossible (#16) survived until a real post hit it; `--outbox DIR --dry-run` is now how
  an outbox file is checked before it is pushed.
- **`sprint-merge` still ends `gh pr create` with `|| true`**, so it can report success having opened and merged
  nothing — that is how the Actions-permission failure went unnoticed twice on 2026-09-09. The setting being on means
  the bug no longer fires, not that it is fixed. On the backlog as "Make `sprint-merge` fail loudly", with a note to
  move the decision into `scripts/` where a test can reach it.
