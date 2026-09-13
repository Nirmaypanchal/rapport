"""Rapport as an MCP server: an assistant can search your recordings, read a transcript, read a summary and
see who is in your library — all from this Mac, over stdio, without the app running and without a network.

    python -m rapport.mcp                     # the default library
    python -m rapport.mcp --library ~/Rapport
    rapport-core --mcp                        # the same thing from the installed app

The transport is the Model Context Protocol's stdio transport: JSON-RPC 2.0, one message per line, requests in
on stdin and responses out on stdout. Nothing else may ever be written to stdout — logs and errors go to stderr.
It is implemented here in the standard library rather than with an SDK: the part of the protocol a read-only
tool server needs is `initialize`, `tools/list` and `tools/call`, and the backend already carries 1.3 GB of
machine learning it cannot avoid (see sprint/decisions.md).

Slice one is **read-only**. Nothing here writes to the library, and no tool touches audio files, so the worst a
confused client can do is read. Writing notes back is a later slice.

Retrieval is not reinvented: `search` is the same FTS index, keyword extraction and excerpt assembly that the
Ask feature uses (`rapport/ask.py`), returned in an MCP envelope instead of an HTTP one.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import IO, Any

from . import ask
from .db import Database

# Versions of the protocol this server speaks, newest first. A client asking for one of these gets it back;
# a client asking for anything else is answered with the newest, which the spec allows it to refuse.
PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
SERVER_NAME = "rapport"

MAX_RESULTS = 25        # excerpts one `search` call may return
DEFAULT_RESULTS = 8
MAX_TURNS = 400         # turns one `get_transcript` call may return before it asks for a narrower window
MAX_RECORDINGS = 100
DEFAULT_RECORDINGS = 20
MAX_PEOPLE = 200


def server_version() -> str:
    try:
        from importlib.metadata import version

        return version("rapport")
    except Exception:
        return "0.0.0"


class ToolError(Exception):
    """Something the caller asked for that cannot be given: a bad argument, an id that is not there.

    Reported as a failed tool result rather than a protocol error, so the model reads it and can correct itself.
    """


# ---- tools ---------------------------------------------------------------------------------------------

READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}

TOOLS: list[dict] = [
    {
        "name": "search",
        "description": (
            "Search the user's own recordings and find what matches. Takes a question or a few words and "
            "returns two kinds of result, each readable on its own: a `moment` is what was said — the matching "
            "turn with the turn before and after it, carrying a timestamp `get_transcript` can widen — and a "
            "`summary` is a block of the summary Rapport wrote for a recording, which often states an outcome "
            "the transcript only arrives at slowly; `get_summary` reads the rest of one. Both carry the "
            "recording id. Start here: it is the only tool that finds a recording id from words."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "A question or some words to look for."},
                "limit": {
                    "type": "integer", "minimum": 1, "maximum": MAX_RESULTS, "default": DEFAULT_RESULTS,
                    "description": "How many excerpts to return.",
                },
                "match": {
                    "type": "string", "enum": ["any", "all"], "default": "any",
                    "description": "'any' ranks whatever matches most of the words (right for a question); "
                                   "'all' requires every word (right for a name or an exact phrase).",
                },
            },
            "required": ["query"],
        },
        "annotations": {"title": "Search recordings", **READ_ONLY},
    },
    {
        "name": "list_recordings",
        "description": (
            "List recordings, newest first: id, title, when it was recorded, how long it is, where it came from, "
            "whether it has been transcribed and whether it has a summary. Use it to browse or to find a "
            "recording by title or date; use `search` to find one by what was said in it."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "minimum": 1, "maximum": MAX_RECORDINGS, "default": DEFAULT_RECORDINGS},
                "title_contains": {"type": "string", "description": "Only recordings whose title or file name contains this."},
                "since": {"type": "string", "description": "Only recordings on or after this date, as YYYY-MM-DD."},
                "until": {"type": "string", "description": "Only recordings before or on this date, as YYYY-MM-DD."},
            },
        },
        "annotations": {"title": "List recordings", **READ_ONLY},
    },
    {
        "name": "get_recording",
        "description": (
            "Everything known about one recording except the words: title, date, length, source, processing "
            "state, who speaks in it and for how long, and whether a summary exists."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"recording_id": {"type": "integer", "description": "The id from `search` or `list_recordings`."}},
            "required": ["recording_id"],
        },
        "annotations": {"title": "Get a recording", **READ_ONLY},
    },
    {
        "name": "get_transcript",
        "description": (
            "The transcript of one recording as speaker-labelled turns with timestamps. A long recording is cut "
            "off; ask again with `from_sec` and `to_sec` for the part you want."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "recording_id": {"type": "integer"},
                "from_sec": {"type": "number", "minimum": 0, "description": "Only turns ending at or after this second."},
                "to_sec": {"type": "number", "minimum": 0, "description": "Only turns starting at or before this second."},
            },
            "required": ["recording_id"],
        },
        "annotations": {"title": "Get a transcript", **READ_ONLY},
    },
    {
        "name": "get_summary",
        "description": (
            "The summary Rapport wrote for one recording, as Markdown, with the template it used and when. "
            "A recording with no summary is not an error: `reason` says why there is none."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"recording_id": {"type": "integer"}},
            "required": ["recording_id"],
        },
        "annotations": {"title": "Get a summary", **READ_ONLY},
    },
    {
        "name": "list_people",
        "description": (
            "The people Rapport recognizes across recordings, most talkative first: name, how many recordings "
            "they appear in, total speaking time and when they were last heard. People the user has not named "
            "yet are marked `named: false` and carry an automatic label like 'Speaker 3'."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "minimum": 1, "maximum": MAX_PEOPLE, "default": 50},
                "named_only": {"type": "boolean", "default": False, "description": "Leave out people the user has not named."},
            },
        },
        "annotations": {"title": "List people", **READ_ONLY},
    },
]


def _arg(args: dict, name: str, kind: type, default=None, required: bool = False):
    if name not in args or args[name] is None:
        if required:
            raise ToolError(f"{name} is required")
        return default
    v = args[name]
    if kind is float and isinstance(v, int) and not isinstance(v, bool):
        return float(v)
    if kind is int and isinstance(v, bool):
        raise ToolError(f"{name} must be a number")
    if not isinstance(v, kind):
        raise ToolError(f"{name} must be {'a number' if kind in (int, float) else kind.__name__}")
    return v


def _clamp(n: int, low: int, high: int) -> int:
    return max(low, min(high, n))


def _recording(db, rid: int) -> dict:
    rec = db.get_recording(rid)
    if not rec:
        raise ToolError(f"no recording with id {rid}; use search or list_recordings to find one")
    return rec


def _title(rec: dict) -> str:
    return rec.get("title") or rec.get("original_name") or f"Recording {rec['id']}"


def _speaker_names(db, rid: int) -> dict[str, str]:
    """Diarization label ('SPEAKER_01') → the name to show, when there is one."""
    out = {}
    for s in db.get_speakers(rid):
        name = s.get("person_name") or s.get("display_name")
        if s.get("label") and name:
            out[s["label"]] = name
    return out


def tool_search(db, args: dict) -> dict:
    query = _arg(args, "query", str, required=True).strip()
    if not query:
        raise ToolError("query is empty")
    limit = _clamp(_arg(args, "limit", int, DEFAULT_RESULTS), 1, MAX_RESULTS)
    match = _arg(args, "match", str, "any")
    if match not in ("any", "all"):
        raise ToolError("match must be 'any' or 'all'")

    terms = ask.keywords(query)
    found = ask.retrieve(db, terms, match=match, max_passages=limit)
    results = []
    for p in found:
        if p.kind == "summary":
            # A summary has no timestamp: `get_summary` is where to read the rest of it, not `get_transcript`.
            results.append({
                "kind": "summary",
                "recording_id": p.recording_id,
                "title": p.title,
                "recorded_at": p.recorded_at,
                "heading": p.heading,
                "excerpt": p.text,
            })
        else:
            results.append({
                "kind": "moment",
                "recording_id": p.recording_id,
                "title": p.title,
                "recorded_at": p.recorded_at,
                "at": ask.clock(p.start),
                "start_sec": round(p.start, 1),
                "speaker": p.speaker,
                "excerpt": p.text,
            })
    return {
        "query": query,
        "searched_for": terms,
        "count": len(results),
        "results": results,
        "note": None if results else "Nothing in the library matches those words.",
    }


def tool_list_recordings(db, args: dict) -> dict:
    limit = _clamp(_arg(args, "limit", int, DEFAULT_RECORDINGS), 1, MAX_RECORDINGS)
    needle = (_arg(args, "title_contains", str, "") or "").lower()
    since = _arg(args, "since", str, "") or ""
    until = _arg(args, "until", str, "") or ""

    rows = []
    for r in db.list_recordings():
        when = r.get("recorded_at") or r.get("imported_at") or ""
        if needle and needle not in (_title(r).lower() + " " + (r.get("original_name") or "").lower()):
            continue
        if since and when[:10] < since:
            continue
        if until and when[:10] > until:
            continue
        rows.append({
            "recording_id": r["id"],
            "title": _title(r),
            "recorded_at": r.get("recorded_at"),
            "duration_sec": round(r["duration_sec"], 1) if r.get("duration_sec") else None,
            "source": r.get("source") or "dji",
            "status": r.get("status"),
            "has_summary": bool(r.get("summary")),
        })
    return {"count": len(rows[:limit]), "total_matching": len(rows), "recordings": rows[:limit]}


def tool_get_recording(db, args: dict) -> dict:
    rec = _recording(db, _arg(args, "recording_id", int, required=True))
    speakers = [
        {
            "speaker": s.get("person_name") or s.get("display_name") or s.get("label"),
            "named": bool(s.get("person_name") or s.get("display_name")),
            "speaking_sec": round(s["speaking_sec"], 1) if s.get("speaking_sec") else 0.0,
        }
        for s in db.get_speakers(rec["id"])
    ]
    return {
        "recording_id": rec["id"],
        "title": _title(rec),
        "original_name": rec.get("original_name"),
        "recorded_at": rec.get("recorded_at"),
        "imported_at": rec.get("imported_at"),
        "duration_sec": round(rec["duration_sec"], 1) if rec.get("duration_sec") else None,
        "source": rec.get("source") or "dji",
        "status": rec.get("status"),
        "error": rec.get("error"),
        "turns": db.count_segments(rec["id"]),
        "speakers": speakers,
        "has_summary": bool(rec.get("summary")),
        "summary_template": rec.get("summary_template"),
    }


def tool_get_transcript(db, args: dict) -> dict:
    rec = _recording(db, _arg(args, "recording_id", int, required=True))
    lo = _arg(args, "from_sec", float)
    hi = _arg(args, "to_sec", float)
    if lo is not None and hi is not None and hi < lo:
        raise ToolError("to_sec is before from_sec")

    names = _speaker_names(db, rec["id"])
    segments = db.get_segments(rec["id"])
    kept = [
        s for s in segments
        if (lo is None or (s.get("end") or 0.0) >= lo) and (hi is None or (s.get("start") or 0.0) <= hi)
    ]
    shown = kept[:MAX_TURNS]
    lines = [
        f"[{ask.clock(s.get('start') or 0.0)}] {names.get(s.get('speaker_label')) or s.get('speaker_label') or 'Unknown'}: {s['text']}"
        for s in shown
    ]
    out = {
        "recording_id": rec["id"],
        "title": _title(rec),
        "recorded_at": rec.get("recorded_at"),
        "turns": len(shown),
        "turns_in_window": len(kept),
        "turns_in_recording": len(segments),
        "truncated": len(kept) > len(shown),
        "transcript": "\n".join(lines),
        "reason": None,
    }
    if not segments:
        out["reason"] = "not_transcribed" if rec.get("status") != "done" else "no_transcript"
        out["note"] = f"This recording has no transcript yet (status: {rec.get('status')})."
    elif not kept:
        out["reason"] = "empty_window"
        out["note"] = "No turns in that window; the recording is "\
                      f"{ask.clock(segments[-1].get('end') or 0.0)} long."
    elif out["truncated"]:
        last = shown[-1].get("end") or 0.0
        out["note"] = (f"Cut off after {MAX_TURNS} turns, at {ask.clock(last)}. "
                       f"Ask again with from_sec={round(last, 1)} for what follows.")
    return out


def tool_get_summary(db, args: dict) -> dict:
    rec = _recording(db, _arg(args, "recording_id", int, required=True))
    out = {
        "recording_id": rec["id"],
        "title": _title(rec),
        "recorded_at": rec.get("recorded_at"),
        "summary": rec.get("summary") or None,
        "template": rec.get("summary_template"),
        "model": rec.get("summary_model"),
        "written_at": rec.get("summary_at"),
        "reason": None,
    }
    if not out["summary"]:
        status = rec.get("summary_status")
        out["reason"] = {"queued": "summary_queued", "running": "summary_running", "error": "summary_failed"}.get(
            status, "no_summary"
        )
        out["error"] = rec.get("summary_error")
        out["note"] = ("No summary for this recording. Its transcript is there to read with get_transcript."
                       if rec.get("status") == "done" else
                       f"No summary: the recording has not been transcribed yet (status: {rec.get('status')}).")
    return out


def tool_list_people(db, args: dict) -> dict:
    limit = _clamp(_arg(args, "limit", int, 50), 1, MAX_PEOPLE)
    named_only = _arg(args, "named_only", bool, False)
    people = []
    for p in db.list_people():
        named = not p.get("auto")
        if named_only and not named:
            continue
        people.append({
            "person_id": p["id"],
            "name": p.get("name"),
            "named": named,
            "recordings": p.get("appearances") or 0,
            "speaking_sec": round(p.get("speaking_sec") or 0.0, 1),
            "last_heard": p.get("last_heard"),
        })
    return {"count": len(people[:limit]), "total": len(people), "people": people[:limit]}


HANDLERS = {
    "search": tool_search,
    "list_recordings": tool_list_recordings,
    "get_recording": tool_get_recording,
    "get_transcript": tool_get_transcript,
    "get_summary": tool_get_summary,
    "list_people": tool_list_people,
}


def call_tool(db, name: str, arguments: dict | None) -> dict:
    """Run one tool and return the MCP result. A bad request comes back as `isError`, not an exception."""
    handler = HANDLERS.get(name)
    if handler is None:
        return _error_result(f"unknown tool: {name}")
    if arguments is not None and not isinstance(arguments, dict):
        return _error_result("arguments must be an object")
    try:
        payload = handler(db, arguments or {})
    except ToolError as e:
        return _error_result(str(e))
    except Exception as e:  # a broken library must not take the whole server down mid-conversation
        return _error_result(f"{type(e).__name__}: {e}")
    return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, indent=2)}]}


def _error_result(message: str) -> dict:
    return {"content": [{"type": "text", "text": message}], "isError": True}


# ---- JSON-RPC ------------------------------------------------------------------------------------------

PARSE_ERROR, INVALID_REQUEST, METHOD_NOT_FOUND, INVALID_PARAMS, INTERNAL_ERROR = -32700, -32600, -32601, -32602, -32603


def _result(mid, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def _error(mid, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def handle(db, msg: Any) -> dict | None:
    """One JSON-RPC message in, one response out — or None for a notification, which gets no reply."""
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or not isinstance(msg.get("method"), str):
        return _error(msg.get("id") if isinstance(msg, dict) else None, INVALID_REQUEST, "not a JSON-RPC 2.0 request")
    method, mid = msg["method"], msg.get("id")
    params = msg.get("params") or {}
    if not isinstance(params, dict):
        return _error(mid, INVALID_PARAMS, "params must be an object")
    notification = "id" not in msg

    if method == "initialize":
        asked = params.get("protocolVersion")
        version = asked if asked in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0]
        return _result(mid, {
            "protocolVersion": version,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "title": "Rapport", "version": server_version()},
            "instructions": (
                "These tools read one person's own audio library on this Mac: recordings, transcripts, summaries "
                "and the people in them. Nothing here can change or delete anything. Use `search` to find the "
                "moments that answer a question, then `get_transcript` for the surrounding words. Say what the "
                "recordings actually say, cite the recording and the timestamp, and never fill a gap with a guess."
            ),
        })
    if method in ("notifications/initialized", "notifications/cancelled"):
        return None
    if method == "ping":
        return None if notification else _result(mid, {})
    if method == "tools/list":
        return _result(mid, {"tools": TOOLS})
    if method == "tools/call":
        name = params.get("name")
        if not isinstance(name, str):
            return _error(mid, INVALID_PARAMS, "name is required")
        return _result(mid, call_tool(db, name, params.get("arguments")))
    if notification:
        return None
    return _error(mid, METHOD_NOT_FOUND, f"method not found: {method}")


def serve(db, stdin: IO[str] | None = None, stdout: IO[str] | None = None) -> int:
    """Read newline-delimited JSON-RPC from stdin until it closes, answering on stdout."""
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as e:
            _write(stdout, _error(None, PARSE_ERROR, f"invalid JSON: {e}"))
            continue
        # A batch was legal in older versions of the protocol and is cheap to keep working.
        for one in msg if isinstance(msg, list) else [msg]:
            try:
                reply = handle(db, one)
            except Exception as e:  # never die on one bad message
                reply = _error(one.get("id") if isinstance(one, dict) else None, INTERNAL_ERROR, str(e))
            if reply is not None:
                _write(stdout, reply)
    return 0


def _write(stdout: IO[str], msg: dict) -> None:
    stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    stdout.flush()


def serve_library(root: Path | None = None) -> int:
    """Open a library folder read-only-ish (no worker, no import, no audio) and serve MCP on stdio."""
    from .config import DEFAULT_LIBRARY

    root = Path(root).expanduser() if root else DEFAULT_LIBRARY
    db_path = root / "library.sqlite"
    if not db_path.exists():
        print(f"No Rapport library at {root} (expected {db_path}). "
              f"Open Rapport once, or pass --library.", file=sys.stderr)
        return 2
    print(f"rapport mcp: serving {root}", file=sys.stderr)
    return serve(Database(db_path))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m rapport.mcp",
        description="Serve the Rapport library to MCP clients (Claude, Cursor, …) over stdio. Read-only.",
    )
    ap.add_argument("--library", default=None, help="library folder (default: ~/Rapport, or $RAPPORT_LIBRARY)")
    args = ap.parse_args(argv)
    return serve_library(Path(args.library) if args.library else None)


if __name__ == "__main__":
    sys.exit(main())
