"""Guards for scripts/sprint_merge.py, which decides when Sprint merge may squash-merge.

The merge bot opened a pull request and merged it three seconds later, which killed the CI run that pull
request had just started: zero jobs, nothing run, permanently red in the history (#19 measured it — opened
03:12:12, merged 03:12:15, run created 03:12:15, dead at 03:12:17). Since #19 that run's jobs skip instead
of running, and a probe pull request that was left open long enough concluded `skipped` in one second — so
all this needs is for the merge to wait that second out.

What must not regress: waiting is never allowed to hold a merge. A branch that does not merge is a worse
problem than a run that goes red, so every path through `decide()` ends in `go` sooner or later.
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


def run(status="completed", conclusion="skipped", sha=SHA, event="pull_request"):
    return {"status": status, "conclusion": conclusion, "head_sha": sha, "event": event}


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
    assert plan["action"] == "go" and "none to kill" in plan["why"]


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
    """This step is about not *killing* a run, not about judging it — the merge gate is CI on the push."""
    plan = sm.decide([run(conclusion="failure")], waited=6)
    assert plan["action"] == "go"


def test_waiting_never_holds_the_merge_forever():
    plan = sm.decide([run(status="in_progress", conclusion=None)], waited=240)
    assert plan["action"] == "go" and "merging anyway" in plan["why"]


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

    plan = sm.wait_for_pr_ci("sprint/x", SHA, fetch=fetch, sleep=clock.sleep, clock=clock, poll=5)
    assert plan["action"] == "go" and "settled" in plan["why"]
    assert asked == [("sprint/x", SHA)] * 4, "it asks again each time, with the branch and commit it was given"
    assert clock.now == 15, "three sleeps of five seconds, and no sleep after the answer that ended it"


def test_a_broken_gh_does_not_hold_the_merge():
    """No token, a rate limit, `gh` not installed: it says so on stderr and merges when the window is up."""
    def fetch(branch, sha):
        raise OSError("gh: command not found")

    clock = Clock()
    plan = sm.wait_for_pr_ci("sprint/x", SHA, fetch=fetch, sleep=clock.sleep, clock=clock, appear=20, poll=5)
    assert plan["action"] == "go"
    assert clock.now == 20, "it stops asking once no run can be expected any more"


def test_the_run_that_ends_the_wait_is_not_slept_on_again():
    clock = Clock()
    plan = sm.wait_for_pr_ci("sprint/x", SHA, fetch=lambda b, s: [run()], sleep=clock.sleep, clock=clock)
    assert plan["action"] == "go" and clock.now == 0


# --- the workflow calls it, before it merges ---------------------------------------------------------------


def test_the_workflow_waits_before_it_merges():
    text = WORKFLOW.read_text()
    wait = text.find("scripts/sprint_merge.py wait-for-pr-ci")
    merge = text.find("gh pr merge")
    assert wait != -1, "the workflow does not call the script, so nothing waits and the ghost comes back"
    assert merge != -1 and wait < merge, "waiting after the merge would be waiting for a run already dead"


def test_the_workflow_may_read_the_runs():
    """A `permissions:` block sets everything it does not name to none, so this has to be spelled out."""
    text = WORKFLOW.read_text()
    block = text.split("permissions:")[1].split("jobs:")[0]
    assert "actions: read" in block, "without it `gh api .../actions/runs` 403s and every merge waits blind"


def test_the_decision_is_not_inlined_in_the_yaml():
    text = WORKFLOW.read_text()
    assert "workflow_runs" not in text, "reading the runs belongs in the script, where these tests are"
