"""The MCP server: the protocol handshake, the tool list, and every tool against a small fake library."""
import io
import json

import pytest

from rapport import mcp


@pytest.fixture
def library_with_two_recordings(db):
    """Two recordings: one transcribed with two named speakers and a summary, one still queued."""
    alice = db.create_person("Alice", auto=False, color="rose")
    bob = db.create_person("Bob", auto=False, color="sky")
    stranger = db.create_person("Speaker 3", auto=True, color="moss")

    rid = db.insert_recording(
        sha256="a" * 64, original_name="TX01_MIC001_20260908_090000.wav", rel_path="audio/a.wav",
        recorded_at="2026-09-08T09:00:00", duration_sec=95.0, status="done", title="Marathon planning",
        source="dji",
    )
    db.replace_segments(rid, [
        {"speaker": "SPEAKER_00", "start": 0.0, "end": 6.0,
         "text": "Good morning. Today we are planning the marathon in October."},
        {"speaker": "SPEAKER_01", "start": 6.0, "end": 12.0,
         "text": "I will book the flights on Friday and send the itinerary."},
        {"speaker": "SPEAKER_00", "start": 12.0, "end": 18.0,
         "text": "Let us also order the pastel notebooks for the workshop."},
    ])
    db.replace_speakers(rid, [
        {"label": "SPEAKER_00", "person_id": alice, "speaking_sec": 12.0},
        {"label": "SPEAKER_01", "person_id": bob, "speaking_sec": 6.0},
    ])
    db.update_recording(rid, summary="## Decisions\n- Run the marathon in October.",
                        summary_template="meeting", summary_model="ollama:llama3.2",
                        summary_at="2026-09-08T09:05:00", summary_status="done")

    queued = db.insert_recording(
        sha256="b" * 64, original_name="voice-memo.m4a", rel_path="audio/b.m4a",
        recorded_at="2026-09-09T18:30:00", duration_sec=40.0, status="queued", source="voicememos",
    )
    db.replace_speakers(queued, [{"label": "SPEAKER_00", "person_id": stranger, "speaking_sec": 4.0}])
    return {"db": db, "done": rid, "queued": queued, "alice": alice}


def _call(db, name, args=None):
    """One tools/call, with the JSON payload parsed back out."""
    res = mcp.call_tool(db, name, args or {})
    assert not res.get("isError"), res["content"][0]["text"]
    return json.loads(res["content"][0]["text"])


def _failure(db, name, args=None):
    res = mcp.call_tool(db, name, args or {})
    assert res.get("isError"), res
    return res["content"][0]["text"]


# ---- protocol ------------------------------------------------------------------------------------------

def test_initialize_agrees_on_a_protocol_version(db):
    r = mcp.handle(db, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                        "params": {"protocolVersion": "2024-11-05", "capabilities": {}}})
    assert r["id"] == 1
    assert r["result"]["protocolVersion"] == "2024-11-05", "a version we speak must be echoed back"
    assert r["result"]["capabilities"]["tools"] == {"listChanged": False}
    assert r["result"]["serverInfo"]["name"] == "rapport"

    # A version we do not know gets ours, which the client may then refuse.
    r = mcp.handle(db, {"jsonrpc": "2.0", "id": 2, "method": "initialize",
                        "params": {"protocolVersion": "1999-01-01"}})
    assert r["result"]["protocolVersion"] == mcp.PROTOCOL_VERSIONS[0]


def test_notifications_get_no_reply(db):
    assert mcp.handle(db, {"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    assert mcp.handle(db, {"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 1}}) is None
    assert mcp.handle(db, {"jsonrpc": "2.0", "method": "something/unknown"}) is None, "an unknown notification is ignored"


def test_unknown_method_and_malformed_request(db):
    r = mcp.handle(db, {"jsonrpc": "2.0", "id": 3, "method": "resources/list"})
    assert r["error"]["code"] == mcp.METHOD_NOT_FOUND

    r = mcp.handle(db, {"id": 4, "method": "tools/list"})
    assert r["error"]["code"] == mcp.INVALID_REQUEST

    r = mcp.handle(db, {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {}})
    assert r["error"]["code"] == mcp.INVALID_PARAMS


def test_tools_list_is_complete_and_well_formed(db):
    tools = mcp.handle(db, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})["result"]["tools"]
    names = {t["name"] for t in tools}
    assert {"search", "get_recording", "get_transcript", "get_summary", "list_people"} <= names
    assert names == set(mcp.HANDLERS), "every advertised tool must have a handler, and no handler may be hidden"
    for t in tools:
        assert t["description"] and t["inputSchema"]["type"] == "object"
        assert t["annotations"]["readOnlyHint"] is True, "slice one writes nothing"
        for prop in t["inputSchema"].get("properties", {}).values():
            assert prop.get("type"), t["name"]


