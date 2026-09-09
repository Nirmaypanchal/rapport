from fastapi.testclient import TestClient

from rapport.importer import Importer
from rapport.server import create_app


class _Worker:
    def status(self):
        return {"state": "idle"}


class _Recorder:
    def status(self):
        return {"active": False}


def _client(library, db, token=None):
    app = create_app(library, db, Importer(library, db), _Worker(), _Recorder(), token=token)
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
