import wave
from pathlib import Path

from rapport.importer import Importer


def _wav(path: Path, seconds: float = 0.5, rate: int = 16000) -> Path:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(rate * seconds))
    return path


def test_import_copies_and_dedupes(library, db, tmp_path):
    src = _wav(tmp_path / "TX01_MIC001_20260907_140758.wav")
    imp = Importer(library, db)
    rid = imp.import_file(src, source_volume="NO NAME", min_age=0)
    assert rid
    rec = db.get_recording(rid)
    assert rec["transmitter"] == "TX01" and rec["recorded_at"].startswith("2026-09-07T14:07:58")
    copied = library.root / rec["rel_path"]
    assert copied.exists() and copied.read_bytes() == src.read_bytes()
    assert src.exists(), "the source must never be deleted by default"
    assert imp.import_file(src, min_age=0) is None, "same bytes again must be skipped"
    assert db.stats()["recordings"] == 1


def test_import_skips_non_audio_and_empty(library, db, tmp_path):
    imp = Importer(library, db)
    (tmp_path / "notes.txt").write_text("x")
    assert imp.import_file(tmp_path / "notes.txt", min_age=0) is None
    (tmp_path / "empty.wav").write_bytes(b"")
    assert imp.import_file(tmp_path / "empty.wav", min_age=0) is None


def test_import_transcript_only_item(library, db):
    imp = Importer(library, db)
    rid = imp.import_transcript({
        "uid": "g-1", "title": "Weekly sync", "recorded_at": "2026-09-08T14:09:00", "duration_sec": 60.0,
        "segments": [{"speaker": "Me", "text": "Let's plan the launch.", "start": 0.0, "end": 3.0}],
        "summary": "## Summary\nLaunch planning.",
    }, source="granola")
    assert rid
    rec = db.get_recording(rid)
    assert rec["source"] == "granola" and rec["source_id"] == "g-1"
    assert db.search("launch")
    assert imp.import_transcript({"uid": "g-1", "title": "dup", "segments": []}, source="granola") is None
