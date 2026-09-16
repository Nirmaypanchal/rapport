"""Guards for `.github/workflows/ci.yml`'s decision about *when* CI runs.

Every auto-merge used to leave a red run behind. `ci.yml` had a bare `pull_request:` trigger, so the pull
request the merge bot opens for a `sprint/*` branch started a second CI run for a commit `push` had already
tested — and `gh pr merge --squash --delete-branch` seconds later killed it before a single job started: zero
jobs, nothing run, permanently red. Four of week 37's 17 CI runs were these, and a history where red means
nothing is a history nobody reads.

The fix is a condition on each job, and a condition in a workflow is untested logic unless something runs it.
So these tests evaluate the real expression out of the real file against made-up events, rather than asserting
how it is spelled. The evaluator below understands only the handful of operators the condition uses and raises
on anything else, so a rewrite into a form it cannot read fails loudly instead of passing quietly.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
REPO = "Nirmaypanchal/rapport"


# --- reading the workflow (no PyYAML in the light environment) -------------------------------------------


def job_conditions(text: str) -> dict[str, str | None]:
    """Every job in `jobs:` mapped to its `if:` expression, or None when it has none."""
    lines = text.splitlines()
    jobs: dict[str, str | None] = {}
    current, in_jobs = None, False
    for i, line in enumerate(lines):
        if line.startswith("jobs:"):
            in_jobs = True
            continue
        if not in_jobs or not line.strip() or line.lstrip().startswith("#"):
            continue
        if re.fullmatch(r"  ([A-Za-z0-9_.-]+):", line.rstrip()):
            current = line.strip().rstrip(":")
            jobs[current] = None
            continue
        m = re.fullmatch(r"    if: (.*)", line.rstrip())
        if m and current:
            value = m.group(1).strip()
            if value in (">-", ">", "|", "|-"):  # a folded block: the lines under it, joined
                more = []
                for nxt in lines[i + 1:]:
                    if not nxt.strip() or not nxt.startswith("      "):
                        break
                    more.append(nxt.strip())
                value = " ".join(more)
            jobs[current] = value.removeprefix("${{").removesuffix("}}").strip()
    return jobs


def push_branches(text: str) -> list[str]:
    """The branch patterns of the `push:` trigger, e.g. ['main', 'sprint/**', 'draft/**']."""
    m = re.search(r"push:.*branches: \[([^\]]*)\]", text)
    assert m, "the push trigger is not in the shape this test can read"
    return [b.strip().strip("'\"") for b in m.group(1).split(",")]


# --- evaluating one (small) GitHub Actions expression ----------------------------------------------------


def resolve(path: str, ctx: dict):
    value = ctx
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None  # a missing context value is null in Actions, as it is here
        value = value[part]
    return value


def split_top(expr: str, sep: str) -> list[str]:
    parts, depth, cur, i = [], 0, "", 0
    while i < len(expr):
        c = expr[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        if depth == 0 and expr.startswith(sep, i):
            parts.append(cur)
            cur, i = "", i + len(sep)
            continue
        cur, i = cur + c, i + 1
    parts.append(cur)
    return [p.strip() for p in parts]


def evaluate(expr: str, ctx: dict) -> bool:
    assert "&&" not in expr, "this evaluator reads `||`, `!`, `==`, `!=` and startsWith(), nothing else"
    ors = split_top(expr, "||")
    if len(ors) > 1:
        return any(evaluate(part, ctx) for part in ors)
    expr = expr.strip()
    if expr.startswith("!(") and expr.endswith(")"):
        return not evaluate(expr[2:-1], ctx)
    if expr.startswith("(") and expr.endswith(")"):
        return evaluate(expr[1:-1], ctx)
    m = re.fullmatch(r"startsWith\(([\w.]+), '([^']*)'\)", expr)
    if m:
        value = resolve(m.group(1), ctx)
        return isinstance(value, str) and value.startswith(m.group(2))
    m = re.fullmatch(r"([\w.]+) (==|!=) (?:'([^']*)'|([\w.]+))", expr)
    if m:
        value = resolve(m.group(1), ctx)
        wanted = m.group(3) if m.group(3) is not None else resolve(m.group(4), ctx)
        return value == wanted if m.group(2) == "==" else value != wanted
    raise AssertionError(f"the test's evaluator does not understand {expr!r}; teach it or keep the shape")


def github(event_name: str, *, head_ref: str | None = None, head_repo: str | None = None) -> dict:
    """The `github` context as CI sees it for one event."""
    ctx = {"event_name": event_name, "repository": REPO, "event": {}}
    if event_name == "pull_request":
        ctx["event"]["pull_request"] = {"head": {"ref": head_ref, "repo": {"full_name": head_repo}}}
    elif head_ref:
        ctx["ref"] = f"refs/heads/{head_ref}"
    return {"github": ctx}


def runs(event_name: str, **kwargs) -> bool:
    """Does every job of the real ci.yml run for this event? (They share one condition.)"""
    conditions = {c for c in job_conditions(WORKFLOW.read_text()).values()}
    assert len(conditions) == 1, f"the jobs no longer agree on when CI runs: {conditions}"
    condition = conditions.pop()
    assert condition, "the jobs have no condition at all, so every auto-merge leaves a ghost run again"
    return evaluate(condition, github(event_name, **kwargs))


# --- what the condition must decide ----------------------------------------------------------------------


def test_a_push_always_runs():
    assert runs("push", head_ref="main")
    assert runs("push", head_ref="sprint/ci-ghost-run")
    assert runs("push", head_ref="draft/something")


@pytest.mark.parametrize("branch", ["sprint/ci-ghost-run", "sprint/a/b", "draft/experiment"])
def test_our_own_pull_request_does_not_run_again(branch):
    """This is the ghost: `push` tested this exact commit minutes ago on this same repository."""
    assert not runs("pull_request", head_ref=branch, head_repo=REPO)


def test_every_branch_the_push_trigger_covers_is_skipped_on_a_pull_request():
    """If the push filter grows a branch pattern, the condition has to grow with it — or ghosts come back."""
    for pattern in push_branches(WORKFLOW.read_text()):
        branch = pattern.replace("/**", "/x").replace("**", "x")
        assert not runs("pull_request", head_ref=branch, head_repo=REPO), f"{pattern} would leave a ghost"


def test_a_fork_still_gets_ci():
    """`push` never fires on this repository for a fork's branch, so the pull request is the only CI there is."""
    assert runs("pull_request", head_ref="sprint/whatever", head_repo="contributor/rapport")
    assert runs("pull_request", head_ref="patch-1", head_repo="contributor/rapport")


def test_a_branch_outside_the_push_filter_still_gets_ci():
    """A same-repo branch `push` does not cover (someone's `fix/…`) must not fall through the gap."""
    assert runs("pull_request", head_ref="fix/typo", head_repo=REPO)
    assert runs("pull_request", head_ref="renovate/next", head_repo=REPO)


def test_the_pull_request_trigger_is_still_there():
    """Deleting the trigger would also stop the ghosts — and stop testing every contribution from a fork."""
    text = WORKFLOW.read_text()
    assert re.search(r"^  pull_request:", text, re.M), "forks would get no CI at all"
    assert "branches:" not in text.split("pull_request:")[1].split("jobs:")[0], (
        "a `branches:` filter here matches the *base*, which is always main, so it cannot narrow this"
    )


def test_the_jobs_are_all_still_there():
    jobs = job_conditions(WORKFLOW.read_text())
    assert set(jobs) == {"frontend", "backend-light", "backend"}
