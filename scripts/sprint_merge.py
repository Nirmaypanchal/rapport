#!/usr/bin/env python3
"""The decisions behind `.github/workflows/sprint-merge.yml`, where tests can reach them.

    scripts/sprint_merge.py open-pr        --branch sprint/foo --sha abc1234 --result success
    scripts/sprint_merge.py prune-ghost-run --branch sprint/foo --sha abc1234
    scripts/sprint_merge.py merge          --branch sprint/foo --sha abc1234 --result success

Each takes `--dry-run`, which decides everything and changes nothing.

It holds two decisions. **Open and merge, or hold and say why** is below; **what to do about the CI run the
merge bot's own pull request leaves behind** is further down.

## Open, merge, hold — and never quietly do nothing

This is the whole path a `sprint/*` branch takes into `main`, so a step that reports success having done
nothing is the worst thing it can do. It did exactly that twice on 2026-09-09: the workflow ended its
`gh pr create` with `|| true`, the repository setting "Allow GitHub Actions to create and approve pull
requests" was off, `gh` printed *"GitHub Actions is not permitted to create or approve pull requests"* and
exited non-zero — and the job went green having merged nothing. Nobody noticed until a person went looking
for the pull request (`sprint/needs-human/done/2026-09-09-actions-cannot-open-prs.md`).

So nothing here is allowed to fail quietly:

- every `gh` call is checked, and a failure ends the step red with what `gh` said,
- after opening a pull request it **asks again whether one exists**, because a create that "succeeded"
  without leaving a pull request behind is the failure this is here to catch,
- and reaching the merge with no pull request to merge is an error, not an early `exit 0`.

The one thing that is not an error is a deliberate hold: a pull request labeled `needs-human` is left alone
(AGENTS.md), and a branch whose CI failed gets a comment instead of a merge. Both say so on stdout.

## The CI run the merge bot's own pull request leaves behind

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
import os
import subprocess
import sys
import tempfile
import time as _time

APPEAR_SECONDS = 90  # how long a run may take to show up at all before we stop expecting one
SETTLE_SECONDS = 240  # how long we wait for a run that did show up (it skips in about a second)
POLL_SECONDS = 5
CONFIRM_ASKS = 3  # how many times the pull request we just opened is looked for before we call it missing
CONFIRM_SECONDS = 3

BASE = "main"
PR_LABEL = "sprint"
HOLD_LABEL = "needs-human"  # AGENTS.md: anything a human must see first is never merged by the bot

PR_BODY = ("{body}\n\n---\nOpened automatically from `{branch}` by the sprint (see AGENTS.md). "
           "CI on the branch: **{result}**.\n")
FAILURE_COMMENT = "CI **{result}** on {sha}. Not merged. The next Build run should fix this or close the PR."
MERGE_COMMENT = "Merged automatically: CI passed on {sha}."


class Stopped(Exception):
    """Something this step must not paper over. The message is printed and the job goes red.

    Only ever raised where going on would mean reporting success having merged nothing — never for a
    deliberate hold (`needs-human`, a red branch), which is a decision, not a failure.
    """


# --- open the pull request, or find the one that is already there ----------------------------------------


def open_plan(prs: list[dict]) -> dict:
    """`open` or `reuse`. A branch keeps its pull request across pushes, so most runs reuse one."""
    if prs:
        number = prs[0].get("number")
        return {"action": "reuse", "number": number, "why": f"#{number} is already open for this branch"}
    return {"action": "open", "why": "no open pull request for this branch yet"}


def merge_plan(prs: list[dict], result: str) -> dict:
    """`merge`, `hold`, `note` or `stop`, always with a reason.

    Order matters: a red branch is commented on whatever its labels say, because the comment is how the
    next Build run finds it. `stop` is the loud one — the pull request that was opened two steps ago has
    to still be there, and if it is not, this run merged nothing and must say so in red.
    """
    if not prs:
        return {"action": "stop",
                "why": "no open pull request to merge; the step that opens one reported success"}
    pr = prs[0]
    number = pr.get("number")
    labels = {(label.get("name") or "") for label in (pr.get("labels") or [])}
    if result != "success":
        return {"action": "note", "number": number, "why": f"CI {result}: #{number} is not merged"}
    if HOLD_LABEL in labels:
        return {"action": "hold", "number": number, "why": f"held: #{number} is labeled {HOLD_LABEL}"}
    return {"action": "merge", "number": number, "why": f"CI passed: squash-merging #{number}"}


def create_command(branch: str, title: str, body_file: str) -> list[str]:
    return ["gh", "pr", "create", "--head", branch, "--base", BASE,
            "--title", title, "--body-file", body_file, "--label", PR_LABEL]


def merge_command(number: int, sha: str) -> list[str]:
    return ["gh", "pr", "merge", str(number), "--squash", "--delete-branch",
            "--body", MERGE_COMMENT.format(sha=sha)]


def comment_command(number: int, body: str) -> list[str]:
    return ["gh", "pr", "comment", str(number), "--body", body]


def gh(argv: list[str]) -> None:
    """Run a `gh` command and let a failure through. Nothing here is optional enough for `|| true`."""
    subprocess.run(argv, check=True)


def open_pull_requests(branch: str) -> list[dict]:
    """The open pull requests whose head is this branch (GitHub allows one per head/base pair)."""
    out = subprocess.run(
        ["gh", "pr", "list", "--head", branch, "--state", "open", "--json", "number,labels"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    return json.loads(out) if out else []


def commit_message(sha: str) -> tuple[str, str]:
    """The commit's subject and body — the pull request's title and description, per AGENTS.md."""
    def log(fmt: str) -> str:
        return subprocess.run(["git", "log", "-1", f"--format={fmt}", sha],
                              check=True, capture_output=True, text=True).stdout.strip()
    return log("%s"), log("%b")


def create_pull_request(branch: str, title: str, body: str, *, run=gh) -> None:
    """`gh pr create`, with the body through a file so its length and quoting cannot bite."""
    fd, tmp = tempfile.mkstemp(suffix=".md")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(body)
        run(create_command(branch, title, tmp))
    finally:
        os.unlink(tmp)


def confirm_opened(branch: str, *, prs=open_pull_requests, sleep=_time.sleep, asks: int = 3) -> list[dict]:
    """Ask again whether the pull request we just created is there — the check that would have caught
    2026-09-09. Asked a few times because "it is not there" is the accusation being made, and a list that
    has not caught up yet would be a red job for no reason; three quiet seconds are cheaper than that."""
    for attempt in range(asks):
        found = prs(branch)
        if found:
            return found
        if attempt + 1 < asks:
            print(f"no pull request on {branch} yet; asking again", file=sys.stderr)
            sleep(CONFIRM_SECONDS)
    return []


def ensure_pull_request(branch: str, sha: str, result: str, *, prs=open_pull_requests,
                        commit=commit_message, create=create_pull_request, sleep=_time.sleep,
                        asks: int = CONFIRM_ASKS, dry_run: bool = False) -> dict:
    """Make sure this branch has an open pull request, even when CI failed — a red branch with no pull
    request is invisible. Returns what was done; raises `Stopped` if afterwards there is still none."""
    plan = open_plan(prs(branch))
    if plan["action"] == "reuse":
        return plan
    title, body = commit(sha)
    if dry_run:
        return {"action": "would open", "why": f"would open a pull request titled {title!r}"}
    create(branch, title, PR_BODY.format(body=body, branch=branch, result=result))
    after = confirm_opened(branch, prs=prs, sleep=sleep, asks=asks)
    if not after:
        raise Stopped(
            f"`gh pr create` reported success but {branch} still has no open pull request. Nothing was "
            "merged. Check that 'Allow GitHub Actions to create and approve pull requests' is on in the "
            "repository settings (see sprint/needs-human/done/2026-09-09-actions-cannot-open-prs.md)."
        )
    number = after[0].get("number")
    return {"action": "opened", "number": number, "why": f"opened #{number} from {branch}"}


def merge_when_green(branch: str, sha: str, result: str, *, prs=open_pull_requests, run=gh,
                     dry_run: bool = False) -> dict:
    """Squash-merge the branch's pull request, or say exactly why it is not being merged."""
    plan = merge_plan(prs(branch), result)
    if plan["action"] == "stop":
        raise Stopped(plan["why"])
    if dry_run:
        return {**plan, "action": f"would {plan['action']}"}
    if plan["action"] == "note":
        run(comment_command(plan["number"], FAILURE_COMMENT.format(result=result, sha=sha)))
    elif plan["action"] == "merge":
        run(merge_command(plan["number"], sha))
    return plan


