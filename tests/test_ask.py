"""Retrieval assembly for "Ask your library". No model runs here: everything up to the prompt is plain Python."""
import pytest

from rapport.ask import ask, build_user, cited, clock, keywords, passages, pick_hits


# ---- the question -> search terms ----------------------------------------

def test_keywords_drops_stopwords_and_punctuation():
    assert keywords("What did we decide about the pricing?") == ["decide", "pricing"]
    assert keywords("Who's paying for Maya's laptop -- the 2024 one?") == ["who's", "paying", "maya's", "laptop", "2024", "one"]


def test_keywords_dedupes_and_caps():
    assert keywords("budget budget BUDGET timeline") == ["budget", "timeline"]
    assert len(keywords(" ".join(f"word{i}" for i in range(30)))) == 12


def test_keywords_keeps_stopwords_when_nothing_else_is_left():
    """Searching for nothing finds nothing, so a question made only of stopwords keeps them."""
    assert keywords("what is it about?") == ["what", "is", "it", "about"]
    assert keywords("!!!") == []


# ---- thinning the hits ----------------------------------------------------

def _hit(sid, rid):
    return {"id": sid, "recording_id": rid}


def test_pick_hits_caps_per_recording_and_in_total():
    hits = [_hit(1, 7), _hit(2, 7), _hit(3, 7), _hit(4, 8), _hit(5, 9)]
    assert [h["id"] for h in pick_hits(hits)] == [1, 2, 4, 5], "a third hit from recording 7 is dropped"
    assert [h["id"] for h in pick_hits(hits, max_passages=2)] == [1, 2]
    assert [h["id"] for h in pick_hits(hits, per_recording=1)] == [1, 4, 5]


def test_pick_hits_keeps_the_ranking():
    hits = [_hit(9, 1), _hit(3, 2), _hit(5, 1)]
    assert [h["id"] for h in pick_hits(hits)] == [9, 3, 5]


# ---- hits -> excerpts -----------------------------------------------------

@pytest.fixture
def library_with_talk(db):
    rid = db.insert_recording(sha256="a" * 64, original_name="standup.wav", rel_path="audio/standup.wav",
                              status="done", title="Monday standup", recorded_at="2026-09-07T09:00:00+02:00")
    db.replace_segments(rid, [
        {"speaker": "SPEAKER_00", "start": 0, "end": 4, "text": "Morning everyone, quick round."},
        {"speaker": "SPEAKER_01", "start": 4, "end": 9, "text": "We settled the pricing at forty euros a seat."},
        {"speaker": "SPEAKER_00", "start": 9, "end": 12, "text": "Good, that matches the budget."},
        {"speaker": "SPEAKER_01", "start": 12, "end": 16, "text": "The launch date is still the fourth of October."},
    ])
    return rid


def test_passages_carry_the_turns_around_the_hit(db, library_with_talk):
    hits = db.search("pricing", match="any")
    found = passages(db, hits)
    assert len(found) == 1
    p = found[0]
    assert p.recording_id == library_with_talk and p.start == 4 and p.title == "Monday standup"
    assert "quick round" in p.text and "forty euros" in p.text and "matches the budget" in p.text
    assert "fourth of October" not in p.text, "only one turn of context on each side"
    assert p.text.startswith("SPEAKER_00: "), "each line is attributed"


def test_passages_use_the_person_name_when_the_speaker_is_known(db, library_with_talk):
    pid = db.create_person("Maya", auto=False, color="sky")
    db.replace_speakers(library_with_talk, [{"label": "SPEAKER_01", "person_id": pid, "speaking_sec": 9}])
    p = passages(db, db.search("pricing", match="any"))[0]
    assert p.speaker == "Maya" and "Maya: We settled the pricing" in p.text


def test_passages_drop_hits_another_excerpt_already_covers(db, library_with_talk):
    """"pricing budget" matches two neighbouring turns; showing the same moment twice would be noise."""
    found = passages(db, pick_hits(db.search("pricing budget", match="any")))
    assert len(found) == 1


