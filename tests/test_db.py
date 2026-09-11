def _rec(db, name="a.wav", sha="0" * 64):
    return db.insert_recording(sha256=sha, original_name=name, rel_path=f"audio/{name}", status="queued")


def test_insert_and_queue(db):
    rid = _rec(db)
    assert db.get_recording(rid)["status"] == "queued"
    assert db.next_queued()["id"] == rid
    db.update_recording(rid, status="done")
    assert db.next_queued() is None
    assert db.stats()["recordings"] == 1


def test_segments_and_search(db):
    rid = _rec(db)
    db.replace_segments(rid, [
        {"speaker": "SPEAKER_00", "start": 0.0, "end": 2.5, "text": "We should ship the marathon feature in October.", "words": [["We", 0.0, 0.2]]},
        {"speaker": "SPEAKER_01", "start": 2.5, "end": 4.0, "text": "Agreed, after the move to Lisbon."},
    ])
    segs = db.get_segments(rid)
    assert [s["idx"] for s in segs] == [0, 1]
    assert segs[0]["words"] == [["We", 0.0, 0.2]]
    hits = db.search("marathon")
    assert len(hits) == 1 and hits[0]["recording_id"] == rid and "[[marathon]]" in hits[0]["snippet"]
    assert db.search('lisbon "after the"')  # punctuation and phrases must not break FTS
    assert db.search("   ") == []


def test_people_and_speakers(db):
    rid = _rec(db)
    db.replace_speakers(rid, [{"label": "SPEAKER_00", "speaking_sec": 10.0}, {"label": "SPEAKER_01", "speaking_sec": 3.0}])
    pid = db.create_person("Sam", auto=False, color="peach")
    db.set_speaker_person(rid, "SPEAKER_00", pid)
    sp = {s["label"]: s for s in db.get_speakers(rid)}
    assert sp["SPEAKER_00"]["person_id"] == pid
    assert db.stats()["people"] == 1
    other = db.create_person("Sam (dup)", auto=True, color="mint")
    db.merge_people(pid, other)
    assert db.get_person(other) is None and db.get_person(pid)["name"] == "Sam"


def test_delete_cascades(db):
    rid = _rec(db)
    db.replace_segments(rid, [{"speaker": None, "start": 0, "end": 1, "text": "hello world"}])
    db.delete_recording(rid)
    assert db.get_recording(rid) is None
    assert db.search("hello") == []


def test_schema_migrates_twice(library):
    from rapport.db import Database

    Database(library.db_path)
    Database(library.db_path)  # reopening an existing library must be a no-op


def test_count_segments_matches_the_segments(db):
    rid = _rec(db, "counted.wav", "c" * 64)
    assert db.count_segments(rid) == 0
    db.replace_segments(rid, [
        {"speaker": "SPEAKER_00", "start": 0.0, "end": 1.0, "text": "one"},
        {"speaker": "SPEAKER_00", "start": 1.0, "end": 2.0, "text": "two"},
    ])
    assert db.count_segments(rid) == len(db.get_segments(rid)) == 2
    assert db.count_segments(rid + 999) == 0
