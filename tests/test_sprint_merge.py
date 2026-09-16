"""Guards for scripts/sprint_merge.py, which cleans up after Sprint merge's own pull request.

Every auto-merge left a red CI run behind. The merge bot opens its pull request with `GITHUB_TOKEN`, and
GitHub will not run a workflow for an event that token created: the run is filed `action_required` with zero
jobs and goes red the moment `gh pr merge --delete-branch` removes the branch under it (#22: blocked at
03:27:54, red at 03:28:01). Nothing in `ci.yml` can rescue a run that was never allowed to start, so the
merge deletes it instead.

Two things must not regress. **Nothing that ran may ever be deleted** — a run whose jobs were all skipped by
a condition still lists all three of them (#20's run 57), so zero jobs is what separates a corpse from a
real run. And **none of this may hold a merge**: no run, a broken `gh`, a refused delete, a run that keeps
going — every path returns and lets the merge happen.
"""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "sprint_merge.py"
WORKFLOW = ROOT / ".github" / "workflows" / "sprint-merge.yml"
SHA = "ef16d732cafe0000000000000000000000000000"


def load():
    spec = importlib.util.spec_from_file_location("sprint_merge", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sm = load()


def run(status="completed", conclusion="skipped", sha=SHA, event="pull_request", id=101):
    return {"id": id, "status": status, "conclusion": conclusion, "head_sha": sha, "event": event}


def ghost(id=101):
    """What the merge bot's own pull request leaves: blocked before it started, nothing run."""
    return run(status="completed", conclusion="action_required", id=id)


# --- which runs count ------------------------------------------------------------------------------------


def test_only_the_runs_for_this_commit_count():
    """A pull request open since an earlier, red push carries runs that concluded long ago."""
    runs = [run(sha="0ld0ld0ld"), run(), run(sha="000000")]
    assert sm.for_sha(runs, SHA) == [run()]


def test_a_push_run_is_not_the_one_the_merge_would_kill():
    """The push run is what CI just passed on; it is finished and not tied to the pull request."""
    assert sm.for_sha([run(event="push")], SHA) == []


# --- the decision ----------------------------------------------------------------------------------------


def test_it_waits_for_a_run_that_has_not_appeared_yet():
    """The run is created a second or three after the pull request opens — that gap is the whole bug."""
    assert sm.decide([], waited=2)["action"] == "wait"


def test_it_gives_up_waiting_for_a_run_that_never_appears():
    plan = sm.decide([], waited=90)
    assert plan["action"] == "go" and "nothing to prune" in plan["why"]


def test_a_blocked_run_counts_as_settled():
    """`action_required` is terminal, not pending: it is waiting for an approval nobody will give."""
    assert sm.decide([ghost()], waited=6)["action"] == "go"


def test_it_waits_while_the_run_is_still_going():
    assert sm.decide([run(status="queued", conclusion=None)], waited=3)["action"] == "wait"
    assert sm.decide([run(status="in_progress", conclusion=None)], waited=3)["action"] == "wait"


def test_one_finished_run_does_not_excuse_another_that_is_still_going():
    plan = sm.decide([run(), run(status="in_progress", conclusion=None)], waited=3)
    assert plan["action"] == "wait"


def test_it_merges_once_the_run_has_settled():
    plan = sm.decide([run()], waited=6)
    assert plan["action"] == "go" and "skipped" in plan["why"]


def test_a_run_that_really_ran_and_failed_still_lets_the_merge_through():
    """This step judges no run: the merge gate is CI on the push, decided before this ever runs."""
    plan = sm.decide([run(conclusion="failure")], waited=6)
    assert plan["action"] == "go"


# --- what may be deleted, and what may never be -----------------------------------------------------------


def test_the_blocked_run_with_no_jobs_is_a_ghost():
    assert sm.is_ghost(ghost(), jobs=0)
    assert sm.is_ghost(run(conclusion="failure"), jobs=0), "the same run, after the branch was deleted"


def test_a_run_whose_jobs_were_skipped_is_not_a_ghost():
    """#20's run 57: three jobs, all skipped by the condition in ci.yml. It ran. It stays."""
    assert not sm.is_ghost(run(conclusion="skipped"), jobs=3)


@pytest.mark.parametrize("run_, jobs", [
    (run(conclusion="success"), 0),                      # it passed: never delete it
    (run(conclusion="failure"), 3),                      # it failed for real: that red means something
    (run(status="in_progress", conclusion=None), 0),     # still going
    (run(conclusion=None), 0),                           # no conclusion yet
    (run(event="push", conclusion="failure"), 0),        # the push run is the gate, not ours to touch
])
def test_nothing_else_is_ever_a_ghost(run_, jobs):
    assert not sm.is_ghost(run_, jobs)


def test_pruning_deletes_the_corpse_and_says_so():
    deleted = []
    lines = sm.prune_ghost_runs("sprint/x", SHA, fetch=lambda b, s: [ghost(id=61)],
                                jobs_of=lambda rid: 0, delete=deleted.append, sleep=lambda s: None)
    assert deleted == [61]
    assert lines == [{"run": 61, "action": "deleted", "why": "action_required, no jobs, nothing ran"}]


def test_pruning_keeps_a_run_that_ran():
    deleted = []
    lines = sm.prune_ghost_runs("sprint/x", SHA, fetch=lambda b, s: [run(conclusion="skipped", id=57)],
                                jobs_of=lambda rid: 3, delete=deleted.append, sleep=lambda s: None)
    assert deleted == [] and lines[0]["action"] == "kept" and "it ran" in lines[0]["why"]


def test_a_dry_run_deletes_nothing():
    deleted = []
    lines = sm.prune_ghost_runs("sprint/x", SHA, fetch=lambda b, s: [ghost(id=61)], jobs_of=lambda rid: 0,
                                delete=deleted.append, dry_run=True, sleep=lambda s: None)
    assert deleted == [] and lines[0]["action"] == "would delete"


def test_a_refused_delete_is_not_a_failed_merge():
    """No permission, a rate limit: the worst case is the red run we already had."""
    def refuse(rid):
        raise RuntimeError("403 actions: write is required")

    lines = sm.prune_ghost_runs("sprint/x", SHA, fetch=lambda b, s: [ghost(id=61)], jobs_of=lambda rid: 0,
                                delete=refuse, sleep=lambda s: None)
    assert lines[0]["action"] == "kept" and "403" in lines[0]["why"]


def test_a_run_whose_jobs_cannot_be_counted_is_kept():
    def boom(rid):
        raise RuntimeError("rate limited")

    deleted = []
    lines = sm.prune_ghost_runs("sprint/x", SHA, fetch=lambda b, s: [ghost(id=61)], jobs_of=boom,
                                delete=deleted.append, sleep=lambda s: None)
    assert deleted == [], "never delete what you could not check"
    assert lines[0]["action"] == "kept"


def test_pruning_when_there_is_nothing_to_prune():
    deleted = []
    lines = sm.prune_ghost_runs("sprint/x", SHA, fetch=lambda b, s: [], jobs_of=lambda rid: 0,
                                delete=deleted.append, sleep=lambda s: None, appear=0)
    assert lines == [] and deleted == []


def test_waiting_never_holds_the_merge_forever():
    plan = sm.decide([run(status="in_progress", conclusion=None)], waited=240)
    assert plan["action"] == "go" and "rather than holding the branch" in plan["why"]


@pytest.mark.parametrize("waited", [0, 1, 30, 89, 90, 91, 239, 240, 1000])
def test_every_state_of_the_world_ends_in_go_or_wait_with_a_reason(waited):
    for runs in ([], [run()], [run(status="queued", conclusion=None)]):
        plan = sm.decide(runs, waited=waited)
        assert plan["action"] in ("go", "wait") and plan["why"]


# --- the loop --------------------------------------------------------------------------------------------


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def test_it_polls_until_the_run_appears_and_finishes():
    clock = Clock()
    answers = [[], [], [run(status="in_progress", conclusion=None)], [run()]]
    asked = []

    def fetch(branch, sha):
        asked.append((branch, sha))
        return answers.pop(0)

    plan, runs = sm.wait_for_pr_ci("sprint/x", SHA, fetch=fetch, sleep=clock.sleep, clock=clock, poll=5)
    assert plan["action"] == "go" and "settled" in plan["why"] and runs == [run()]
    assert asked == [("sprint/x", SHA)] * 4, "it asks again each time, with the branch and commit it was given"
    assert clock.now == 15, "three sleeps of five seconds, and no sleep after the answer that ended it"


def test_a_broken_gh_does_not_hold_the_merge():
    """No token, a rate limit, `gh` not installed: it says so on stderr and gives up when the window is up."""
    def fetch(branch, sha):
        raise OSError("gh: command not found")

    clock = Clock()
    plan, runs = sm.wait_for_pr_ci("sprint/x", SHA, fetch=fetch, sleep=clock.sleep, clock=clock, appear=20, poll=5)
    assert plan["action"] == "go" and runs == []
    assert clock.now == 20, "it stops asking once no run can be expected any more"


def test_the_run_that_ends_the_wait_is_not_slept_on_again():
    clock = Clock()
    plan, _ = sm.wait_for_pr_ci("sprint/x", SHA, fetch=lambda b, s: [run()], sleep=clock.sleep, clock=clock)
    assert plan["action"] == "go" and clock.now == 0


# --- the workflow calls it, before it merges ---------------------------------------------------------------


def test_the_workflow_prunes_before_it_merges():
    text = WORKFLOW.read_text()
    prune = text.find("scripts/sprint_merge.py prune-ghost-run")
    merge = text.find("gh pr merge")
    assert prune != -1, "the workflow does not call the script, so the ghost comes back"
    assert merge != -1 and prune < merge, "after the merge the branch is gone and so is the run's context"


def test_the_workflow_may_read_and_delete_the_runs():
    """A `permissions:` block sets everything it does not name to none, so this has to be spelled out."""
    text = WORKFLOW.read_text()
    block = text.split("permissions:")[1].split("jobs:")[0]
    assert "actions: write" in block, "without it the read 403s and the delete is refused"


def test_the_decision_is_not_inlined_in_the_yaml():
    text = WORKFLOW.read_text()
    assert "workflow_runs" not in text, "reading the runs belongs in the script, where these tests are"
