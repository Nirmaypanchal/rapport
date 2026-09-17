"""Guards for scripts/sprint_merge.py, which opens, merges and cleans up after Sprint merge's pull request.

Two things it must never do, each with its own history.

**It must never report success having merged nothing.** The workflow used to end `gh pr create` with
`|| true`. On 2026-09-09 "Allow GitHub Actions to create and approve pull requests" was off, `gh` said so and
exited non-zero, `|| true` ate it, and the job went green twice with no pull request anywhere
(`sprint/needs-human/done/2026-09-09-actions-cannot-open-prs.md`). So: every `gh` call is checked, opening a
pull request is followed by asking whether one now exists, and arriving at the merge with nothing to merge is
an error. A hold is different from a failure and stays quiet-but-spoken: `needs-human` is never merged, a red
branch gets a comment.

**It must never delete a CI run that ran.** Every auto-merge left a red CI run behind. The merge bot opens
its pull request with `GITHUB_TOKEN`, and GitHub will not run a workflow for an event that token created:
the run is filed `action_required` with zero jobs and goes red the moment `gh pr merge --delete-branch`
removes the branch under it (#22: blocked at 03:27:54, red at 03:28:01). Nothing in `ci.yml` can rescue a
run that was never allowed to start, so the merge deletes it instead. A run whose jobs were all skipped by a
condition still lists all three of them (#20's run 57), so zero jobs separates a corpse from a real run.
And **none of that may hold a merge**: no run, a broken `gh`, a refused delete, a run that keeps going —
every path returns and lets the merge happen. (That is the one part of this script allowed to swallow an
error, and only because the worst case is the red run we already had.)
"""
import importlib.util
import subprocess
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


def pr(number=7, labels=()):
    """One entry as `gh pr list --json number,labels` gives it."""
    return {"number": number, "labels": [{"name": n} for n in labels]}


class Gh:
    """A `gh` that records what it was asked to do, and can be told to fail like the real one."""

    def __init__(self, fail_on=None):
        self.calls = []
        self.fail_on = fail_on

    def __call__(self, argv):
        self.calls.append(argv)
        if self.fail_on and self.fail_on in argv:
            raise subprocess.CalledProcessError(1, argv, stderr="GitHub Actions is not permitted to …")

    def did(self, verb):
        return [c for c in self.calls if len(c) > 2 and c[2] == verb]


# --- opening the pull request: the failure that went unnoticed twice ---------------------------------------


def test_a_branch_with_no_pull_request_gets_one():
    assert sm.open_plan([])["action"] == "open"


def test_a_branch_that_already_has_one_reuses_it():
    """A pull request outlives the pushes to its branch; only the first push of a branch opens one."""
    plan = sm.open_plan([pr(number=31)])
    assert plan == {"action": "reuse", "number": 31, "why": "#31 is already open for this branch"}


def test_opening_uses_the_commit_as_the_title_and_body():
    """AGENTS.md: the commit's first line is the PR title, its body the description."""
    gh = Gh()
    sm.ensure_pull_request("sprint/x", SHA, "success", prs=lambda b: [] if not gh.calls else [pr()],
                           commit=lambda s: ("Ship the thing", "Why it was shipped."),
                           create=lambda b, t, body: gh(["gh", "pr", "create", b, t, body]))
    _, _, _, branch, title, body = gh.calls[0]
    assert (branch, title) == ("sprint/x", "Ship the thing")
    assert "Why it was shipped." in body and "sprint/x" in body and "**success**" in body


def test_a_red_branch_still_gets_a_pull_request():
    """Otherwise a failure nobody opened a pull request for is a failure nobody can see."""
    opened = []
    sm.ensure_pull_request("sprint/x", SHA, "failure", prs=lambda b: [pr()] if opened else [],
                           commit=lambda s: ("Broken", ""),
                           create=lambda b, t, body: opened.append(body))
    assert opened and "**failure**" in opened[0]


def test_a_create_that_leaves_no_pull_request_is_an_error():
    """The 2026-09-09 shape: the step "succeeds" and there is nothing to merge. This is what `|| true` hid."""
    asked = []
    with pytest.raises(sm.Stopped) as e:
        sm.ensure_pull_request("sprint/x", SHA, "success", prs=lambda b: asked.append(b) or [],
                               commit=lambda s: ("t", "b"), create=lambda b, t, body: None,
                               sleep=lambda s: None)
    assert "Allow GitHub Actions" in str(e.value), "the message has to name the setting that was off"
    assert len(asked) > 2, "it asks more than once before calling a pull request missing"


