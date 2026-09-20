import json
from pathlib import Path

from fastapi.testclient import TestClient

from rapport.importer import Importer
from rapport.server import create_app


def ask_events(response) -> list[dict]:
    """`/api/ask` answers newline-delimited JSON: deltas as the model writes, then one final object."""
    assert "x-ndjson" in response.headers["content-type"]
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


def ask_answer(response) -> dict:
    """The final event — the body this route used to return in one piece."""
    events = ask_events(response)
    assert events and "delta" not in events[-1], "the stream must end with the answer, not a delta"
    return events[-1]


class _Worker:
    def __init__(self):
        self.queued = []

    def status(self):
        return {"state": "idle"}

    def wake(self):
        pass

    def summarize_later(self, rid):
        self.queued.append(rid)
        return True


class _Recorder:
    def status(self):
        return {"active": False}


def _client(library, db, token=None, worker=None):
    app = create_app(library, db, Importer(library, db), worker or _Worker(), _Recorder(), token=token)
    return TestClient(app)


def test_health_and_status(library, db):
    c = _client(library, db)
    assert c.get("/api/health").json() == {"ok": True}
    st = c.get("/api/status").json()
    assert st["library"] == str(library.root)
    assert st["settings"]["delete_from_device_after_import"] is False


def test_token_required(library, db):
    c = _client(library, db, token="secret")
    assert c.get("/api/health").status_code == 200
    assert c.get("/api/status").status_code == 401
    assert c.get("/api/status", headers={"Authorization": "Bearer secret"}).status_code == 200
    assert c.get("/api/status?token=secret").status_code == 200


def test_secrets_are_masked(library, db):
    library.update_settings({"granola_api_key": "gr-123"})
    c = _client(library, db)
    assert c.get("/api/status").json()["settings"]["granola_api_key"] == "•••"
    c.put("/api/settings", json={"patch": {"granola_api_key": "•••", "granola_auto": False}})
    assert library.settings.granola_api_key == "gr-123", "the mask must never overwrite the real key"
    assert library.settings.granola_auto is False


def test_search_and_recordings(library, db):
    rid = db.insert_recording(sha256="1" * 64, original_name="x.wav", rel_path="audio/x.wav", status="done")
    db.replace_segments(rid, [{"speaker": "SPEAKER_00", "start": 0, "end": 1, "text": "pastel colours everywhere"}])
    c = _client(library, db)
    assert c.get("/api/recordings").json()[0]["id"] == rid
    assert c.get("/api/search", params={"q": "pastel"}).json()["moments"][0]["recording_id"] == rid
    r = c.patch(f"/api/recordings/{rid}", json={"title": "Design review"})
    assert r.status_code == 200 and db.get_recording(rid)["title"] == "Design review"


def test_search_finds_summaries_beside_moments(library, db):
    """The word is in both halves of the library, so one query must come back with both."""
    rid = db.insert_recording(sha256="7" * 64, original_name="q3.wav", rel_path="audio/q3.wav", status="done", title="Pricing sync")
    db.replace_segments(rid, [{"speaker": "SPEAKER_00", "start": 30, "end": 33, "text": "so what do we do about pricing"}])
    db.update_recording(rid, summary="## Decisions\n- Pricing lands at forty euros a seat.", summary_status="done")

    found = _client(library, db).get("/api/search", params={"q": "pricing"}).json()
    assert [m["recording_id"] for m in found["moments"]] == [rid]
    assert len(found["summaries"]) == 1
    hit = found["summaries"][0]
    assert hit["recording_id"] == rid and hit["heading"] == "Decisions" and hit["title"] == "Pricing sync"
    assert "[[Pricing]]" in hit["snippet"], "a summary hit marks the matching words like any other"
    assert "start" not in hit, "a summary block has no timestamp, and the card must not be able to pretend it has one"


def test_search_finds_a_word_only_the_summary_uses(library, db):
    """The point of the whole thing: the summary says it in a word nobody said out loud."""
    rid = db.insert_recording(sha256="8" * 64, original_name="w.wav", rel_path="audio/w.wav", status="done", title="Kickoff")
    db.replace_segments(rid, [{"speaker": "SPEAKER_00", "start": 0, "end": 2, "text": "let us give it another two weeks"}])
    db.update_recording(rid, summary="- The launch was postponed.", summary_status="done")

    found = _client(library, db).get("/api/search", params={"q": "postponed"}).json()
    assert found["moments"] == [], "no turn contains the word"
    assert [s["recording_id"] for s in found["summaries"]] == [rid]


