"""Guards for scripts/needs_human_issues.py, the escalation-to-issue workflow.

Escalations are the only way the agents reach a human, and the workflow that files them runs every six
hours by cron. On 2026-09-09 its dedupe check asked the issue *search* index whether the title already
existed; it answered no for an issue opened two and a half hours earlier, and the same request was filed
twice (#3 and #6). Nothing in CI noticed, because nothing tested it. These tests cover the decision the
workflow makes — file this, skip that — without touching GitHub.
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "needs_human_issues.py"
WORKFLOW = ROOT / ".github" / "workflows" / "needs-human.yml"


def load():
    spec = importlib.util.spec_from_file_location("needs_human_issues", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


nh = load()


@pytest.fixture
def folder(tmp_path):
    """A scratch sprint/needs-human/ with one request and the README the workflow must ignore."""
    d = tmp_path / "needs-human"
    d.mkdir()
    (d / "README.md").write_text("Escalations to the owner. This README is ignored by the workflow.\n")
    (d / "2026-09-09-signing.md").write_text(
        "# Add an Apple Developer signing certificate as a repo secret\n\n"
        "**Why:** unsigned DMGs scare people off.\n"
    )
    return d


def issue(title="", body=""):
    return {"number": 1, "title": title, "body": body}


def test_readme_and_non_markdown_are_not_requests(folder):
    (folder / "notes.txt").write_text("# Not a request\n")
    assert [p.name for p in nh.escalations(folder)] == ["2026-09-09-signing.md"]


def test_escalations_are_in_a_stable_order(folder):
    (folder / "2026-09-10-later.md").write_text("# Later\n")
    (folder / "2026-09-08-earlier.md").write_text("# Earlier\n")
    assert [p.name for p in nh.escalations(folder)] == [
        "2026-09-08-earlier.md", "2026-09-09-signing.md", "2026-09-10-later.md",
    ]


@pytest.mark.parametrize("text,title,rest", [
    ("# Title\n\nbody\n", "Title", "body"),
    ("### Title\nbody\n", "Title", "body"),
    ("#Title\n", "Title", ""),
    ("\n\n# Title\n\nbody\n", "Title", "body"),  # a leading blank line must not become the title
    ("", "", ""),
    ("\n \n", "", ""),
])
def test_the_first_real_line_is_the_title(text, title, rest):
    assert nh.split_title(text) == (title, rest)


def test_a_file_with_no_title_is_skipped_not_filed(folder):
    (folder / "2026-09-11-empty.md").write_text("\n")
    assert [i["name"] for i in nh.plan(folder, [])] == ["2026-09-09-signing.md"]


def test_a_new_file_is_filed(folder):
    todo = nh.plan(folder, [])
    assert len(todo) == 1
    assert todo[0]["title"] == "Add an Apple Developer signing certificate as a repo secret"
    assert "unsigned DMGs scare people off" in todo[0]["body"]
    assert todo[0]["body"].startswith("**Why:**"), "the title line is the issue title, not part of the body"
    assert "close this issue" in todo[0]["body"]
    assert nh.marker("2026-09-09-signing.md") in todo[0]["body"]


def test_a_file_that_already_has_an_issue_is_not_filed_again(folder):
    """The regression: #3 existed and the run opened #6 anyway."""
    opened = nh.plan(folder, [])[0]
    assert nh.plan(folder, [issue(title=opened["title"], body=opened["body"])]) == []


def test_the_marker_wins_over_the_title(folder):
    """An edited title must not open a second issue for the same file."""
    opened = nh.plan(folder, [])[0]
    assert nh.plan(folder, [issue(title="Something else entirely", body=opened["body"])]) == []


def test_an_issue_opened_before_markers_existed_still_counts(folder):
    """#2, #3 and #5 were opened by the old shell and carry no marker, only their title."""
    assert nh.plan(folder, [issue(title="Add an Apple Developer signing certificate as a repo secret")]) == []


def test_a_closed_issue_still_counts(folder):
    """The owner closes the issue; a later Research run moves the file to done/. Nothing is re-filed in
    between, so the caller asks for --state all and the decision here only sees issues, not their state."""
    opened = nh.plan(folder, [])[0]
    assert nh.plan(folder, [issue(title=opened["title"], body=opened["body"])]) == []


def test_someone_elses_issue_does_not_count(folder):
    assert len(nh.plan(folder, [issue(title="Unrelated", body="unrelated\n")])) == 1


def test_only_the_unfiled_files_are_filed(folder):
    (folder / "2026-09-10-second.md").write_text("# A second request\n\nbody\n")
    first = nh.plan(folder, [])[0]
    todo = nh.plan(folder, [issue(title=first["title"], body=first["body"])])
    assert [i["title"] for i in todo] == ["A second request"]


def test_the_real_escalation_folder_is_readable():
    """Every file the owner is waiting on parses, and none of them would be filed twice: each one's own
    marker is enough to recognise it."""
    real = ROOT / "sprint" / "needs-human"
    files = nh.escalations(real)
    assert files, "sprint/needs-human/ should hold the open escalations"
    for path in files:
        title, _ = nh.split_title(path.read_text())
        assert title, f"{path.name} has no title on its first line"
    todo = nh.plan(real, [])
    filed = [issue(title=i["title"], body=i["body"]) for i in todo]
    assert nh.plan(real, filed) == []


def test_the_script_runs(tmp_path):
    """`--help` must actually print: a script without an entry point exits 0 saying nothing, which is how
    scripts/e2e.py silently tested nothing for two days."""
    p = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr
    assert "--dry-run" in p.stdout


def test_dry_run_touches_nothing_and_needs_no_github(tmp_path, folder, monkeypatch):
    """With gh unreachable a dry run still reports; a real run must never guess."""
    p = subprocess.run(
        [sys.executable, str(SCRIPT), "--dir", str(folder), "--dry-run"],
        capture_output=True, text=True, timeout=60, env={"PATH": "/nonexistent", **{"HOME": str(tmp_path)}},
    )
    assert p.returncode == 0, p.stderr
    assert "would open: Add an Apple Developer signing certificate" in p.stdout


def test_the_workflow_calls_the_script_and_not_the_search_index():
    text = WORKFLOW.read_text()
    assert "scripts/needs_human_issues.py" in text
    assert "--search" not in text, "the search index is what filed #3 and #6 twice"
    assert "gh issue create" not in text, "creating issues belongs in the script, where it is tested"
