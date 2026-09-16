#!/usr/bin/env python3
"""The decisions behind `.github/workflows/sprint-merge.yml`, where tests can reach them.

    scripts/sprint_merge.py wait-for-pr-ci --branch sprint/foo --sha abc1234
    scripts/sprint_merge.py wait-for-pr-ci --branch sprint/foo --sha abc1234 --dry-run

Today it holds one decision: **when it is safe to squash-merge without killing a CI run**.

Every auto-merge used to leave a red run behind. `ci.yml` answers `pull_request` as well as `push` — it has
to, because `push` never fires on this repository for a fork's branch — so the pull request the merge bot
opens starts a second run for a commit that was already tested. Since #19 that run's jobs all skip, which
takes about one second; but the merge bot opened its pull request and merged it three seconds later (#19:
opened 03:12:12, merged 03:12:15), and the run was created in that same second and killed before a single
job was evaluated. Zero jobs, nothing run, permanently red. No condition inside `ci.yml` can win that race,
because the race is decided before any condition is read.

So the fix is on this side: open the pull request, let its run reach a conclusion, *then* merge. One second
of waiting, against a run history where red means something actually failed.

Two rules this follows:

- **Never block a merge on it.** If no run appears, or one is still going after a few minutes, it merges
  anyway and says so. A merge that does not happen is a worse problem than a run that goes red.
- **Wait on the run for this exact commit.** A pull request that has been open since an earlier, red push
  carries older runs that concluded long ago; they say nothing about the one this merge would kill.
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
    """`wait` or `go`, always with a reason. `runs` are already narrowed to this commit."""
    if not runs:
        if waited < appear:
            return {"action": "wait", "why": f"no pull_request run yet after {waited:.0f}s"}
        return {"action": "go", "why": f"no pull_request run appeared in {appear}s; there is none to kill"}
    unfinished = [r for r in runs if r.get("status") != "completed"]
    if not unfinished:
        states = ", ".join(sorted({str(r.get("conclusion")) for r in runs}))
        return {"action": "go", "why": f"the pull request's CI run has settled ({states}) after {waited:.0f}s"}
    if waited >= settle:
        return {
            "action": "go",
            "why": f"{len(unfinished)} pull_request run(s) still going after {settle}s; merging anyway "
                   "rather than holding the branch",
        }
    return {"action": "wait", "why": f"{len(unfinished)} pull_request run(s) still going after {waited:.0f}s"}


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


def wait_for_pr_ci(branch, sha, *, fetch=fetch_runs, sleep=_time.sleep, clock=_time.monotonic,
                   appear=APPEAR_SECONDS, settle=SETTLE_SECONDS, poll=POLL_SECONDS) -> dict:
    """Poll until it is safe to merge. Returns the `go` plan that ended the wait."""
    started = clock()
    while True:
        try:
            runs = fetch(branch, sha)
        except Exception as e:  # gh missing, a rate limit, a bad token: never a reason to hold a merge
            print(f"could not read the runs on {branch} ({e}); treating it as none", file=sys.stderr)
            runs = []
        plan = decide(runs, clock() - started, appear, settle)
        if plan["action"] == "go":
            return plan
        print(f"waiting: {plan['why']}", file=sys.stderr)
        sleep(poll)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    wait = sub.add_parser("wait-for-pr-ci", help="wait until merging cannot kill the pull request's CI run")
    wait.add_argument("--branch", required=True, help="the head branch of the pull request")
    wait.add_argument("--sha", required=True, help="the commit the merge bot was handed")
    wait.add_argument("--appear", type=int, default=APPEAR_SECONDS, help="seconds to wait for a run to show up")
    wait.add_argument("--settle", type=int, default=SETTLE_SECONDS, help="seconds to wait for it to finish")
    wait.add_argument("--dry-run", action="store_true", help="decide once on what exists now, wait for nothing")
    args = ap.parse_args(argv)

    if args.dry_run:
        try:
            runs = fetch_runs(args.branch, args.sha)
        except Exception as e:
            print(f"could not read the runs on {args.branch} ({e}); treating it as none", file=sys.stderr)
            runs = []
        plan = decide(runs, 0.0, args.appear, args.settle)
        print(f"{plan['action']}: {plan['why']}")
        return 0
    plan = wait_for_pr_ci(args.branch, args.sha, appear=args.appear, settle=args.settle)
    print(f"go: {plan['why']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