def test_a_pull_request_that_shows_up_a_moment_later_is_not_a_failure():
    """The list is asked again rather than once: a red job for a pull request that does exist would be a
    worse lie than the one this whole change is about."""
    answers = [[], [], [pr(number=9)]]
    plan = sm.ensure_pull_request("sprint/x", SHA, "success", prs=lambda b: answers.pop(0),
                                  commit=lambda s: ("t", "b"), create=lambda b, t, body: None,
                                  sleep=lambda s: None)
    assert plan == {"action": "opened", "number": 9, "why": "opened #9 from sprint/x"}


def test_a_failing_create_is_not_swallowed():
    gh = Gh(fail_on="create")
    with pytest.raises(subprocess.CalledProcessError):
        sm.ensure_pull_request("sprint/x", SHA, "success", prs=lambda b: [], commit=lambda s: ("t", "b"),
                               create=lambda b, t, body: gh(["gh", "pr", "create"]))


def test_a_dry_run_opens_nothing():
    gh = Gh()
    plan = sm.ensure_pull_request("sprint/x", SHA, "success", prs=lambda b: [], commit=lambda s: ("t", "b"),
                                  create=lambda b, t, body: gh(["gh", "pr", "create"]), dry_run=True)
    assert plan["action"] == "would open" and gh.calls == []


# --- merging, holding, or saying why not -------------------------------------------------------------------


def test_a_green_branch_is_merged():
    gh = Gh()
    plan = sm.merge_when_green("sprint/x", SHA, "success", prs=lambda b: [pr(number=31)], run=gh)
    assert plan["action"] == "merge"
    assert gh.did("merge")[0] == ["gh", "pr", "merge", "31", "--squash", "--delete-branch",
                                  "--body", f"Merged automatically: CI passed on {SHA}."]


def test_a_needs_human_pull_request_is_held_not_merged():
    """AGENTS.md: anything a human must see first never merges by itself."""
    gh = Gh()
    plan = sm.merge_when_green("sprint/x", SHA, "success", prs=lambda b: [pr(labels=["sprint", "needs-human"])],
                               run=gh)
    assert plan["action"] == "hold" and gh.calls == []
    assert "needs-human" in plan["why"], "a hold has to say what held it"


def test_a_red_branch_is_commented_on_and_not_merged():
    gh = Gh()
    plan = sm.merge_when_green("sprint/x", SHA, "failure", prs=lambda b: [pr(number=31)], run=gh)
    assert plan["action"] == "note" and gh.did("merge") == []
    body = gh.did("comment")[0][-1]
    assert "failure" in body and SHA in body and "next Build run" in body


def test_a_red_branch_is_commented_on_even_when_it_is_held():
    """The comment is how the next Build run finds a red branch; a label must not hide it."""
    gh = Gh()
    plan = sm.merge_when_green("sprint/x", SHA, "failure", prs=lambda b: [pr(labels=["needs-human"])], run=gh)
    assert plan["action"] == "note" and gh.did("comment")


@pytest.mark.parametrize("result", ["failure", "cancelled", "timed_out", "startup_failure", "neutral", ""])
def test_nothing_but_success_ever_merges(result):
    gh = Gh()
    sm.merge_when_green("sprint/x", SHA, result, prs=lambda b: [pr()], run=gh)
    assert gh.did("merge") == []


def test_reaching_the_merge_with_no_pull_request_is_an_error():
    """Two steps earlier one was opened or found. If it is gone now, this run merged nothing: say so."""
    gh = Gh()
    with pytest.raises(sm.Stopped):
        sm.merge_when_green("sprint/x", SHA, "success", prs=lambda b: [], run=gh)
    assert gh.calls == []


def test_a_failing_merge_is_not_swallowed():
    gh = Gh(fail_on="merge")
    with pytest.raises(subprocess.CalledProcessError):
        sm.merge_when_green("sprint/x", SHA, "success", prs=lambda b: [pr()], run=gh)


def test_a_dry_run_merges_nothing():
    gh = Gh()
    plan = sm.merge_when_green("sprint/x", SHA, "success", prs=lambda b: [pr()], run=gh, dry_run=True)
    assert plan["action"] == "would merge" and gh.calls == []


def test_every_state_of_the_world_is_merge_hold_note_or_stop():
    for prs in ([], [pr()], [pr(labels=["needs-human"])]):
        for result in ("success", "failure", None):
            plan = sm.merge_plan(prs, result)
            assert plan["action"] in ("merge", "hold", "note", "stop") and plan["why"]


# --- the command line the workflow actually calls -----------------------------------------------------------