# --- the CI run the merge bot's own pull request leaves behind --------------------------------------------


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

    def command(name: str, help: str) -> argparse.ArgumentParser:
        p = sub.add_parser(name, help=help)
        p.add_argument("--branch", required=True, help="the head branch of the pull request")
        p.add_argument("--sha", required=True, help="the commit the merge bot was handed")
        p.add_argument("--dry-run", action="store_true", help="decide everything, change nothing")
        return p

    opener = command("open-pr", "open the branch's pull request unless one is already open")
    opener.add_argument("--result", required=True, help="CI's conclusion on the branch, for the body")
    prune = command("prune-ghost-run", "delete the pull request's CI run if it never ran at all")
    prune.add_argument("--appear", type=int, default=APPEAR_SECONDS, help="seconds to wait for a run to show up")
    prune.add_argument("--settle", type=int, default=SETTLE_SECONDS, help="seconds to wait for it to finish")
    merger = command("merge", "squash-merge the pull request, or say why it is being held")
    merger.add_argument("--result", required=True, help="CI's conclusion on the branch; only success merges")
    args = ap.parse_args(argv)

    if args.command == "prune-ghost-run":
        # Nothing in here may hold a merge, so it never raises: every path returns a line, kept or deleted.
        for line in prune_ghost_runs(args.branch, args.sha, dry_run=args.dry_run,
                                     appear=args.appear, settle=args.settle):
            print(f"run {line['run']}: {line['action']} — {line['why']}")
        return 0

    try:
        # The seams are passed rather than defaulted so that everything reaching GitHub is named in one
        # place — and so a test can replace them here, on the path the workflow actually takes.
        if args.command == "open-pr":
            line = ensure_pull_request(args.branch, args.sha, args.result, dry_run=args.dry_run,
                                       prs=open_pull_requests, commit=commit_message,
                                       create=create_pull_request)
        else:
            line = merge_when_green(args.branch, args.sha, args.result, dry_run=args.dry_run,
                                    prs=open_pull_requests, run=gh)
    except Stopped as e:
        print(f"sprint-merge stopped: {e}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as e:
        # The `|| true` this replaced swallowed exactly this, twice, and reported success.
        print(f"sprint-merge stopped: {' '.join(e.cmd)} exited {e.returncode}", file=sys.stderr)
        for stream in (e.stdout, e.stderr):
            if stream:
                print(stream, file=sys.stderr)
        return 1
    print(f"{line['action']}: {line['why']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