def test_search_caps_the_summaries_and_never_the_moments(library, db):
    """Summaries are there to answer in a sentence, not to push the transcript off the page."""
    for i in range(8):
        rid = db.insert_recording(sha256=str(i) * 64, original_name=f"{i}.wav", rel_path=f"audio/{i}.wav", status="done", title=f"Call {i}")
        db.replace_segments(rid, [{"speaker": "SPEAKER_00", "start": 0, "end": 1, "text": "quarterly budget talk"}])
        db.update_recording(rid, summary="- The budget holds.", summary_status="done")

    found = _client(library, db).get("/api/search", params={"q": "budget"}).json()
    assert len(found["summaries"]) == 5
    assert len(found["moments"]) == 8


def test_search_says_nothing_rather_than_half_an_answer(library, db, monkeypatch):
    """Both halves come from one call, so a failure in either is still a 400 with the reason — never
    one array and a missing one, which the UI would render as "no summaries matched"."""
    c = _client(library, db)
    assert c.get("/api/search", params={"q": ""}).json() == {"moments": [], "summaries": []}

    def unhappy(*a, **k):
        raise RuntimeError("fts is unhappy")

    monkeypatch.setattr(db, "search_summaries", unhappy)
    r = c.get("/api/search", params={"q": "anything"})
    assert r.status_code == 400 and r.json() == {"error": "fts is unhappy"}


def test_ask_returns_sources_without_a_model(library, db):
    """summary_provider is "off" in the test library, so this is the no-model path: excerpts, no answer."""
    rid = db.insert_recording(sha256="4" * 64, original_name="a.wav", rel_path="audio/a.wav", status="done", title="Kickoff")
    db.replace_segments(rid, [{"speaker": "SPEAKER_00", "start": 12, "end": 15, "text": "the deadline is in March"}])
    c = _client(library, db)

    body = ask_answer(c.post("/api/ask", json={"q": "When is the deadline?"}))
    assert body["answer"] is None and body["reason"] == "no_model"
    assert body["sources"][0]["kind"] == "moment"
    assert body["sources"][0]["recording_id"] == rid and body["sources"][0]["start"] == 12
    assert "deadline" in body["sources"][0]["snippet"]

    assert c.post("/api/ask", json={"q": "  "}).status_code == 400
    assert ask_answer(c.post("/api/ask", json={"q": "nothing like this word exists"}))["reason"] == "no_matches"


def test_ask_can_answer_from_a_summary(library, db):
    """The shape the Ask panel reads for a cited summary: no segment, no timestamp, a heading to show."""
    rid = db.insert_recording(sha256="5" * 64, original_name="b.wav", rel_path="audio/b.wav", status="done", title="Kickoff")
    db.replace_segments(rid, [{"speaker": "SPEAKER_00", "start": 12, "end": 15, "text": "so March then, probably"}])
    db.update_recording(rid, summary="## Decisions\n- The deadline is the first of March.", summary_status="done")

    body = ask_answer(_client(library, db).post("/api/ask", json={"q": "What is the deadline?"}))
    top = body["sources"][0]
    assert top["kind"] == "summary" and top["segment_id"] is None and top["start"] == 0
    assert top["heading"] == "Decisions" and top["recording_id"] == rid
    assert "deadline" in top["snippet"]


def test_summary_templates_listed(library, db):
    c = _client(library, db)
    body = c.get("/api/summary/templates").json()
    ids = [t["id"] for t in body["templates"]]
    assert "meeting" in ids and "interview" in ids and ids[-1] == "custom"
    assert body["default"] == "meeting"
    assert all(t["name"] for t in body["templates"])


def test_summary_template_default_follows_settings(library, db):
    library.update_settings({"summary_template": "lecture"})
    assert _client(library, db).get("/api/summary/templates").json()["default"] == "lecture"
    # A custom prompt that was never written is not a usable default.
    library.update_settings({"summary_template": "custom"})
    assert _client(library, db).get("/api/summary/templates").json()["default"] == "meeting"
    library.update_settings({"summary_custom_prompt": "Two bullets."})
    assert _client(library, db).get("/api/summary/templates").json()["default"] == "custom"


def test_summary_templates_list_the_sources_in_the_library(library, db):
    db.insert_recording(sha256="a" * 64, original_name="a.wav", rel_path="audio/a.wav", source="granola")
    db.insert_recording(sha256="b" * 64, original_name="b.wav", rel_path="audio/b.wav", source="granola")
    db.insert_recording(sha256="c" * 64, original_name="c.m4a", rel_path="audio/c.m4a", source="voicememos")
    body = _client(library, db).get("/api/summary/templates").json()

    assert [s["id"] for s in body["sources"]] == ["granola", "voicememos"], "the most-used source first"
    assert body["sources"][0]["count"] == 2
    assert body["by_source"] == {}, "nothing is defaulted for a source until the user says so"


