"""Guards for scripts/nightly_watchdog.py, which notices when the nightly QA run stops reporting.

The nightly writes `sprint/log/YYYY-MM-DD-nightly.md` when it runs and opens an issue when it fails. When it
never starts it does neither, and in week 37 that silence — four nights of it — was caught only because an
agent remembered the log was there yesterday and noticed it wasn't today (#12). These tests cover the
decision the watchdog makes without touching GitHub: `decide()` is the whole of it, and nothing below calls
`gh`.
"""
import importlib.util
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "nightly_watchdog.py"
WORKFLOW = ROOT / ".github" / "workflows" / "nightly-watchdog.yml"
NOW = datetime(2026, 9, 15, 15, 23, tzinfo=timezone.utc)  # when the cron fires


def load():
    spec = importlib.util.spec_from_file_location("nightly_watchdog", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


wd = load()


@pytest.fixture
def logs(tmp_path):
    """A scratch sprint/log/ holding the other agents' logs, which are not nightly logs."""
    d = tmp_path / "log"
    d.mkdir()
    (d / "2026-09-15-build.md").write_text("# Build\n")
    (d / "2026-09-14-community.md").write_text("# Community\n")
    return d


def nightly(folder: Path, days_ago: int) -> str:
    """A nightly log dated that many days before NOW."""
    name = f"{(NOW - timedelta(days=days_ago)).date().isoformat()}-nightly.md"
    (folder / name).write_text("# Nightly\n\n**Verdict: PASS**\n")
    return name


def issue(number=42, body="", title="An issue"):
    return {"number": number, "title": title, "body": body}


def reported():
    """The issue the watchdog opened on an earlier run."""
    return issue(body=f"The newest nightly log is old.\n\n{wd.MARKER}\n")


# --- the four cases the board asked for ------------------------------------------------------------


def test_a_fresh_log_is_nothing_to_report(logs):
    nightly(logs, 1)
    assert wd.decide(logs, [], NOW)["action"] == "nothing"


def test_a_stale_log_opens_one_issue(logs):
    name = nightly(logs, 5)
    plan = wd.decide(logs, [], NOW)
    assert plan["action"] == "open"
    assert plan["title"] == "The nightly QA run has not reported since 2026-09-10"
    assert name in plan["body"] and "5 day(s) ago" in plan["body"]
    assert wd.MARKER in plan["body"], "without the marker the next run opens a second issue"


def test_a_stale_log_that_already_has_an_issue_opens_no_second_one(logs):
    """The regression this shape of script exists to avoid: needs-human asked the search index and filed
    #3 and #6 for the same request."""
    nightly(logs, 5)
    plan = wd.decide(logs, [reported()], NOW)
    assert plan["action"] == "nothing"
    assert "#42" in plan["why"]


def test_no_logs_at_all_is_not_silence(logs):
    """A repository that has never run a nightly has nothing to be silent about."""
    assert wd.decide(logs, [], NOW)["action"] == "nothing"
    assert wd.decide(ROOT / "does-not-exist", [], NOW)["action"] == "nothing"


# --- the edges of the threshold ---------------------------------------------------------------------


@pytest.mark.parametrize("days_ago,action", [(0, "nothing"), (1, "nothing"), (2, "open"), (3, "open")])
def test_today_and_yesterday_are_fresh_and_anything_older_is_not(logs, days_ago, action):
    """The date in the name counts as 00:00 UTC, so a log from the night before last is already more than
    48 hours old by the time the cron fires — one missed night is the signal."""
    nightly(logs, days_ago)
    assert wd.decide(logs, [], NOW)["action"] == action


def test_the_threshold_is_a_setting(logs):
    nightly(logs, 3)
    assert wd.decide(logs, [], NOW, threshold=48)["action"] == "open"
    assert wd.decide(logs, [], NOW, threshold=24 * 7)["action"] == "nothing"


def test_the_newest_log_decides_not_the_first_one_found(logs):
    nightly(logs, 9)
    nightly(logs, 1)
    nightly(logs, 5)
    assert wd.decide(logs, [], NOW)["action"] == "nothing"


def test_a_file_that_is_not_a_dated_nightly_log_is_not_one(logs):
    (logs / "README-nightly.md").write_text("notes about the nightly\n")
    (logs / "2026-13-45-nightly.md").write_text("not a date\n")
    (logs / "2026-09-15-nightly.txt").write_text("not markdown\n")
    assert wd.nightly_logs(logs) == []
    assert wd.decide(logs, [], NOW)["action"] == "nothing"


def test_the_other_agents_logs_are_not_nightly_logs(logs):
    """Build and Community write to the same folder every day; only the nightly's own name counts."""
    nightly(logs, 5)
    assert [name for _, name in wd.nightly_logs(logs)] == ["2026-09-10-nightly.md"]


# --- recovery ----------------------------------------------------------------------------------------


def test_a_log_landing_closes_the_issue(logs):
    """Beyond what the board asked for, and the reason the watchdog works twice: an issue left open after
    the nightly recovers would suppress the next silence, since dedupe is by marker."""
    name = nightly(logs, 0)
    plan = wd.decide(logs, [reported()], NOW)
    assert plan["action"] == "close" and plan["number"] == 42
    assert name in plan["comment"]


def test_someone_elses_issue_is_not_this_watchdogs(logs):
    nightly(logs, 5)
    assert wd.decide(logs, [issue(body="The nightly is quiet, I think")], NOW)["action"] == "open"


def test_a_closed_issue_does_not_suppress_a_new_silence(logs):
    """Unlike needs-human, where the file waits for a human, this condition is live: `open_issues()` asks
    for open issues only, so a silence that returns after the owner fixed it is news again."""
    nightly(logs, 5)
    assert wd.decide(logs, [], NOW)["action"] == "open", "a closed issue is simply not in the list"


# --- the script and the workflow ----------------------------------------------------------------------


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, timeout=60,
                          env={"PATH": "/nonexistent", "HOME": "/tmp"})


def test_the_script_runs():
    """`--help` must actually print: a script without an entry point exits 0 saying nothing, which is how
    scripts/e2e.py silently tested nothing for two days."""
    p = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr
    assert "--dry-run" in p.stdout


def test_a_dry_run_reports_without_gh_and_opens_nothing(logs):
    """With gh unreachable a dry run still says what it would do; a real run raises instead of guessing."""
    nightly(logs, 5)
    p = run("--dir", str(logs), "--dry-run")
    assert p.returncode == 0, p.stderr
    assert "open: 2026-09-10-nightly.md is" in p.stdout


def test_a_real_run_without_gh_fails_rather_than_guessing(logs):
    nightly(logs, 5)
    p = run("--dir", str(logs))
    assert p.returncode != 0, "opening an issue without knowing which ones exist is how #3 was filed twice"


def test_the_workflow_calls_the_script_and_may_write_issues():
    text = WORKFLOW.read_text()
    assert "scripts/nightly_watchdog.py" in text
    assert "gh issue create" not in text, "the decision belongs in the script, where it is tested"
    assert "issues: write" in text and "schedule:" in text


def test_the_real_log_folder_reads():
    """The repository's own logs must parse, whatever the watchdog decides about them today."""
    found = wd.nightly_logs(ROOT / "sprint" / "log")
    assert found, "sprint/log/ should hold at least one nightly log"
    assert all(name.endswith("-nightly.md") for _, name in found)
