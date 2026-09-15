#!/usr/bin/env python3
"""Open one GitHub issue when the nightly on-device QA run stops reporting.

    scripts/nightly_watchdog.py                       # decide and act
    scripts/nightly_watchdog.py --dry-run             # print the decision, change nothing
    scripts/nightly_watchdog.py --dir DIR --hours 48  # read another folder, another threshold (tests)

Run daily by .github/workflows/nightly-watchdog.yml. Needs `gh` on PATH and GH_TOKEN in the environment.

Why this exists: the nightly runs on the owner's Mac and is the only thing in the loop that meets the real
pipeline, a real local model and the built app. When it fails it writes a log and opens an issue — but when
it never *starts* it does neither, and silence is indistinguishable from "nothing to report". In week 37 it
went quiet after 2026-09-10; an agent noticed the absence on day 2 and escalated on day 3 (#12), and four
features shipped in between without ever meeting a Mac. A missing log is a signal, so something has to watch
for the absence rather than rely on an agent remembering.

Decisions worth knowing:

- **The date in the file name is the log's age**, not its mtime: a fresh clone in CI stamps every file with
  the checkout time, so mtime says "seconds old" for a log written a week ago. That date counts as 00:00 UTC,
  so with the default 48 hours a log from today or yesterday is fresh and anything older is not.
- **Dedupe looks at open issues only**, unlike `needs_human_issues.py`, which also counts closed ones. There
  the escalation file lingers until a human acts; here the condition is live, so a silence that comes back
  after the owner fixed it is news again and deserves a new issue.
- **A recovery closes the issue.** The run after a nightly log lands closes the open watchdog issue with a
  comment, so the watchdog works the second time as well as the first, without anyone tidying up.
- **No logs at all is not silence.** A fresh checkout of a repository that has never run a nightly has
  nothing to be silent about.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import date, datetime, time, timezone
from pathlib import Path

LABELS = "sprint,bug"
MARKER = "<!-- nightly-watchdog -->"
ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIR = ROOT / "sprint" / "log"
DEFAULT_HOURS = 48
NIGHTLY = re.compile(r"^(\d{4}-\d{2}-\d{2})-nightly\.md$")


def nightly_logs(folder: Path) -> list[tuple[date, str]]:
    """Every nightly log as (date from its name, file name), oldest first. A name that is not a date is
    not a nightly log, and a folder that does not exist holds none."""
    found = []
    for path in sorted(folder.glob("*-nightly.md")) if folder.is_dir() else []:
        m = NIGHTLY.match(path.name)
        if not m:
            continue
        try:
            found.append((date.fromisoformat(m.group(1)), path.name))
        except ValueError:  # 2026-13-45-nightly.md: a name, not a date
            continue
    return sorted(found)


def hours_since(day: date, now: datetime) -> float:
    """How long ago that date began, in hours. The log is dated, not timestamped, so 00:00 UTC is the only
    honest reading of it — and the generous one, since the run itself happened later that day."""
    started = datetime.combine(day, time(0, 0), tzinfo=timezone.utc)
    return (now - started).total_seconds() / 3600


def watchdog_issue(issues: list[dict]) -> dict | None:
    """The open issue this watchdog already opened, if there is one."""
    return next((i for i in issues if MARKER in (i.get("body") or "")), None)


def body_of(day: date, name: str, hours: float, threshold: int) -> str:
    nights = int(hours // 24)
    return f"""The newest nightly log is `sprint/log/{name}`, dated {day.isoformat()} — {nights} day(s) ago. \
Nothing has reported since, and this watchdog opens an issue when the newest log is more than {threshold} \
hours old.

A nightly that never starts writes no log and opens no failure issue, so its silence looks exactly like \
"nothing to report". It is also the only run in the loop that meets the real pipeline, a real local model \
and the built Mac app, so while it is quiet every change ships untested against any of them.

**What to check on the Mac that runs it** (`sprint/agents/nightly.md`):

1. Is the scheduled task still installed and enabled, and did the Mac stay awake and online through the night?
2. Does the clone at `~/.rapport-sprint/repo` still exist and still pull `main`?
3. If it ran and died, its output is the only place that says why — the run writes its log at the end, so a \
crash mid-run leaves nothing behind.

Close this issue once a nightly log lands; the next watchdog run closes it by itself when one does.

{MARKER}
"""


def decide(folder: Path, issues: list[dict], now: datetime, threshold: int = DEFAULT_HOURS) -> dict:
    """What to do: `open` an issue, `close` the one that is open, or `nothing`, always with a reason."""
    logs = nightly_logs(folder)
    open_issue = watchdog_issue(issues)
    if not logs:
        return {"action": "nothing", "why": f"no nightly logs in {folder}; nothing has ever reported"}
    day, name = logs[-1]
    hours = hours_since(day, now)
    if hours <= threshold:
        if open_issue:
            return {
                "action": "close",
                "number": open_issue["number"],
                "comment": f"The nightly reported again: `sprint/log/{name}`. Closing this automatically.",
                "why": f"{name} is {hours:.0f}h old and #{open_issue['number']} is still open",
            }
        return {"action": "nothing", "why": f"{name} is {hours:.0f}h old, within {threshold}h"}
    if open_issue:
        return {"action": "nothing", "why": f"silent since {name}, already reported in #{open_issue['number']}"}
    return {
        "action": "open",
        "title": f"The nightly QA run has not reported since {day.isoformat()}",
        "body": body_of(day, name, hours, threshold),
        "why": f"{name} is {hours:.0f}h old, more than {threshold}h, and no open issue says so",
    }


def open_issues() -> list[dict]:
    """Every open issue, from the list API — never the search index, which is fuzzy and eventually
    consistent and filed #3 and #6 for the same request on 2026-09-09. No label filter: the escalation
    that reported this silence by hand (#12) is labeled `needs-human`, and carrying the marker is what
    makes an issue count, whoever opened it."""
    out = subprocess.run(
        ["gh", "issue", "list", "--state", "open", "--limit", "200", "--json", "number,title,body"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    return json.loads(out) if out else []


def create_issue(title: str, body: str) -> None:
    """`gh issue create`, with the body through a file so its length and quoting cannot bite."""
    fd, tmp = tempfile.mkstemp(suffix=".md")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(body)
        subprocess.run(["gh", "issue", "create", "--title", title, "--body-file", tmp, "--label", LABELS], check=True)
    finally:
        os.unlink(tmp)


def close_issue(number: int, comment: str) -> None:
    subprocess.run(["gh", "issue", "close", str(number), "--comment", comment], check=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", type=Path, default=DEFAULT_DIR, help="folder holding YYYY-MM-DD-nightly.md logs")
    ap.add_argument("--hours", type=int, default=DEFAULT_HOURS, help="how old the newest log may be")
    ap.add_argument("--dry-run", action="store_true", help="print the decision, change nothing")
    args = ap.parse_args(argv)

    try:
        issues = open_issues()
    except (OSError, ValueError, subprocess.CalledProcessError) as e:
        if not args.dry_run:
            raise  # never open an issue without knowing which ones exist: that is how #3 was filed twice
        print(f"gh is unavailable ({e}); deciding as if no issue were open", file=sys.stderr)
        issues = []
    plan = decide(args.dir, issues, datetime.now(timezone.utc), args.hours)
    print(f"{plan['action']}: {plan['why']}")
    if plan["action"] == "nothing" or args.dry_run:
        return 0
    if plan["action"] == "open":
        create_issue(plan["title"], plan["body"])
        print(f"opened: {plan['title']}")
    else:
        close_issue(plan["number"], plan["comment"])
        print(f"closed: #{plan['number']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
