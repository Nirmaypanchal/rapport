#!/usr/bin/env python3
"""The decisions behind `.github/workflows/sprint-merge.yml`, where tests can reach them.

    scripts/sprint_merge.py prune-ghost-run --branch sprint/foo --sha abc1234
    scripts/sprint_merge.py prune-ghost-run --branch sprint/foo --sha abc1234 --dry-run

Today it holds one decision: **what to do about the CI run the merge bot's own pull request leaves behind.**

Every auto-merge used to leave a red run in the history. `ci.yml` answers `pull_request` as well as `push` —
it has to, because `push` never fires on this repository for a branch that lives in a fork — so opening a
pull request starts a second run for a commit `push` already tested. Since #19 that run's jobs skip
themselves, which takes about a second (verified on a pull request opened by hand: #20, run 57, `skipped`).

But the merge bot's own pull requests never get that far, and it took three measurements to see why. The
bot opens them with `GITHUB_TOKEN`, and GitHub will not run a workflow for an event that token created —
the run is filed as **`action_required`**, blocked, with **zero jobs**, waiting for an approval that is
never coming. It is not red yet. Deleting the head branch is what turns it red: #22's run sat at
`action_required` for six seconds and went to `failure` the instant `gh pr merge --delete-branch` ran.

So no condition in `ci.yml` and no amount of waiting can save that run: it was never allowed to start. What
is left is to not keep the corpse. Before merging, this deletes that one run — and only that one:

- it must be a `pull_request` run for **this exact commit** on this branch,
- it must be **completed**, and not successful,
- and it must have **zero jobs** — the proof that nothing ran. A run whose jobs merely skipped lists all
  three of them (run 57 again), so a real, skipped run is never mistaken for a corpse.

Two rules this follows:

- **Never block a merge.** No run, a broken `gh`, a refused delete: each says so on stderr and returns. A
  branch that does not merge is a worse problem than a run that goes red.
- **Never delete anything that ran.** Every guard above has to hold, and what was deleted is printed into
  the workflow log, which keeps the record the deleted run would not have carried anyway.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time as _time

APPEAR_SECONDS = 90  # how long a run may take to show up at all before we stop expecting one
SETTLE_SECONDS = 240  # how long we wait for a run that did show up (it skips in about a second)
POLL_SECONDS = 5


def for_sha(runs: list[dict], sha: str) -> list[dict]:
    """The `pull_request` runs for exactly this commit. `head_sha` on a pull_request run is the head
    branch's commit, not the merge commit, so it compares directly with the sha the merge bot was given."""
    return [r for r in runs if r.get("head_sha") == sha and r.get("event") == "pull_request"]


def decide(runs: list[dict], waited: float, appear: int = APPEAR_SECONDS, settle: int = SETTLE_SECONDS) -> dict:
    """`wait` or `go`, always with a reason. `runs` are already narrowed to this commit.

    A run blocked as `action_required` reports `status: completed`, which is what makes it safe to look at:
    it is terminal, not pending. Nothing here decides what to do with it — that is `is_ghost`.
    """
    if not runs:
        if waited < appear:
            return {"action": "wait", "why": f"no pull_request run yet after {waited:.0f}s"}
        return {"action": "go", "why": f"no pull_request run appeared in {appear}s; there is nothing to prune"}
    unfinished = [r for r in runs if r.get("status") != "completed"]
    if not unfinished:
        states = ", ".join(sorted({str(r.get("conclusion")) for r in runs}))
        return {"action": "go", "why": f"the pull request's CI run has settled ({states}) after {waited:.0f}s"}
    if waited >= settle:
        return {
            "action": "go",
            "why": f"{len(unfinished)} pull_request run(s) still going after {settle}s; going on "
                   "rather than holding the branch",
        }
    return {"action": "wait", "why": f"{len(unfinished)} pull_request run(s) still going after {waited:.0f}s"}


def is_ghost(run: dict, jobs: int) -> bool:
    """Is this a run that never executed anything, and so says nothing by existing?

    Zero jobs is the load-bearing test. A run whose jobs were all skipped by a condition still lists every
    one of them, so the only runs with none are those GitHub refused to start: the merge bot's own pull
    request, filed `action_required` because `GITHUB_TOKEN` opened it, and turned red by the branch being
    deleted under it. Anything that ran, or passed, is kept whatever else is true of it.
    """
    return (
        run.get("event") == "pull_request"
        and run.get("status") == "completed"
        and run.get("conclusion") not in (None, "success")
        and jobs == 0
    )


