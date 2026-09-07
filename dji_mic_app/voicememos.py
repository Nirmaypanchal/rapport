"""Import from Apple Voice Memos on this Mac.

Voice Memos keeps its recordings as .m4a files plus a Core Data SQLite database:

    ~/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings/
        CloudRecordings.db      titles, dates, durations, file names
        <name>.m4a              the audio

macOS guards that folder with Full Disk Access, so reading it fails with
"Operation not permitted" until the user grants access to whatever launched
this server (Terminal, or the Python binary itself).
"""
from __future__ import annotations

import shutil
import sqlite3
import sys
import tempfile
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

RECORDINGS_DIR = Path.home() / "Library" / "Group Containers" / "group.com.apple.VoiceMemos.shared" / "Recordings"
DB_NAME = "CloudRecordings.db"
CORE_DATA_EPOCH = datetime(2001, 1, 1, tzinfo=timezone.utc)


@dataclass
class Memo:
    uid: str
    title: str
    recorded_at: str | None
    duration_sec: float | None
    path: str  # absolute path to the .m4a
    size_bytes: int

    def as_dict(self) -> dict:
        return asdict(self)


class VoiceMemosError(Exception):
    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind  # "not_found" | "permission" | "error"


def python_executable() -> str:
    return str(Path(sys.executable).resolve())


def _core_data_date(v) -> str | None:
    if v is None:
        return None
    try:
        dt = CORE_DATA_EPOCH + timedelta(seconds=float(v))
        return dt.astimezone().isoformat(timespec="seconds")
    except (TypeError, ValueError, OverflowError):
        return None


def list_memos() -> list[Memo]:
    """All memos whose audio is present on this Mac. Raises VoiceMemosError."""
    if not RECORDINGS_DIR.parent.exists():
        raise VoiceMemosError("not_found", "Voice Memos has no recordings folder on this Mac.")
    db = RECORDINGS_DIR / DB_NAME
    try:
        list(RECORDINGS_DIR.iterdir())
    except PermissionError as e:
        raise VoiceMemosError("permission", str(e)) from e
    except FileNotFoundError:
        raise VoiceMemosError("not_found", "Voice Memos has no recordings folder on this Mac.")
    if not db.exists():
        raise VoiceMemosError("not_found", "Voice Memos database not found.")

    # Copy the database first: Voice Memos keeps it open, and a copy avoids lock issues and WAL surprises.
    with tempfile.TemporaryDirectory() as tmp:
        tmp_db = Path(tmp) / DB_NAME
        shutil.copyfile(db, tmp_db)
        for suffix in ("-wal", "-shm"):
            side = db.with_name(DB_NAME + suffix)
            if side.exists():
                shutil.copyfile(side, tmp_db.with_name(DB_NAME + suffix))
        conn = sqlite3.connect(f"file:{tmp_db}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(ZCLOUDRECORDING)")}
            if "ZPATH" not in cols:
                raise VoiceMemosError("error", "Unexpected Voice Memos database layout.")
            title_col = "ZENCRYPTEDTITLE" if "ZENCRYPTEDTITLE" in cols else ("ZCUSTOMLABEL" if "ZCUSTOMLABEL" in cols else "NULL")
            label_col = "ZCUSTOMLABEL" if "ZCUSTOMLABEL" in cols else "NULL"
            uid_col = "ZUNIQUEID" if "ZUNIQUEID" in cols else "Z_PK"
            rows = conn.execute(
                f"SELECT Z_PK, {uid_col} AS uid, {title_col} AS title, {label_col} AS label, ZDATE, ZDURATION, ZPATH FROM ZCLOUDRECORDING WHERE ZPATH IS NOT NULL ORDER BY ZDATE DESC"
            ).fetchall()
        finally:
            conn.close()

    memos: list[Memo] = []
    for r in rows:
        p = Path(r["ZPATH"])
        if not p.is_absolute():
            p = RECORDINGS_DIR / p
        if not p.exists():  # evicted to iCloud, or a stale row
            continue
        title = (r["title"] or r["label"] or p.stem).strip()
        memos.append(
            Memo(
                uid=str(r["uid"] or r["Z_PK"]),
                title=title,
                recorded_at=_core_data_date(r["ZDATE"]),
                duration_sec=float(r["ZDURATION"]) if r["ZDURATION"] is not None else None,
                path=str(p),
                size_bytes=p.stat().st_size,
            )
        )
    return memos