def test_the_script_exits_non_zero_when_nothing_could_be_merged(monkeypatch, capsys):
    """The workflow has no `|| true` any more, so this exit code is what turns the job red."""
    monkeypatch.setattr(sm, "open_pull_requests", lambda b: [])
    assert sm.main(["merge", "--branch", "sprint/x", "--sha", SHA, "--result", "success"]) == 1
    assert "sprint-merge stopped" in capsys.readouterr().err


def test_the_script_exits_non_zero_when_gh_fails(monkeypatch, capsys):
    def boom(argv):
        raise subprocess.CalledProcessError(1, argv, stderr="GitHub Actions is not permitted …")

    monkeypatch.setattr(sm, "open_pull_requests", lambda b: [pr()])
    monkeypatch.setattr(sm, "gh", boom)
    assert sm.main(["merge", "--branch", "sprint/x", "--sha", SHA, "--result", "failure"]) == 1
    assert "not permitted" in capsys.readouterr().err, "what gh said has to reach the log"


def test_the_script_exits_zero_on_a_hold(monkeypatch, capsys):
    """A hold is a decision, not a failure: green job, and the reason on stdout."""
    monkeypatch.setattr(sm, "open_pull_requests", lambda b: [pr(labels=["needs-human"])])
    assert sm.main(["merge", "--branch", "sprint/x", "--sha", SHA, "--result", "success"]) == 0
    assert "held" in capsys.readouterr().out


def test_pruning_a_run_never_fails_the_job(monkeypatch):
    """Even with `gh` gone: the prune step must not be what stops a branch merging. `--appear 0` is how
    this returns without ever sleeping, so the test is as fast as the others."""
    def no_gh(*a, **k):
        raise FileNotFoundError("gh: command not found")

    monkeypatch.setattr(sm.subprocess, "run", no_gh)  # the real `fetch_runs`, with nothing to call
    assert sm.main(["prune-ghost-run", "--branch", "sprint/x", "--sha", SHA, "--appear", "0"]) == 0


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


def workflow() -> str:
    """The workflow without its comments — which describe `|| true` and `if:` at length, and would
    otherwise answer the questions the guards below are asking of the steps themselves."""
    return "\n".join(l for l in WORKFLOW.read_text().splitlines() if not l.lstrip().startswith("#"))


def steps() -> list[str]:
    """The subcommands the workflow calls, in the order it calls them."""
    text = workflow()
    found = [(text.find(f"sprint_merge.py {c}"), c) for c in ("open-pr", "prune-ghost-run", "merge")]
    missing = [c for at, c in found if at == -1]
    assert not missing, f"the workflow no longer calls: {missing}"
    return [c for _, c in sorted(found)]


def test_the_workflow_opens_then_prunes_then_merges():
    """Order is load-bearing: there is nothing to prune before the pull request exists, and after the
    merge the branch is gone and so is the run's context."""
    assert steps() == ["open-pr", "prune-ghost-run", "merge"]


def test_the_workflow_swallows_nothing():
    """The regression this item exists to stop: `gh pr create … || true` reported success having opened
    and merged nothing, twice, on 2026-09-09. Nothing in this workflow may end that way again."""
    text = workflow()
    assert "|| true" not in text, "a step that cannot fail cannot tell you the merge bot stopped working"
    assert "exit 0" not in text, "an early exit hides the same thing `|| true` did"


def test_the_merge_step_has_no_condition_on_it():
    """Splitting merge and comment across two `if:`-ed steps is how a run could satisfy neither and still
    go green. One step now decides, and it always decides something."""
    after = workflow().split("sprint_merge.py merge")[0].rsplit("- name:", 1)[-1]
    assert "if:" not in after, "the merge step must run for every conclusion and decide in the script"


def test_the_workflow_may_read_and_delete_the_runs():
    """A `permissions:` block sets everything it does not name to none, so this has to be spelled out."""
    text = WORKFLOW.read_text()
    block = text.split("permissions:")[1].split("jobs:")[0]
    assert "actions: write" in block, "without it the read 403s and the delete is refused"


def test_the_decision_is_not_inlined_in_the_yaml():
    """Logic in a workflow is untested logic (sprint/skills/all-sprint-automation.md)."""
    text = WORKFLOW.read_text()
    assert "workflow_runs" not in text, "reading the runs belongs in the script, where these tests are"
    for shell in ("gh pr create", "gh pr merge", "gh pr comment", "gh pr list", "--jq"):
        assert shell not in text, f"`{shell}` is back in the YAML, where no test can reach it"