def fetch_runs(branch: str, sha: str) -> list[dict]:
    """The recent runs on this branch, through `gh`. Not filtered by workflow name: any workflow that
    answers `pull_request` would be killed by the merge just the same, and CI is only today's only one.
    A failure here is not fatal — the caller treats it as "nothing to wait for" and eventually merges."""
    out = subprocess.run(
        ["gh", "api", f"repos/{{owner}}/{{repo}}/actions/runs?branch={branch}&event=pull_request&per_page=20"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    runs = json.loads(out).get("workflow_runs", []) if out else []
    return for_sha(runs, sha)


def job_count(run_id: int) -> int:
    """How many jobs that run actually has. Zero means GitHub never started it."""
    out = subprocess.run(
        ["gh", "api", f"repos/{{owner}}/{{repo}}/actions/runs/{run_id}/jobs?per_page=1"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    return int(json.loads(out).get("total_count", 0)) if out else 0


def delete_run(run_id: int) -> None:
    subprocess.run(
        ["gh", "api", "-X", "DELETE", f"repos/{{owner}}/{{repo}}/actions/runs/{run_id}"],
        check=True, capture_output=True, text=True,
    )


def wait_for_pr_ci(branch, sha, *, fetch=fetch_runs, sleep=_time.sleep, clock=_time.monotonic,
                   appear=APPEAR_SECONDS, settle=SETTLE_SECONDS, poll=POLL_SECONDS) -> tuple[dict, list[dict]]:
    """Poll until every pull_request run for this commit is terminal. Returns the plan and those runs."""
    started = clock()
    while True:
        try:
            runs = fetch(branch, sha)
        except Exception as e:  # gh missing, a rate limit, a bad token: never a reason to hold a merge
            print(f"could not read the runs on {branch} ({e}); treating it as none", file=sys.stderr)
            runs = []
        plan = decide(runs, clock() - started, appear, settle)
        if plan["action"] == "go":
            return plan, runs
        print(f"waiting: {plan['why']}", file=sys.stderr)
        sleep(poll)


def prune_ghost_runs(branch, sha, *, fetch=fetch_runs, jobs_of=job_count, delete=delete_run,
                     dry_run: bool = False, **wait_kw) -> list[dict]:
    """Delete the runs for this commit that never ran. Returns one line per run, kept or deleted."""
    plan, runs = wait_for_pr_ci(branch, sha, fetch=fetch, **wait_kw)
    print(plan["why"], file=sys.stderr)
    out = []
    for run in runs:
        rid = run.get("id")
        try:
            jobs = jobs_of(rid)
        except Exception as e:
            out.append({"run": rid, "action": "kept", "why": f"could not count its jobs ({e})"})
            continue
        if not is_ghost(run, jobs):
            out.append({"run": rid, "action": "kept",
                        "why": f"{run.get('conclusion')} with {jobs} job(s): it ran, so it stays"})
            continue
        if dry_run:
            out.append({"run": rid, "action": "would delete", "why": f"{run.get('conclusion')}, no jobs"})
            continue
        try:
            delete(rid)
            out.append({"run": rid, "action": "deleted", "why": f"{run.get('conclusion')}, no jobs, nothing ran"})
        except Exception as e:  # a refused delete is a red run, not a failed merge
            out.append({"run": rid, "action": "kept", "why": f"delete refused ({e})"})
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    prune = sub.add_parser("prune-ghost-run", help="delete the pull request's CI run if it never ran at all")
    prune.add_argument("--branch", required=True, help="the head branch of the pull request")
    prune.add_argument("--sha", required=True, help="the commit the merge bot was handed")
    prune.add_argument("--appear", type=int, default=APPEAR_SECONDS, help="seconds to wait for a run to show up")
    prune.add_argument("--settle", type=int, default=SETTLE_SECONDS, help="seconds to wait for it to finish")
    prune.add_argument("--dry-run", action="store_true", help="say what would be deleted, delete nothing")
    args = ap.parse_args(argv)

    for line in prune_ghost_runs(args.branch, args.sha, dry_run=args.dry_run,
                                 appear=args.appear, settle=args.settle):
        print(f"run {line['run']}: {line['action']} — {line['why']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