def test_serve_reads_a_conversation_from_stdin(library_with_two_recordings):
    lines = [
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}}),
        json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
        "",
        "{not json",
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                    "params": {"name": "search", "arguments": {"query": "marathon"}}}),
    ]
    out = io.StringIO()
    assert mcp.serve(library_with_two_recordings["db"], io.StringIO("\n".join(lines) + "\n"), out) == 0
    replies = [json.loads(l) for l in out.getvalue().splitlines()]

    assert len(replies) == 3, "initialize, the parse error, and the tool call — the notification gets nothing"
    assert replies[0]["id"] == 1
    assert replies[1]["error"]["code"] == mcp.PARSE_ERROR and replies[1]["id"] is None
    assert "marathon" in replies[2]["result"]["content"][0]["text"].lower()
    for line in out.getvalue().splitlines():
        assert "\n" not in line  # one message per line is the whole framing


# ---- tools ---------------------------------------------------------------------------------------------

def test_search_returns_excerpts_with_context(library_with_two_recordings):
    lib = library_with_two_recordings
    out = _call(lib["db"], "search", {"query": "Who is booking the flights?"})

    assert out["searched_for"] == ["booking", "flights"], "stopwords are dropped before the index"
    assert out["count"] == 1
    hit = out["results"][0]
    assert hit["recording_id"] == lib["done"]
    assert hit["title"] == "Marathon planning" and hit["at"] == "00:06"
    assert hit["speaker"] == "Bob"
    assert "book the flights" in hit["excerpt"]
    assert "Alice: Good morning" in hit["excerpt"], "the turn before comes with it"


def test_search_match_modes_and_no_matches(library_with_two_recordings):
    db = library_with_two_recordings["db"]
    any_hits = _call(db, "search", {"query": "marathon submarine", "match": "any"})
    assert [r["kind"] for r in any_hits["results"]] == ["summary", "moment"], "the summary says it in one line"
    assert _call(db, "search", {"query": "marathon submarine", "match": "all"})["count"] == 0

    empty = _call(db, "search", {"query": "submarine"})
    assert empty["count"] == 0 and empty["results"] == [] and empty["note"]


def test_search_returns_summary_blocks_without_a_timestamp(library_with_two_recordings):
    """A summary is not a moment: it has no second to jump to, and `get_summary` reads the rest of it."""
    out = _call(library_with_two_recordings["db"], "search", {"query": "What did we decide about the marathon?"})
    block = out["results"][0]
    assert block["kind"] == "summary" and block["heading"] == "Decisions"
    assert block["excerpt"] == "Run the marathon in October."
    assert block["recording_id"] == library_with_two_recordings["done"] and block["title"] == "Marathon planning"
    assert "at" not in block and "start_sec" not in block and "speaker" not in block


def test_search_rejects_bad_arguments(db):
    assert "query is required" in _failure(db, "search")
    assert "query is empty" in _failure(db, "search", {"query": "   "})
    assert "match must be" in _failure(db, "search", {"query": "x", "match": "some"})
    assert "limit must be a number" in _failure(db, "search", {"query": "x", "limit": "eight"})


def test_search_limit_is_clamped_not_refused(library_with_two_recordings):
    assert _call(library_with_two_recordings["db"], "search", {"query": "marathon", "limit": 9999})["count"] == 2


def test_list_recordings_filters(library_with_two_recordings):
    db = library_with_two_recordings["db"]
    out = _call(db, "list_recordings")
    assert [r["recording_id"] for r in out["recordings"]] == [
        library_with_two_recordings["queued"], library_with_two_recordings["done"]
    ], "newest first"
    assert out["recordings"][1]["has_summary"] is True
    assert out["recordings"][0]["title"] == "voice-memo.m4a", "an untitled recording falls back to its file name"

    assert _call(db, "list_recordings", {"title_contains": "marathon"})["count"] == 1
    assert _call(db, "list_recordings", {"since": "2026-09-09"})["count"] == 1
    assert _call(db, "list_recordings", {"until": "2026-09-08"})["count"] == 1
    assert _call(db, "list_recordings", {"limit": 1})["count"] == 1
    assert _call(db, "list_recordings", {"limit": 1})["total_matching"] == 2


def test_get_recording(library_with_two_recordings):
    out = _call(library_with_two_recordings["db"], "get_recording",
                {"recording_id": library_with_two_recordings["done"]})
    assert out["title"] == "Marathon planning" and out["status"] == "done"
    assert out["duration_sec"] == 95.0 and out["source"] == "dji" and out["turns"] == 3
    assert out["has_summary"] is True and out["summary_template"] == "meeting"
    assert [s["speaker"] for s in out["speakers"]] == ["Alice", "Bob"], "most talkative first"


def test_get_recording_needs_an_id_that_exists(db):
    assert "recording_id is required" in _failure(db, "get_recording")
    assert "no recording with id 404" in _failure(db, "get_recording", {"recording_id": 404})


def test_get_transcript_names_the_speakers(library_with_two_recordings):
    out = _call(library_with_two_recordings["db"], "get_transcript",
                {"recording_id": library_with_two_recordings["done"]})
    assert out["turns"] == 3 and out["truncated"] is False and out["reason"] is None
    assert out["transcript"].splitlines()[0] == "[00:00] Alice: Good morning. Today we are planning the marathon in October."
    assert "[00:06] Bob:" in out["transcript"]


