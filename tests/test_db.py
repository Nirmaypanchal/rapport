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


# ---- summaries in the search index ----------------------------------------

def _summarized(db, text, name="talk.wav", sha="e" * 64, title="Pricing sync"):
    rid = db.insert_recording(sha256=sha, original_name=name, rel_path=f"audio/{name}", status="done", title=title)
    db.update_recording(rid, summary=text, summary_status="done")
    return rid


def test_writing_a_summary_indexes_its_blocks(db):
    rid = _summarized(db, "## Decisions\n- Forty euros a seat.\n- Launch on the fourth.")
    assert [c["text"] for c in db.summary_chunks(rid)] == ["Forty euros a seat.", "Launch on the fourth."]
    assert [c["heading"] for c in db.summary_chunks(rid)] == ["Decisions", "Decisions"]

    hit = db.search_summaries("euros")[0]
    assert hit["recording_id"] == rid and hit["title"] == "Pricing sync" and hit["heading"] == "Decisions"
    assert "[[euros]]" in hit["snippet"], "the matching words are marked like any other search hit"


def test_a_rewritten_summary_replaces_what_was_indexed(db):
    """Regenerating a summary must not leave the old one findable — it is no longer in the library."""
    rid = _summarized(db, "- The launch slips to November.")
    db.update_recording(rid, summary="- The launch holds in October.")
    assert db.search_summaries("November") == []
    assert len(db.search_summaries("October")) == 1
    assert len(db.summary_chunks(rid)) == 1, "the old blocks are gone, not merely unfindable"


def test_clearing_a_summary_clears_its_blocks(db):
    rid = _summarized(db, "- Something was decided.")
    db.update_recording(rid, summary=None)
    assert db.summary_chunks(rid) == [] and db.search_summaries("decided") == []


def test_a_summary_that_arrives_with_the_recording_is_indexed(db):
    """Granola, Omi and Notion notes come in already summarized, through insert_recording."""
    rid = db.insert_recording(sha256="f" * 64, original_name="note.txt", rel_path="a/note.txt", status="done",
                              source="granola", summary="- Agreed to ship on Tuesday.")
    assert db.search_summaries("Tuesday")[0]["recording_id"] == rid


def test_summaries_written_before_the_index_existed_are_backfilled(db, library):
    """An existing library gets its summaries indexed the next time Rapport opens it."""
    from rapport.db import Database

    rid = _summarized(db, "- The pastel notebooks are ordered.")
    db.connect().execute("DELETE FROM summary_chunks")  # as if written by a version without the index
    db.connect().commit()
    assert db.search_summaries("notebooks") == []

    reopened = Database(library.db_path)
    assert reopened.search_summaries("notebooks")[0]["recording_id"] == rid
    assert reopened._index_unindexed_summaries() == 0, "a second open has nothing left to do"


def test_deleting_a_recording_takes_its_summary_out_of_the_index(db):
    rid = _summarized(db, "- Forty euros a seat.")
    db.delete_recording(rid)
    assert db.search_summaries("euros") == [] and db.summary_chunks(rid) == []


def test_summary_search_match_modes(db):
    _summarized(db, "- Forty euros a seat, agreed with Maya.")
    assert db.search_summaries("euros helicopter") == [], "every term must match by default"
    assert len(db.search_summaries("euros helicopter", match="any")) == 1
    assert db.search_summaries("") == [] and db.search_summaries("?") == []
