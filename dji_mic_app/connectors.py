"""Pull transcripts from other note-takers into the library.

Each connector returns normalized items:

    {"uid": str, "title": str, "recorded_at": iso | None, "duration_sec": float | None,
     "segments": [{"speaker": str, "text": str, "start": float | None, "end": float | None}],
     "summary": markdown | None}

Granola: https://public-api.granola.ai/v1 (Bearer grn_…). Omi: https://api.omi.me/v1/dev (Bearer omi_dev_…).
Notion: pages with `meeting_notes` blocks (Notion-Version 2026-03-11). All read-only.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone


def _get(url: str, headers: dict, timeout: int = 60) -> dict:
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="ignore")[:300]
        raise RuntimeError(f"HTTP {e.code} from {urllib.parse.urlparse(url).netloc}: {body or e.reason}") from e


def _post(url: str, headers: dict, body: dict, timeout: int = 60) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={**headers, "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body_txt = e.read().decode(errors="ignore")[:300]
        raise RuntimeError(f"HTTP {e.code} from {urllib.parse.urlparse(url).netloc}: {body_txt or e.reason}") from e


def _iso(v) -> str | None:
    if not v:
        return None
    try:
        if isinstance(v, (int, float)):
            return datetime.fromtimestamp(v).isoformat(timespec="seconds")
        s = str(v).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo:
            dt = dt.astimezone().replace(tzinfo=None)
        return dt.isoformat(timespec="seconds")
    except Exception:
        return None


# ---------------------------------------------------------------- Granola
GRANOLA = "https://public-api.granola.ai/v1"


def granola_items(api_key: str, known: set[str], limit: int = 200) -> list[dict]:
    h = {"Authorization": f"Bearer {api_key.strip()}", "Accept": "application/json"}
    items: list[dict] = []
    cursor = None
    seen = 0
    while seen < limit:
        q = f"?cursor={urllib.parse.quote(cursor)}" if cursor else ""
        page = _get(f"{GRANOLA}/notes{q}", h)
        notes = page.get("notes") or page.get("data") or []
        for n in notes:
            seen += 1
            nid = str(n.get("id"))
            if nid in known:
                continue
            try:
                full = _get(f"{GRANOLA}/notes/{nid}?include=transcript", h)
            except RuntimeError as e:
                if "413" in str(e):
                    full = _get(f"{GRANOLA}/notes/{nid}", h)
                    full["transcript"] = (_get(f"{GRANOLA}/notes/{nid}/transcript", h) or {}).get("transcript", [])
                else:
                    raise
            note = full.get("note") or full
            segs = []
            for t in note.get("transcript") or []:
                sp = t.get("speaker") or {}
                label = sp.get("diarization_label") or ("Me" if sp.get("source") == "microphone" else "Others")
                text = (t.get("text") or "").strip()
                if text:
                    segs.append({"speaker": label, "text": text, "start": t.get("start_timestamp") or t.get("start"), "end": t.get("end_timestamp") or t.get("end")})
            summary = note.get("summary")
            if isinstance(summary, dict):
                summary = summary.get("markdown") or summary.get("text") or json.dumps(summary)
            items.append({
                "uid": nid, "title": note.get("title") or "Granola note",
                "recorded_at": _iso(note.get("created_at") or note.get("createdAt") or note.get("start_time") or note.get("meeting_start")),
                "duration_sec": None, "segments": segs, "summary": summary,
            })
        if not page.get("hasMore") or not page.get("cursor"):
            break
        cursor = page["cursor"]
    return items


# ---------------------------------------------------------------- Omi
OMI = "https://api.omi.me/v1/dev"


def omi_items(api_key: str, known: set[str], limit: int = 200) -> list[dict]:
    h = {"Authorization": f"Bearer {api_key.strip()}", "Accept": "application/json"}
    items: list[dict] = []
    offset = 0
    while offset < limit:
        page = _get(f"{OMI}/user/conversations?limit=50&offset={offset}&include_transcript=true", h)
        convs = page.get("conversations") if isinstance(page, dict) else page
        convs = convs or []
        for c in convs:
            cid = str(c.get("id"))
            if cid in known:
                continue
            st = c.get("structured") or {}
            segs = []
            for t in c.get("transcript_segments") or []:
                text = (t.get("text") or "").strip()
                if not text:
                    continue
                speaker = "Me" if t.get("is_user") else (t.get("speaker_name") or f"Speaker {int(t.get('speaker_id', 0)) + 1}")
                segs.append({"speaker": speaker, "text": text, "start": t.get("start"), "end": t.get("end")})
            summary_parts = []
            if st.get("overview"):
                summary_parts.append("## Summary\n" + st["overview"])
            if st.get("action_items"):
                summary_parts.append("## Action items\n" + "\n".join(f"- {'[x] ' if a.get('completed') else ''}{a.get('description', '')}" for a in st["action_items"]))
            started, finished = c.get("started_at"), c.get("finished_at")
            dur = None
            try:
                if started and finished:
                    dur = (datetime.fromisoformat(str(finished).replace("Z", "+00:00")) - datetime.fromisoformat(str(started).replace("Z", "+00:00"))).total_seconds()
            except Exception:
                pass
            items.append({
                "uid": cid, "title": st.get("title") or "Omi conversation",
                "recorded_at": _iso(started or c.get("created_at")), "duration_sec": dur,
                "segments": segs, "summary": "\n\n".join(summary_parts) or None,
            })
        if len(convs) < 50:
            break
        offset += 50
    return items


# ---------------------------------------------------------------- Notion
NOTION = "https://api.notion.com/v1"


def _notion_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token.strip()}", "Notion-Version": "2026-03-11", "Accept": "application/json"}


def _rich_text(rt: list) -> str:
    return "".join((x.get("plain_text") or (x.get("text") or {}).get("content") or "") for x in rt or [])


def notion_items(token: str, database_id: str | None, known: set[str], limit: int = 100) -> list[dict]:
    h = _notion_headers(token)
    pages: list[dict] = []
    if database_id:
        cursor = None
        while len(pages) < limit:
            body = {"page_size": 50}
            if cursor:
                body["start_cursor"] = cursor
            res = _post(f"{NOTION}/databases/{database_id.strip()}/query", h, body)
            pages += res.get("results") or []
            if not res.get("has_more"):
                break
            cursor = res.get("next_cursor")
    else:
        cursor = None
        while len(pages) < limit:
            body = {"filter": {"property": "object", "value": "page"}, "page_size": 50, "sort": {"direction": "descending", "timestamp": "last_edited_time"}}
            if cursor:
                body["start_cursor"] = cursor
            res = _post(f"{NOTION}/search", h, body)
            pages += res.get("results") or []
            if not res.get("has_more"):
                break
            cursor = res.get("next_cursor")

    items: list[dict] = []
    for p in pages:
        pid = str(p.get("id"))
        if pid in known:
            continue
        title = "Notion meeting"
        for prop in (p.get("properties") or {}).values():
            if prop.get("type") == "title":
                title = _rich_text(prop.get("title")) or title
        # Walk the page's blocks for meeting_notes (formerly transcription).
        texts: list[str] = []
        cursor = None
        while True:
            q = f"?page_size=100" + (f"&start_cursor={cursor}" if cursor else "")
            res = _get(f"{NOTION}/blocks/{pid}/children{q}", h)
            for b in res.get("results") or []:
                t = b.get("type")
                if t in ("meeting_notes", "transcription"):
                    texts.append(_rich_text((b.get(t) or {}).get("rich_text")))
            if not res.get("has_more"):
                break
            cursor = res.get("next_cursor")
        if not any(texts):
            continue
        segs = [{"speaker": "Transcript", "text": para.strip(), "start": None, "end": None} for para in "\n".join(texts).split("\n") if para.strip()]
        items.append({"uid": pid, "title": title, "recorded_at": _iso(p.get("created_time")), "duration_sec": None, "segments": segs, "summary": None})
    return items