def test_fs_roots_lists_what_is_on_this_mac(library, db, tmp_path, monkeypatch):
    # The same list that resolves a watched folder to its service, so the Sources page and the filing agree.
    (tmp_path / "Library/Mobile Documents/com~apple~CloudDocs").mkdir(parents=True)
    (tmp_path / "Desktop").mkdir()
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))

    roots = _client(library, db).get("/api/fs/roots").json()
    assert [(r["key"], r["label"]) for r in roots] == [("icloud", "iCloud Drive"), ("desktop", "Desktop")]
    assert roots[0]["path"] == str(tmp_path / "Library/Mobile Documents/com~apple~CloudDocs")

    # An app's own folder is a root too, so its tile opens at it: Zoom saves local recordings to ~/Documents/Zoom.
    (tmp_path / "Documents/Zoom").mkdir(parents=True)
    zoom = [r for r in _client(library, db).get("/api/fs/roots").json() if r["key"] == "zoom"]
    assert zoom == [{"key": "zoom", "label": "Zoom", "path": str(tmp_path / "Documents/Zoom")}]


def test_a_zoom_meeting_is_filed_under_zoom_not_under_watched_folder(library, db, tmp_path, monkeypatch):
    # Zoom writes one folder per meeting; watching ~/Documents/Zoom brings every one of them in, and they are filed
    # under the tile the user set the folder up from, so a Zoom-only summary template is expressible.
    (tmp_path / "Documents/Zoom/2026-09-20 10.00.00 Standup").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    # `source_volume` is the *watched* folder, and `audio_files` recurses, so one watch covers every meeting folder.
    db.insert_recording(sha256="1" * 64, original_name="a.m4a", rel_path="audio/a.m4a", source="folder", source_volume=str(tmp_path / "Documents/Zoom"))
    db.insert_recording(sha256="2" * 64, original_name="b.m4a", rel_path="audio/b.m4a", source="folder", source_volume=str(tmp_path / "Elsewhere"))
    c = _client(library, db)

    places = {r["original_name"]: r["source_place"] for r in c.get("/api/recordings").json()}
    assert places == {"a.m4a": "zoom", "b.m4a": "folder"}
    assert dict((s["id"], s["count"]) for s in c.get("/api/summary/templates").json()["sources"]) == {"zoom": 1, "folder": 1}


def test_the_sources_offered_are_places_not_the_mechanism_column(library, db, tmp_path, monkeypatch):
    """Settings offers a row per *place*, which is what the user picked on the Sources page.

    Two watched folders under iCloud Drive are one iCloud row, not two `folder` ones; a third folder that is
    nobody's stays generic; and `microphone` is offered under the name the Sources page gives its tile.
    """
    icloud = tmp_path / "Library/Mobile Documents/com~apple~CloudDocs"
    icloud.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    for i, (source, volume) in enumerate([
        ("folder", str(icloud / "Recorder")),
        ("folder", str(icloud / "Meetings")),
        ("folder", str(tmp_path / "Elsewhere")),
        ("microphone", "microphone"),
    ]):
        db.insert_recording(sha256=str(i) * 64, original_name=f"{i}.wav", rel_path=f"audio/{i}.wav", source=source, source_volume=volume)

    body = _client(library, db).get("/api/summary/templates").json()
    assert [(s["id"], s["count"]) for s in body["sources"]] == [("icloud", 2), ("folder", 1), ("mic", 1)]


def test_a_recording_carries_the_place_it_came_from(library, db, tmp_path, monkeypatch):
    # The UI reads the resolved key back rather than re-deriving it: only this Mac knows where its iCloud Drive is.
    icloud = tmp_path / "Library/Mobile Documents/com~apple~CloudDocs"
    icloud.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    rid = db.insert_recording(sha256="f" * 64, original_name="f.wav", rel_path="audio/f.wav", source="folder", source_volume=str(icloud / "Recorder"))
    c = _client(library, db)

    assert c.get("/api/recordings").json()[0]["source_place"] == "icloud"
    assert c.get(f"/api/recordings/{rid}").json()["source_place"] == "icloud"
    assert c.patch(f"/api/recordings/{rid}", json={"title": "Standup"}).json()["source_place"] == "icloud"
    assert c.get(f"/api/recordings/{rid}").json()["source"] == "folder", "the mechanism column is untouched"


def test_a_source_default_round_trips_and_is_cleaned(library, db):
    c = _client(library, db)
    c.put("/api/settings", json={"patch": {"summary_template_by_source": {"voicememos": "journal"}}})
    body = c.get("/api/summary/templates").json()
    assert body["by_source"] == {"voicememos": "journal"}
    assert [s["id"] for s in body["sources"]] == ["voicememos"], "a source with an override shows with no recordings"

    # A template that does not exist is not stored, and neither is a source with no name.
    c.put("/api/settings", json={"patch": {"summary_template_by_source": {"omi": "no-such-template", "": "journal"}}})
    assert library.settings.summary_template_by_source == {}
    assert c.get("/api/summary/templates").json()["by_source"] == {}

    c.put("/api/settings", json={"patch": {"summary_template_by_source": "not a map"}})
    assert library.settings.summary_template_by_source == {}


