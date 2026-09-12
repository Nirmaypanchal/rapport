#!/usr/bin/env python3
"""One GitHub issue per escalation file in sprint/needs-human/, opened exactly once.

    scripts/needs_human_issues.py                     # open an issue for every file that has none
    scripts/needs_human_issues.py --dry-run           # print what it would open, change nothing
    scripts/needs_human_issues.py --dir DIR           # read another folder (tests)

Run by .github/workflows/needs-human.yml: on every push to main that touches the folder, and every six
hours by cron. Needs `gh` on PATH and GH_TOKEN in the environment. See AGENTS.md, "Escalating to the owner".

Why a script and not four lines of shell: the workflow used to ask the issue *search* index whether an
issue with the same title already existed (`gh issue list --search '"<title>" in:title'`). Search is
fuzzy and eventually consistent, and on 2026-09-09 it did not find an issue opened two and a half hours
earlier, so the same request was filed twice (#3 and #6). The cron re-runs every six hours, so an
unresolved file would have kept opening issues — and emailing the owner — indefinitely. This asks the
list API instead (immediate, exact, no index in the way) and recognises the issues it already opened by
a marker carrying the file name, so editing a file's title does not open a second issue either.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

LABEL = "needs-human"
OWNER = "Nirmaypanchal"
MARKER = "needs-human-file"
ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIR = ROOT / "sprint" / "needs-human"
FOOTER = "From `{path}`. When done, close this issue; the sprint moves the file to `done/`."


def marker(name: str) -> str:
    """The line that lets a later run recognise the issue it already opened for a file."""
    return f"<!-- {MARKER}: {name} -->"


def escalations(folder: Path) -> list[Path]:
    """Every escalation file in the folder, in a stable order. README.md is documentation, not a request."""
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.glob("*.md") if p.name != "README.md")


def split_title(text: str) -> tuple[str, str]:
    """The first non-empty line without its leading `#` is the title; everything after it is the body.
    A file with nothing in it has no title, and is skipped rather than filed."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip():
            return line.strip().lstrip("#").strip(), "\n".join(lines[i + 1:]).strip("\n")
    return "", ""


def body_of(rest: str, path: str, name: str) -> str:
    """The issue body: the file minus its title, the note about closing it, and the marker."""
    return f"{rest}\n\n---\n{FOOTER.format(path=path)}\n\n{marker(name)}\n"


def already_filed(name: str, title: str, issues: list[dict]) -> bool:
    """True when one of the existing issues was opened for this file."""
    mark = marker(name)
    for issue in issues:
        if mark in (issue.get("body") or ""):
            return True
        if title and (issue.get("title") or "").strip() == title:
            # Issues opened before the marker existed (#2, #3, #5) carry only their title.
            return True
    return False


def plan(folder: Path, issues: list[dict], base: Path = ROOT) -> list[dict]:
    """The issues that still have to be opened, one entry per file, in file order."""
    todo = []
    for path in escalations(folder):
        title, rest = split_title(path.read_text())
        if not title:
            print(f"skip (no title on the first line): {path}", file=sys.stderr)
            continue
        if already_filed(path.name, title, issues):
            continue
        try:
            shown = str(path.resolve().relative_to(base))
        except ValueError:
            shown = str(path)
        todo.append({"name": path.name, "title": title, "body": body_of(rest, shown, path.name)})
    return todo


def existing_issues() -> list[dict]:
    """Every issue ever labeled needs-human, open or closed, from the list API — not the search index.
    Closed counts: the owner closes the issue when it is done and a later run moves the file to done/,
    and nothing should be re-filed in between."""
    limit = 500
    out = subprocess.run(
        ["gh", "issue", "list", "--label", LABEL, "--state", "all", "--limit", str(limit),
         "--json", "number,title,body"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    issues = json.loads(out) if out else []
    if len(issues) >= limit:
        # Older issues fell off the end, so a very old file could be filed twice. Nowhere near this yet.
        print(f"warning: {limit} issues is the whole page; raise the limit", file=sys.stderr)
    return issues


def create_issue(title: str, body: str, assignee: str) -> None:
    """`gh issue create`, with the body through a file so its length and quoting cannot bite."""
    fd, tmp = tempfile.mkstemp(suffix=".md")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(body)
        subprocess.run(
            ["gh", "issue", "create", "--title", title, "--body-file", tmp,
             "--label", LABEL, "--assignee", assignee],
            check=True,
        )
    finally:
        os.unlink(tmp)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", type=Path, default=DEFAULT_DIR, help="folder of escalation files")
    ap.add_argument("--assignee", default=OWNER, help="who the issue is assigned to")
    ap.add_argument("--dry-run", action="store_true", help="print what would be opened, change nothing")
    args = ap.parse_args()

    try:
        issues = existing_issues()
    except (OSError, ValueError, subprocess.CalledProcessError) as e:
        if not args.dry_run:
            raise  # never open issues without knowing which ones exist: that is the bug this fixes
        print(f"gh is unavailable ({e}); listing every file as new", file=sys.stderr)
        issues = []
    todo = plan(args.dir, issues)
    if not todo:
        print(f"nothing to file: {len(escalations(args.dir))} escalation(s), all already have an issue")
        return 0
    failed = 0
    for item in todo:
        if args.dry_run:
            print(f"would open: {item['title']}")
            continue
        try:
            create_issue(item["title"], item["body"], args.assignee)
        except subprocess.CalledProcessError as e:
            # One request that cannot be filed must not hold up the others; the red job is the signal.
            print(f"FAILED to open an issue for {item['name']}: {e}", file=sys.stderr)
            failed += 1
            continue
        print(f"opened: {item['title']}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
