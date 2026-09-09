#!/usr/bin/env python3
"""Post the files in sprint/reddit/outbox/ to r/rapport and move them to sent/ or failed/.

Runs in GitHub Actions with the secrets REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME, REDDIT_PASSWORD
(a Reddit "script" app on the bot account). Hard rules: only r/rapport, only self posts and comments, one file at a time.
"""
from __future__ import annotations

import base64, json, os, sys, time, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTBOX, SENT, FAILED = (ROOT / "sprint/reddit" / d for d in ("outbox", "sent", "failed"))
ALLOWED_SUBREDDITS = {"rapport"}
UA = "rapport-sprint/1.0 (github.com/Nirmaypanchal/rapport)"


def parse(path: Path) -> tuple[dict, str]:
    text = path.read_text()
    if not text.startswith("---\n"):
        raise ValueError("missing frontmatter")
    head, _, body = text[4:].partition("\n---\n")
    meta = {}
    for line in head.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.split("#")[0].strip() if not v.strip().startswith("t") else v.strip().split()[0]
    return meta, body.strip()


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


def main() -> int:
    files = sorted(p for p in OUTBOX.glob("*.md") if p.name != "README.md")
    if not files:
        print("outbox empty")
        return 0
    tok = None
    failures = 0
    for f in files:
        try:
            meta, body = parse(f)
            sub = meta.get("subreddit", "").lstrip("r/").lower()
            if sub not in ALLOWED_SUBREDDITS:
                raise RuntimeError(f"subreddit {sub!r} is not allowed; only {sorted(ALLOWED_SUBREDDITS)}")
            if not body:
                raise RuntimeError("empty body")
            tok = tok or token()
            kind = meta.get("kind", "comment")
            if kind == "post":
                if not meta.get("title"):
                    raise RuntimeError("post needs a title")
                data = call(tok, "/api/submit", {"sr": sub, "kind": "self", "title": meta["title"][:300], "text": body, "sendreplies": "true"})
                url = data.get("url") or ""
            elif kind == "comment":
                parent = meta.get("parent", "")
                if not (parent.startswith("t1_") or parent.startswith("t3_")):
                    raise RuntimeError("comment needs parent t1_… or t3_…")
                data = call(tok, "/api/comment", {"thing_id": parent, "text": body})
                things = data.get("things") or []
                url = "https://www.reddit.com" + things[0]["data"]["permalink"] if things and things[0].get("data", {}).get("permalink") else ""
            else:
                raise RuntimeError(f"unknown kind {kind!r}")
            dest = SENT / f.name
            dest.write_text(f.read_text().replace("---\n", f"---\nurl: {url}\nposted_at: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n", 1))
            f.unlink()
            print(f"posted {f.name} -> {url}")
            time.sleep(2)
        except Exception as e:  # keep going; one bad file must not block the rest
            failures += 1
            dest = FAILED / f.name
            dest.write_text(f.read_text().replace("---\n", f"---\nerror: {str(e)[:300]}\n", 1))
            f.unlink()
            print(f"failed {f.name}: {e}", file=sys.stderr)
    return 1 if failures and failures == len(files) else 0


if __name__ == "__main__":
    sys.exit(main())