def test_get_transcript_window(library_with_two_recordings):
    db = library_with_two_recordings["db"]
    rid = library_with_two_recordings["done"]
    # The window keeps every turn that overlaps it, so a timestamp taken from a search hit never
    # cuts the turn it points at in half.
    assert _call(db, "get_transcript", {"recording_id": rid, "from_sec": 13})["turns"] == 1
    assert _call(db, "get_transcript", {"recording_id": rid, "from_sec": 12})["turns"] == 2, "12.0 ends a turn"
    assert _call(db, "get_transcript", {"recording_id": rid, "to_sec": 5})["turns"] == 1
    assert _call(db, "get_transcript", {"recording_id": rid, "from_sec": 7, "to_sec": 8})["turns"] == 1

    far = _call(db, "get_transcript", {"recording_id": rid, "from_sec": 600})
    assert far["turns"] == 0 and far["reason"] == "empty_window" and far["note"]
    assert "to_sec is before from_sec" in _failure(db, "get_transcript",
                                                   {"recording_id": rid, "from_sec": 10, "to_sec": 5})


def test_get_transcript_truncates_a_long_recording(db, monkeypatch):
    rid = db.insert_recording(sha256="c" * 64, original_name="long.wav", rel_path="audio/c.wav", status="done")
    db.replace_segments(rid, [
        {"speaker": "SPEAKER_00", "start": float(i), "end": float(i + 1), "text": f"turn {i}"} for i in range(10)
    ])
    monkeypatch.setattr(mcp, "MAX_TURNS", 4)
    out = _call(db, "get_transcript", {"recording_id": rid})
    assert out["turns"] == 4 and out["turns_in_recording"] == 10 and out["truncated"] is True
    assert "from_sec=4.0" in out["note"], "the note must say exactly how to ask for the rest"


def test_get_transcript_of_a_recording_that_has_none(library_with_two_recordings):
    out = _call(library_with_two_recordings["db"], "get_transcript",
                {"recording_id": library_with_two_recordings["queued"]})
    assert out["turns"] == 0 and out["reason"] == "not_transcribed" and "queued" in out["note"]


def test_get_summary(library_with_two_recordings):
    out = _call(library_with_two_recordings["db"], "get_summary",
                {"recording_id": library_with_two_recordings["done"]})
    assert out["summary"].startswith("## Decisions") and out["reason"] is None
    assert out["template"] == "meeting" and out["model"] == "ollama:llama3.2"


def test_missing_summary_is_a_state_not_an_error(library_with_two_recordings):
    db = library_with_two_recordings["db"]
    out = _call(db, "get_summary", {"recording_id": library_with_two_recordings["queued"]})
    assert out["summary"] is None and out["reason"] == "no_summary" and out["note"]

    db.update_recording(library_with_two_recordings["queued"], summary_status="error", summary_error="ollama is not running")
    out = _call(db, "get_summary", {"recording_id": library_with_two_recordings["queued"]})
    assert out["reason"] == "summary_failed" and out["error"] == "ollama is not running"


def test_list_people(library_with_two_recordings):
    db = library_with_two_recordings["db"]
    out = _call(db, "list_people")
    assert [p["name"] for p in out["people"]] == ["Alice", "Bob", "Speaker 3"], "named first, then by speaking time"
    assert out["people"][0]["recordings"] == 1 and out["people"][0]["speaking_sec"] == 12.0
    assert out["people"][0]["last_heard"] == "2026-09-08T09:00:00"
    assert out["people"][2]["named"] is False, "an auto-created speaker is not a named person"

    named = _call(db, "list_people", {"named_only": True})
    assert [p["name"] for p in named["people"]] == ["Alice", "Bob"]


def test_unknown_tool_is_reported_to_the_model(db):
    assert "unknown tool: delete_everything" in _failure(db, "delete_everything")


def test_a_broken_library_does_not_kill_the_server(db, monkeypatch):
    import sqlite3

    def boom(*a, **k):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(db, "list_recordings", boom)
    assert "OperationalError: database is locked" in _failure(db, "list_recordings")


def _dump(db) -> dict:
    c = db.connect()
    names = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    return {t: [tuple(r) for r in c.execute(f"SELECT * FROM {t}")] for t in names}


def test_no_tool_writes_to_the_library(library_with_two_recordings):
    """Slice one is read-only: running every tool must leave every table exactly as it was."""
    db = library_with_two_recordings["db"]
    rid = library_with_two_recordings["done"]
    before = _dump(db)

    _call(db, "search", {"query": "marathon"})
    _call(db, "list_recordings")
    _call(db, "get_recording", {"recording_id": rid})
    _call(db, "get_transcript", {"recording_id": rid})
    _call(db, "get_summary", {"recording_id": rid})
    _call(db, "list_people")

    assert _dump(db) == before


def test_serve_library_refuses_a_folder_with_no_library(tmp_path, capsys):
    assert mcp.serve_library(tmp_path / "nowhere") == 2
    assert "No Rapport library" in capsys.readouterr().err
    assert not (tmp_path / "nowhere").exists(), "a typo in the path must not create an empty library"