def test_ask_spreads_over_recordings(db):
    for n, (title, text) in enumerate([("First", "the budget is tight"), ("Second", "budget approved")]):
        rid = db.insert_recording(sha256=str(n) * 64, original_name=f"{n}.wav", rel_path=f"a/{n}.wav", status="done", title=title)
        db.replace_segments(rid, [{"speaker": "SPEAKER_00", "start": 0, "end": 3, "text": text}])
    found = passages(db, pick_hits(db.search("budget", match="any")))
    assert {p.title for p in found} == {"First", "Second"}


# ---- the prompt -----------------------------------------------------------

def test_build_user_numbers_the_excerpts(db, library_with_talk):
    found = passages(db, db.search("pricing", match="any"))
    user = build_user("What did we agree on?", found)
    assert user.startswith("Question: What did we agree on?")
    assert "[1] Monday standup, 2026-09-07, at 00:04" in user
    assert "forty euros" in user


def test_clock():
    assert clock(0) == "00:00" and clock(65) == "01:05" and clock(3725) == "1:02:05" and clock(-4) == "00:00"


def test_cited_reads_the_numbers_the_answer_used():
    assert cited("Forty euros a seat [2]. The date moved [1][2].", 3) == [2, 1]
    assert cited("Nothing here.", 3) == []
    assert cited("Out of range [9] and zero [0].", 3) == []


# ---- end to end (no model) ------------------------------------------------

def test_ask_returns_the_excerpts_when_no_model_is_available(db, library_with_talk):
    out = ask(db, "What did we decide about pricing?", provider="off")
    assert out["answer"] is None and out["reason"] == "no_model" and out["model"] is None
    assert [s["recording_id"] for s in out["sources"]] == [library_with_talk]
    src = out["sources"][0]
    assert src["n"] == 1 and src["start"] == 4 and "pricing" in src["snippet"] and src["cited"] is True


def test_ask_says_when_nothing_matches(db, library_with_talk):
    out = ask(db, "What about the helicopter?", provider="off")
    assert out["sources"] == [] and out["reason"] == "no_matches" and out["answer"] is None


def test_ask_needs_a_question(db):
    with pytest.raises(ValueError):
        ask(db, "   ", provider="off")


def test_ask_marks_only_the_cited_excerpts(db, library_with_talk, monkeypatch):
    for n in range(2):  # a second recording so there is something to leave uncited
        rid = db.insert_recording(sha256=f"{n}b" * 32, original_name=f"{n}.wav", rel_path=f"a/{n}.wav", status="done", title=f"Other {n}")
        db.replace_segments(rid, [{"speaker": "SPEAKER_00", "start": 0, "end": 3, "text": "pricing was mentioned once"}])
    monkeypatch.setattr("rapport.ask.chat", lambda *a, **k: "Forty euros a seat [1].")
    monkeypatch.setattr("rapport.ask.resolve_provider", lambda *a, **k: ("ollama", "llama3"))
    out = ask(db, "What is the pricing?")
    assert out["answer"] == "Forty euros a seat [1]." and out["model"] == {"provider": "ollama", "model": "llama3"}
    assert len(out["sources"]) > 1
    assert [s["cited"] for s in out["sources"]] == [True] + [False] * (len(out["sources"]) - 1)


def test_ask_keeps_the_excerpts_when_the_model_fails(db, library_with_talk, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("Ollama error 500: model not found")

    monkeypatch.setattr("rapport.ask.chat", boom)
    monkeypatch.setattr("rapport.ask.resolve_provider", lambda *a, **k: ("ollama", "llama3"))
    out = ask(db, "What is the pricing?")
    assert out["reason"] == "model_error" and "model not found" in out["error"]
    assert out["answer"] is None and len(out["sources"]) == 1


def test_ask_reports_an_empty_answer(db, library_with_talk, monkeypatch):
    monkeypatch.setattr("rapport.ask.chat", lambda *a, **k: "   ")
    monkeypatch.setattr("rapport.ask.resolve_provider", lambda *a, **k: ("mlx", "qwen"))
    out = ask(db, "What is the pricing?")
    assert out["reason"] == "empty_answer" and out["answer"] is None and out["sources"]


# ---- the search itself ----------------------------------------------------

def test_search_match_any_vs_all(db, library_with_talk):
    assert db.search("pricing helicopter") == [], "every term must match by default"
    assert db.search("pricing helicopter", match="any"), "a question only needs some of its words"
