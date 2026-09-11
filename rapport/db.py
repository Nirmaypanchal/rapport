"""SQLite storage. One connection per thread; WAL mode so the UI can read while the worker writes."""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS recordings (
    id INTEGER PRIMARY KEY,
    sha256 TEXT UNIQUE NOT NULL,
    original_name TEXT NOT NULL,
    rel_path TEXT NOT NULL,
    transmitter TEXT,
    file_index TEXT,
    recorded_at TEXT,            -- ISO local time
    duration_sec REAL,
    sample_rate INTEGER,
    channels INTEGER,
    size_bytes INTEGER,
    source_volume TEXT,
    source_path TEXT,
    deleted_from_device INTEGER DEFAULT 0,
    imported_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',   -- queued | processing | done | error
    stage TEXT,
    error TEXT,
    title TEXT,
    notes TEXT DEFAULT '',
    language TEXT,
    whisper_model TEXT,
    diarizer TEXT,
    processed_at TEXT
);

CREATE TABLE IF NOT EXISTS people (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    auto INTEGER DEFAULT 1,       -- 1 = auto-created "Speaker N", 0 = user named
    color TEXT,
    note TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS recording_speakers (
    id INTEGER PRIMARY KEY,
    recording_id INTEGER NOT NULL REFERENCES recordings(id) ON DELETE CASCADE,
    label TEXT NOT NULL,          -- SPEAKER_00 ...
    person_id INTEGER REFERENCES people(id) ON DELETE SET NULL,
    speaking_sec REAL DEFAULT 0,
    embedding BLOB,               -- float32 vector
    embedding_model TEXT,
    similarity REAL,              -- similarity to the matched person at processing time
    UNIQUE(recording_id, label)
);

CREATE TABLE IF NOT EXISTS segments (
    id INTEGER PRIMARY KEY,
    recording_id INTEGER NOT NULL REFERENCES recordings(id) ON DELETE CASCADE,
    idx INTEGER NOT NULL,
    speaker_label TEXT,
    start REAL NOT NULL,
    end REAL NOT NULL,
    text TEXT NOT NULL,
    words TEXT                    -- JSON [[word, start, end], ...]
);
CREATE INDEX IF NOT EXISTS segments_rec ON segments(recording_id, idx);

CREATE VIRTUAL TABLE IF NOT EXISTS segments_fts USING fts5(
    text, content='segments', content_rowid='id', tokenize='porter unicode61'
);
CREATE TRIGGER IF NOT EXISTS segments_ai AFTER INSERT ON segments BEGIN
    INSERT INTO segments_fts(rowid, text) VALUES (new.id, new.text);
END;
CREATE TRIGGER IF NOT EXISTS segments_au AFTER UPDATE OF text ON segments BEGIN
    INSERT INTO segments_fts(segments_fts, rowid, text) VALUES ('delete', old.id, old.text);
    INSERT INTO segments_fts(rowid, text) VALUES (new.id, new.text);
END;
CREATE TRIGGER IF NOT EXISTS segments_ad AFTER DELETE ON segments BEGIN
    INSERT INTO segments_fts(segments_fts, rowid, text) VALUES ('delete', old.id, old.text);
END;

CREATE TABLE IF NOT EXISTS log (
    id INTEGER PRIMARY KEY,
    ts TEXT NOT NULL,
    level TEXT NOT NULL,
    message TEXT NOT NULL
);
"""


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._local = threading.local()
        with self.connect() as c:
            c.executescript(SCHEMA)
        self._migrate_colors()
        self._migrate_columns()

    def _migrate_columns(self) -> None:
        c = self.connect()
        cols = {r[1] for r in c.execute("PRAGMA table_info(recordings)")}
        with c:
            if "source" not in cols:
                c.execute("ALTER TABLE recordings ADD COLUMN source TEXT DEFAULT 'dji'")
            if "source_id" not in cols:
                c.execute("ALTER TABLE recordings ADD COLUMN source_id TEXT")
            for col, typ in (("summary", "TEXT"), ("summary_model", "TEXT"), ("summary_at", "TEXT"), ("summary_status", "TEXT"), ("summary_error", "TEXT"), ("summary_template", "TEXT"), ("has_audio", "INTEGER DEFAULT 1"), ("progress", "REAL")):
                if col not in cols:
                    c.execute(f"ALTER TABLE recordings ADD COLUMN {col} {typ}")
            scols = {r[1] for r in c.execute("PRAGMA table_info(recording_speakers)")}
            if "display_name" not in scols:
                c.execute("ALTER TABLE recording_speakers ADD COLUMN display_name TEXT")

    def source_ids(self, source: str) -> set[str]:
        return {r[0] for r in self.connect().execute("SELECT source_id FROM recordings WHERE source=? AND source_id IS NOT NULL", (source,))}

    def has_source_id(self, source: str, source_id: str) -> bool:
        return self.connect().execute("SELECT 1 FROM recordings WHERE source=? AND source_id=?", (source, source_id)).fetchone() is not None

    def _migrate_colors(self) -> None:
        """People used to store a hex colour; the UI now expects a palette name."""
        from .speakers import COLORS

        c = self.connect()
        rows = c.execute("SELECT id, color FROM people ORDER BY id").fetchall()
        if not any((r["color"] or "").startswith("#") or not r["color"] for r in rows):
            return
        with c:
            for i, r in enumerate(rows):
                if (r["color"] or "").startswith("#") or not r["color"]:
                    c.execute("UPDATE people SET color=? WHERE id=?", (COLORS[i % len(COLORS)], r["id"]))

    def connect(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn = conn
        return conn

    # ---- log -------------------------------------------------------------
    def log(self, message: str, level: str = "info") -> None:
        c = self.connect()
        with c:
            c.execute("INSERT INTO log(ts, level, message) VALUES (?,?,?)", (now_iso(), level, message))
            c.execute("DELETE FROM log WHERE id < (SELECT MAX(id) FROM log) - 2000")

    def recent_log(self, limit: int = 100) -> list[dict]:
        rows = self.connect().execute("SELECT * FROM log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    # ---- recordings ------------------------------------------------------
    def has_sha(self, sha256: str) -> bool:
        return self.connect().execute("SELECT 1 FROM recordings WHERE sha256=?", (sha256,)).fetchone() is not None

    def insert_recording(self, **cols) -> int:
        cols.setdefault("imported_at", now_iso())
        keys = ", ".join(cols)
        qs = ", ".join("?" for _ in cols)
        c = self.connect()
        with c:
            cur = c.execute(f"INSERT INTO recordings({keys}) VALUES ({qs})", tuple(cols.values()))
            return cur.lastrowid

    def update_recording(self, rid: int, **cols) -> None:
        if not cols:
            return
        sets = ", ".join(f"{k}=?" for k in cols)
        c = self.connect()
        with c:
            c.execute(f"UPDATE recordings SET {sets} WHERE id=?", (*cols.values(), rid))

    def get_recording(self, rid: int) -> dict | None:
        r = self.connect().execute("SELECT * FROM recordings WHERE id=?", (rid,)).fetchone()
        return dict(r) if r else None

    def list_recordings(self) -> list[dict]:
        rows = self.connect().execute(
            "SELECT * FROM recordings ORDER BY COALESCE(recorded_at, imported_at) DESC, id DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def next_queued(self) -> dict | None:
        r = self.connect().execute(
            "SELECT * FROM recordings WHERE status='queued' ORDER BY id ASC LIMIT 1"
        ).fetchone()
        return dict(r) if r else None

    def next_summary_queued(self) -> dict | None:
        r = self.connect().execute(
            "SELECT * FROM recordings WHERE status='done' AND summary_status='queued' ORDER BY id ASC LIMIT 1"
        ).fetchone()
        return dict(r) if r else None

    def delete_recording(self, rid: int) -> None:
        c = self.connect()
        with c:
            c.execute("DELETE FROM recordings WHERE id=?", (rid,))

    # ---- segments & speakers --------------------------------------------
    def replace_segments(self, rid: int, segments: list[dict]) -> None:
        c = self.connect()
        with c:
            c.execute("DELETE FROM segments WHERE recording_id=?", (rid,))
            c.executemany(
                "INSERT INTO segments(recording_id, idx, speaker_label, start, end, text, words) VALUES (?,?,?,?,?,?,?)",
                [
                    (rid, i, s.get("speaker"), s["start"], s["end"], s["text"], json.dumps(s.get("words") or []))
                    for i, s in enumerate(segments)
                ],
            )

    def get_segments(self, rid: int) -> list[dict]:
        rows = self.connect().execute(
            "SELECT id, idx, speaker_label, start, end, text, words FROM segments WHERE recording_id=? ORDER BY idx",
            (rid,),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["words"] = json.loads(d["words"] or "[]")
            out.append(d)
        return out

    # ---- manual corrections -----------------------------------------------
    def count_segments(self, rid: int) -> int:
        """How many turns a recording has, without loading them (and their word timings) to find out."""
        return self.connect().execute("SELECT COUNT(*) FROM segments WHERE recording_id=?", (rid,)).fetchone()[0]

    def get_segment(self, sid: int) -> dict | None:
        r = self.connect().execute("SELECT * FROM segments WHERE id=?", (sid,)).fetchone()
        if not r:
            return None
        d = dict(r)
        d["words"] = json.loads(d["words"] or "[]")
        return d

    def update_segment(self, sid: int, **cols) -> None:
        if "words" in cols:
            cols["words"] = json.dumps(cols["words"])
        sets = ", ".join(f"{k}=?" for k in cols)
        c = self.connect()
        with c:
            c.execute(f"UPDATE segments SET {sets} WHERE id=?", (*cols.values(), sid))

    def insert_segment_after(self, rid: int, after_idx: int, seg: dict) -> int:
        """Insert a segment at idx=after_idx+1, shifting later ones down."""
        c = self.connect()
        with c:
            c.execute("UPDATE segments SET idx = idx + 1 WHERE recording_id=? AND idx > ?", (rid, after_idx))
            cur = c.execute(
                "INSERT INTO segments(recording_id, idx, speaker_label, start, end, text, words) VALUES (?,?,?,?,?,?,?)",
                (rid, after_idx + 1, seg["speaker"], seg["start"], seg["end"], seg["text"], json.dumps(seg.get("words") or [])),
            )
            return cur.lastrowid

    def delete_segment(self, sid: int) -> None:
        c = self.connect()
        with c:
            row = c.execute("SELECT recording_id, idx FROM segments WHERE id=?", (sid,)).fetchone()
            c.execute("DELETE FROM segments WHERE id=?", (sid,))
            if row:  # keep idx contiguous
                c.execute("UPDATE segments SET idx = idx - 1 WHERE recording_id=? AND idx > ?", (row["recording_id"], row["idx"]))

    def ensure_speaker_for_person(self, rid: int, person_id: int) -> str:
        """Return the label used for this person in this recording, creating a speaker row if needed."""
        c = self.connect()
        r = c.execute("SELECT label FROM recording_speakers WHERE recording_id=? AND person_id=?", (rid, person_id)).fetchone()
        if r:
            return r["label"]
        labels = [x["label"] for x in c.execute("SELECT label FROM recording_speakers WHERE recording_id=?", (rid,))]
        n = 0
        while f"SPEAKER_{n:02d}" in labels:
            n += 1
        label = f"SPEAKER_{n:02d}"
        with c:
            c.execute("INSERT INTO recording_speakers(recording_id, label, person_id, speaking_sec) VALUES (?,?,?,0)", (rid, label, person_id))
        return label

    def recompute_speaking(self, rid: int) -> None:
        """Refresh speaking_sec from segments; drop speakers that no longer have any turn."""
        c = self.connect()
        with c:
            rows = c.execute("SELECT speaker_label, SUM(end - start) AS sec FROM segments WHERE recording_id=? GROUP BY speaker_label", (rid,)).fetchall()
            secs = {r["speaker_label"]: r["sec"] or 0.0 for r in rows}
            for sp in c.execute("SELECT id, label FROM recording_speakers WHERE recording_id=?", (rid,)).fetchall():
                if sp["label"] in secs:
                    c.execute("UPDATE recording_speakers SET speaking_sec=? WHERE id=?", (round(secs[sp["label"]], 2), sp["id"]))
                else:
                    c.execute("DELETE FROM recording_speakers WHERE id=?", (sp["id"],))

    def replace_speakers(self, rid: int, speakers: list[dict]) -> None:
        c = self.connect()
        with c:
            c.execute("DELETE FROM recording_speakers WHERE recording_id=?", (rid,))
            c.executemany(
                "INSERT INTO recording_speakers(recording_id, label, person_id, speaking_sec, embedding, embedding_model, similarity, display_name) VALUES (?,?,?,?,?,?,?,?)",
                [
                    (rid, s["label"], s.get("person_id"), s.get("speaking_sec", 0), s.get("embedding"), s.get("embedding_model"), s.get("similarity"), s.get("display_name"))
                    for s in speakers
                ],
            )

    def get_speakers(self, rid: int) -> list[dict]:
        rows = self.connect().execute(
            """SELECT rs.id, rs.label, rs.person_id, rs.speaking_sec, rs.similarity, rs.embedding_model, rs.display_name,
                      p.name AS person_name, p.color AS person_color, p.auto AS person_auto
               FROM recording_speakers rs LEFT JOIN people p ON p.id = rs.person_id
               WHERE rs.recording_id=? ORDER BY rs.speaking_sec DESC""",
            (rid,),
        ).fetchall()
        return [dict(r) for r in rows]

    def speakers_for_recordings(self) -> dict[int, list[dict]]:
        rows = self.connect().execute(
            """SELECT rs.recording_id, rs.label, rs.person_id, rs.speaking_sec, rs.similarity, rs.display_name, p.name AS person_name, p.color AS person_color
               FROM recording_speakers rs LEFT JOIN people p ON p.id = rs.person_id ORDER BY rs.speaking_sec DESC"""
        ).fetchall()
        out: dict[int, list[dict]] = {}
        for r in rows:
            out.setdefault(r["recording_id"], []).append(dict(r))
        return out

    def set_speaker_person(self, rid: int, label: str, person_id: int | None) -> None:
        c = self.connect()
        with c:
            c.execute(
                "UPDATE recording_speakers SET person_id=?, similarity=NULL WHERE recording_id=? AND label=?",
                (person_id, rid, label),
            )

    # ---- people ----------------------------------------------------------
    def create_person(self, name: str, auto: bool, color: str) -> int:
        c = self.connect()
        with c:
            cur = c.execute(
                "INSERT INTO people(name, auto, color, created_at) VALUES (?,?,?,?)",
                (name, 1 if auto else 0, color, now_iso()),
            )
            return cur.lastrowid

    def get_person(self, pid: int) -> dict | None:
        r = self.connect().execute("SELECT * FROM people WHERE id=?", (pid,)).fetchone()
        return dict(r) if r else None

    def list_people(self) -> list[dict]:
        rows = self.connect().execute(
            """SELECT p.*, COUNT(rs.id) AS appearances, COALESCE(SUM(rs.speaking_sec),0) AS speaking_sec,
                      MAX(r.recorded_at) AS last_heard
               FROM people p
               LEFT JOIN recording_speakers rs ON rs.person_id = p.id
               LEFT JOIN recordings r ON r.id = rs.recording_id
               GROUP BY p.id ORDER BY p.auto ASC, speaking_sec DESC"""
        ).fetchall()
        return [dict(r) for r in rows]

    def update_person(self, pid: int, **cols) -> None:
        if not cols:
            return
        sets = ", ".join(f"{k}=?" for k in cols)
        c = self.connect()
        with c:
            c.execute(f"UPDATE people SET {sets} WHERE id=?", (*cols.values(), pid))

    def merge_people(self, keep_id: int, remove_id: int) -> None:
        c = self.connect()
        with c:
            c.execute("UPDATE recording_speakers SET person_id=? WHERE person_id=?", (keep_id, remove_id))
            c.execute("DELETE FROM people WHERE id=?", (remove_id,))

    def delete_person(self, pid: int) -> None:
        c = self.connect()
        with c:
            c.execute("DELETE FROM people WHERE id=?", (pid,))

    def reset_people(self) -> int:
        """Forget every person and every voice match. Speaker labels and transcripts are untouched."""
        c = self.connect()
        with c:
            n = c.execute("SELECT COUNT(*) FROM people").fetchone()[0]
            c.execute("UPDATE recording_speakers SET person_id=NULL, similarity=NULL")
            c.execute("DELETE FROM people")
        return n

    def speakers_with_embeddings(self, rid: int) -> list[dict]:
        rows = self.connect().execute(
            "SELECT id, label, speaking_sec, embedding, embedding_model, display_name FROM recording_speakers WHERE recording_id=? ORDER BY speaking_sec DESC", (rid,)
        ).fetchall()
        return [dict(r) for r in rows]

    def queue_all_audio(self) -> int:
        c = self.connect()
        with c:
            cur = c.execute("UPDATE recordings SET status='queued', stage=NULL, error=NULL WHERE has_audio=1 AND status IN ('done','error')")
            return cur.rowcount

    def person_embeddings(self, model: str) -> list[tuple[int, bytes, float]]:
        """All stored (person_id, embedding, speaking_sec) for the given embedding model."""
        rows = self.connect().execute(
            "SELECT person_id, embedding, speaking_sec FROM recording_speakers WHERE person_id IS NOT NULL AND embedding IS NOT NULL AND embedding_model=?",
            (model,),
        ).fetchall()
        return [(r["person_id"], r["embedding"], r["speaking_sec"] or 0.0) for r in rows]

    def person_appearances(self, pid: int) -> list[dict]:
        rows = self.connect().execute(
            """SELECT r.id AS recording_id, r.title, r.original_name, r.recorded_at, r.duration_sec, rs.label, rs.speaking_sec, rs.similarity
               FROM recording_speakers rs JOIN recordings r ON r.id = rs.recording_id
               WHERE rs.person_id=? ORDER BY r.recorded_at DESC""",
            (pid,),
        ).fetchall()
        return [dict(r) for r in rows]

    def segment_context(self, sid: int, before: int = 1, after: int = 1) -> list[dict]:
        """A segment together with its neighbouring turns in the same recording, in order.

        What a search hit means usually needs the turn before and after it; this is how "Ask" builds a passage.
        """
        c = self.connect()
        row = c.execute("SELECT recording_id, idx FROM segments WHERE id=?", (sid,)).fetchone()
        if not row:
            return []
        rows = c.execute(
            """SELECT s.id, s.idx, s.recording_id, s.speaker_label, s.start, s.end, s.text,
                      COALESCE(p.name, rs.display_name) AS person_name
               FROM segments s
               LEFT JOIN recording_speakers rs ON rs.recording_id = s.recording_id AND rs.label = s.speaker_label
               LEFT JOIN people p ON p.id = rs.person_id
               WHERE s.recording_id=? AND s.idx BETWEEN ? AND ? ORDER BY s.idx""",
            (row["recording_id"], row["idx"] - max(0, before), row["idx"] + max(0, after)),
        ).fetchall()
        return [dict(r) for r in rows]

    # ---- search ----------------------------------------------------------
    def search(self, query: str, limit: int = 100, match: str = "all") -> list[dict]:
        """Full-text search over every turn. `match='all'` needs every term (the Search page);
        `match='any'` ranks whatever matches most of them (a question, where no one word is required)."""
        q = query.strip()
        if not q:
            return []
        # Quote each term so punctuation in user input doesn't break the FTS grammar.
        joiner = " OR " if match == "any" else " "
        terms = joiner.join('"' + t.replace('"', '""') + '"' for t in q.split())
        rows = self.connect().execute(
            """SELECT s.id, s.recording_id, s.speaker_label, s.start, s.end,
                      snippet(segments_fts, 0, '[[', ']]', '…', 14) AS snippet,
                      r.title, r.original_name, r.recorded_at,
                      COALESCE(p.name, rs.display_name) AS person_name, p.color AS person_color
               FROM segments_fts
               JOIN segments s ON s.id = segments_fts.rowid
               JOIN recordings r ON r.id = s.recording_id
               LEFT JOIN recording_speakers rs ON rs.recording_id = s.recording_id AND rs.label = s.speaker_label
               LEFT JOIN people p ON p.id = rs.person_id
               WHERE segments_fts MATCH ?
               ORDER BY bm25(segments_fts) LIMIT ?""",
            (terms, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def source_counts(self) -> dict[str, int]:
        return {r[0] or "dji": r[1] for r in self.connect().execute("SELECT source, COUNT(*) FROM recordings GROUP BY source")}

    def stats(self) -> dict:
        c = self.connect()
        return {
            "recordings": c.execute("SELECT COUNT(*) FROM recordings").fetchone()[0],
            "queued": c.execute("SELECT COUNT(*) FROM recordings WHERE status IN ('queued','processing')").fetchone()[0],
            "people": c.execute("SELECT COUNT(*) FROM people").fetchone()[0],
            "hours": (c.execute("SELECT COALESCE(SUM(duration_sec),0) FROM recordings").fetchone()[0] or 0) / 3600.0,
        }