def test_summarize_stores_the_chosen_template(library, db):
    worker = _Worker()
    rid = db.insert_recording(sha256="2" * 64, original_name="y.wav", rel_path="audio/y.wav", status="done")
    c = _client(library, db, worker=worker)

    assert c.post(f"/api/recordings/{rid}/summarize", json={"template": "interview"}).status_code == 200
    assert db.get_recording(rid)["summary_template"] == "interview"
    assert worker.queued == [rid]

    # No template in the body keeps whatever the recording already uses.
    assert c.post(f"/api/recordings/{rid}/summarize", json={}).status_code == 200
    assert db.get_recording(rid)["summary_template"] == "interview"

    bad = c.post(f"/api/recordings/{rid}/summarize", json={"template": "nonsense"})
    assert bad.status_code == 400
    assert db.get_recording(rid)["summary_template"] == "interview", "a bad template must not overwrite the good one"


def test_summarize_requires_a_processed_recording(library, db):
    rid = db.insert_recording(sha256="3" * 64, original_name="z.wav", rel_path="audio/z.wav", status="queued")
    assert _client(library, db).post(f"/api/recordings/{rid}/summarize", json={}).status_code == 409
    assert _client(library, db).post("/api/recordings/9999/summarize", json={}).status_code == 404


def test_import_path_returns_the_imported_ids(library, db, tmp_path):
    """`POST /api/import/path` answers `{"imported": [id, ...]}`. scripts/e2e.py reads that key by hand,
    so pin it here: it read the wrong one for a day and only the nightly noticed."""
    import wave

    src = tmp_path / "TX01_MIC001_20260909_090000_e2e.wav"
    with wave.open(str(src), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 16000)

    body = _client(library, db).post("/api/import/path", json={"path": str(src)}).json()
    assert list(body) == ["imported"]
    assert body["imported"] and db.get_recording(body["imported"][0])["original_name"] == src.name


def test_ask_streams_the_answer_line_by_line(library, db, monkeypatch):
    """What the panel reads: every delta on its own line, then one object with the sources. A citation
    number only means something once the whole list has arrived, which is why it comes last."""
    rid = db.insert_recording(sha256="6" * 64, original_name="c.wav", rel_path="audio/c.wav", status="done", title="Kickoff")
    db.replace_segments(rid, [{"speaker": "SPEAKER_00", "start": 12, "end": 15, "text": "the deadline is in March"}])
    monkeypatch.setattr("rapport.ask.resolve_provider", lambda *a, **k: ("ollama", "llama3"))
    monkeypatch.setattr("rapport.ask.stream_chat", lambda *a, **k: iter(["March ", "the first [1]."]))

    r = _client(library, db).post("/api/ask", json={"q": "When is the deadline?"})
    assert r.status_code == 200
    events = ask_events(r)
    assert [e["delta"] for e in events[:-1]] == ["March ", "the first [1]."]
    assert events[-1]["answer"] == "March the first [1]." and events[-1]["sources"][0]["recording_id"] == rid


def test_ask_still_refuses_an_empty_question_with_a_status_code(library, db):
    """A 400 has to happen before the stream starts, or the client gets 200 and a body full of nothing."""
    assert _client(library, db).post("/api/ask", json={"q": "  "}).status_code == 400


def test_a_delta_with_a_newline_in_it_stays_one_line(library, db, monkeypatch):
    """Models write newlines — a bulleted answer is mostly newlines. If one reached the wire raw it would
    split an event in two and the client would read half a JSON object."""
    rid = db.insert_recording(sha256="7" * 64, original_name="d.wav", rel_path="audio/d.wav", status="done", title="Kickoff")
    db.replace_segments(rid, [{"speaker": "SPEAKER_00", "start": 1, "end": 2, "text": "the deadline is in March"}])
    monkeypatch.setattr("rapport.ask.resolve_provider", lambda *a, **k: ("ollama", "llama3"))
    monkeypatch.setattr("rapport.ask.stream_chat", lambda *a, **k: iter(["- March [1]\n", "- and\nApril\n"]))

    r = _client(library, db).post("/api/ask", json={"q": "When is the deadline?"})
    events = ask_events(r)
    assert len(events) == 3, "two deltas and the answer, however many newlines are inside them"
    assert [e["delta"] for e in events[:-1]] == ["- March [1]\n", "- and\nApril\n"]
    assert events[-1]["answer"] == "- March [1]\n- and\nApril"
