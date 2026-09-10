from fastapi.testclient import TestClient

from rapport.importer import Importer
from rapport.server import create_app


class _Worker:
    def __init__(self):
        self.queued = []

    def status(self):
        return {"state": "idle"}

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
    assert c.get("/api/search", params={"q": "pastel"}).json()[0]["recording_id"] == rid
    r = c.patch(f"/api/recordings/{rid}", json={"title": "Design review"})
    assert r.status_code == 200 and db.get_recording(rid)["title"] == "Design review"


def test_ask_returns_sources_without_a_model(library, db):
    """summary_provider is "off" in the test library, so this is the no-model path: excerpts, no answer."""
    rid = db.insert_recording(sha256="4" * 64, original_name="a.wav", rel_path="audio/a.wav", status="done", title="Kickoff")
    db.replace_segments(rid, [{"speaker": "SPEAKER_00", "start": 12, "end": 15, "text": "the deadline is in March"}])
    c = _client(library, db)

    body = c.post("/api/ask", json={"q": "When is the deadline?"}).json()
    assert body["answer"] is None and body["reason"] == "no_model"
    assert body["sources"][0]["recording_id"] == rid and body["sources"][0]["start"] == 12
    assert "deadline" in body["sources"][0]["snippet"]

    assert c.post("/api/ask", json={"q": "  "}).status_code == 400
    assert c.post("/api/ask", json={"q": "nothing like this word exists"}).json()["reason"] == "no_matches"


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
