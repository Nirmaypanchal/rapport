#!/usr/bin/env python3
"""Post the files in sprint/reddit/outbox/ to r/rapport and move them to sent/ or failed/.

Runs in GitHub Actions with the secrets REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME, REDDIT_PASSWORD
(a Reddit "script" app on the bot account). Hard rules: only r/rapport, only self posts and comments, one file at a time.
"""
from __future__ import annotations

import argparse, base64, json, os, re, sys, time, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTBOX = ROOT / "sprint/reddit/outbox"  # sent/ and failed/ sit beside whichever outbox is used
ALLOWED_SUBREDDITS = {"rapport"}
UA = "rapport-sprint/1.0 (github.com/Nirmaypanchal/rapport)"
COMMENT = re.compile(r"(?:^|\s)#(?=\s|$)")  # a frontmatter comment: a lone '#', space on both sides


def value(raw: str) -> str:
    """One frontmatter value, with an inline `# comment` stripped.

    The documented format (sprint/agents/community.md) shows comments beside the keys, so they have to go,
    but only a `#` standing alone with whitespace on both sides is one: a hash inside the text ("Rapport #1")
    is part of the value. The old rule — cut at the first `#`, unless the value happened to start with the
    letter `t` — truncated any value beginning with a lowercase `t` word ("the week in Rapport") to that one
    word. The `t` was guarding `parent: t1_…` fullnames, which this rule handles without a special case.
    """
    v = raw.strip()
    m = COMMENT.search(v)
    return (v[: m.start()] if m else v).strip()


def subreddit(raw: str) -> str:
    """`rapport`, `r/rapport` or `/r/rapport` → `rapport`.

    `.lstrip("r/")` strips leading `r` and `/` *characters*, not the prefix, so it turned the literal word
    "rapport" into "apport" and every post failed this script's own allow-list (issue #16).
    """
    return raw.strip().lower().removeprefix("/").removeprefix("r/").strip("/").strip()


def parse(path: Path) -> tuple[dict, str]:
    text = path.read_text()
    if not text.startswith("---\n"):
        raise ValueError("missing frontmatter")
    head, _, body = text[4:].partition("\n---\n")
    meta = {}
    for line in head.splitlines():
        k, sep, v = line.partition(":")
        if sep:
            meta[k.strip()] = value(v)
    return meta, body.strip()


def prepare(path: Path) -> tuple[str, str, dict]:
    """What this file would post: (kind, API path, form). Raises for anything that must not be posted."""
    meta, body = parse(path)
    sub = subreddit(meta.get("subreddit", ""))
    if sub not in ALLOWED_SUBREDDITS:
        raise RuntimeError(f"subreddit {sub!r} is not allowed; only {sorted(ALLOWED_SUBREDDITS)}")
    if not body:
        raise RuntimeError("empty body")
    kind = meta.get("kind", "comment")
    if kind == "post":
        if not meta.get("title"):
            raise RuntimeError("post needs a title")
        form = {"sr": sub, "kind": "self", "title": meta["title"][:300], "text": body, "sendreplies": "true"}
        return kind, "/api/submit", form
    if kind == "comment":
        parent = meta.get("parent", "")
        if not (parent.startswith("t1_") or parent.startswith("t3_")):
            raise RuntimeError("comment needs parent t1_… or t3_…")
        return kind, "/api/comment", {"thing_id": parent, "text": body}
    raise RuntimeError(f"unknown kind {kind!r}")


def token() -> str:
    cid, secret, user, pw = (os.environ.get(k) for k in ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USERNAME", "REDDIT_PASSWORD"))
    if not all((cid, secret, user, pw)):
        raise RuntimeError("Reddit credentials are not configured (REDDIT_* secrets)")
    req = urllib.request.Request(
        "https://www.reddit.com/api/v1/access_token",
        data=urllib.parse.urlencode({"grant_type": "password", "username": user, "password": pw}).encode(),
        headers={"Authorization": "Basic " + base64.b64encode(f"{cid}:{secret}".encode()).decode(), "User-Agent": UA},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    if "access_token" not in data:
        raise RuntimeError(f"token error: {data}")
    return data["access_token"]


def call(tok: str, path: str, form: dict) -> dict:
    req = urllib.request.Request(
        "https://oauth.reddit.com" + path, data=urllib.parse.urlencode({**form, "api_type": "json"}).encode(),
        headers={"Authorization": f"bearer {tok}", "User-Agent": UA},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    errors = data.get("json", {}).get("errors") or []
    if errors:
        raise RuntimeError(f"reddit error: {errors}")
    return data.get("json", {}).get("data", {})


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Post sprint/reddit/outbox/*.md to r/rapport.")
    ap.add_argument("--outbox", default=str(OUTBOX), help="folder of files to post (sent/ and failed/ sit beside it)")
    ap.add_argument("--dry-run", action="store_true", help="check every file, post nothing, move nothing")
    args = ap.parse_args(argv)
    outbox = Path(args.outbox)
    sent, failed = (outbox.parent / d for d in ("sent", "failed"))
    files = sorted(p for p in outbox.glob("*.md") if p.name != "README.md")
    if not files:
        print("outbox empty")
        return 0
    if not args.dry_run:
        for d in (sent, failed):
            d.mkdir(parents=True, exist_ok=True)
    tok = None
    failures = 0
    for f in files:
        try:
            kind, api, form = prepare(f)
            if args.dry_run:
                print(f"would post {f.name}: {kind}")
                continue
            tok = tok or token()
            data = call(tok, api, form)
            if kind == "post":
                url = data.get("url") or ""
            else:
                things = data.get("things") or []
                url = "https://www.reddit.com" + things[0]["data"]["permalink"] if things and things[0].get("data", {}).get("permalink") else ""
            dest = sent / f.name
            dest.write_text(f.read_text().replace("---\n", f"---\nurl: {url}\nposted_at: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n", 1))
            f.unlink()
            print(f"posted {f.name} -> {url}")
            time.sleep(2)
        except Exception as e:  # keep going; one bad file must not block the rest
            failures += 1
            if args.dry_run:
                print(f"would fail {f.name}: {e}", file=sys.stderr)
                continue
            dest = failed / f.name
            dest.write_text(f.read_text().replace("---\n", f"---\nerror: {str(e)[:300]}\n", 1))
            f.unlink()
            print(f"failed {f.name}: {e}", file=sys.stderr)
    return 1 if failures and failures == len(files) else 0


if __name__ == "__main__":
    sys.exit(main())
