"""Watches /Volumes for DJI transmitters, copies new recordings into the library,
verifies the copy byte-for-byte, then (optionally) deletes the file from the mic."""
from __future__ import annotations

import os
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path

from .audio import probe, sha256_file
from .config import Library
from .db import Database, now_iso
from .dji import AUDIO_EXT, MicVolume, find_mic_volumes, parse_name, list_removable_volumes, audio_files


class Importer:
    def __init__(self, library: Library, db: Database):
        self.library = library
        self.db = db
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None
        self.lock = threading.Lock()
        self.state: dict = {"volumes": [], "importing": None, "last_scan": None, "last_error": None}

    # ---- lifecycle ---------------------------------------------------------
    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="importer", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()

    def scan_now(self) -> None:
        self._wake.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.scan()
            except Exception as e:  # never let the watcher die
                self.state["last_error"] = str(e)
                self.db.log(f"Import scan failed: {e}", "error")
            self._wake.wait(timeout=max(1.0, self.library.settings.poll_interval_sec))
            self._wake.clear()

    # ---- scanning ----------------------------------------------------------
    def scan(self) -> int:
        settings = self.library.settings
        vols = find_mic_volumes(settings.extra_volume_names)
        self.state["volumes"] = [
            {"mount": str(v.mount), "name": v.volume_name, "media": v.media_name, "files": len(v.files)} for v in vols
        ]
        self.state["last_scan"] = datetime.now().astimezone().isoformat(timespec="seconds")
        # Other removable drives the user opted into, and watched folders. Never deleted from.
        try:
            for vol in list_removable_volumes():
                if vol["name"] in settings.usb_volumes and not vol["is_dji"]:
                    for f in audio_files(Path(vol["mount"])):
                        try:
                            self.import_file(f, source_volume=vol["name"], delete_source=False, source="usb")
                        except Exception as e:
                            self.db.log(f"Failed to import {f.name}: {e}", "error")
            for folder in settings.watched_folders:
                fp = Path(folder).expanduser()
                if fp.is_dir():
                    for f in audio_files(fp):
                        try:
                            self.import_file(f, source_volume=str(fp), delete_source=False, source="folder")
                        except Exception as e:
                            self.db.log(f"Failed to import {f.name}: {e}", "error")
        except Exception as e:
            self.state["last_error"] = str(e)
        self._sync_connectors_if_due()
        if getattr(settings, "auto_import_voice_memos", False):
            try:
                self.import_voice_memos()
            except Exception as e:
                self.state["voice_memos_error"] = str(e)
        if not settings.auto_import:
            return 0
        imported = 0
        for v in vols:
            for f in v.files:
                if self._stop.is_set():
                    return imported
                try:
                    if self.import_file(f, source_volume=v.volume_name, delete_source=settings.delete_from_device_after_import):
                        imported += 1
                except Exception as e:
                    self.db.log(f"Failed to import {f.name}: {e}", "error")
        return imported

    # ---- transcript-only items from other apps ------------------------------
    def import_transcript(self, item: dict, source: str) -> int | None:
        """Store a transcript that has no audio (Granola, Omi, Notion…). Returns the recording id or None if known."""
        uid = str(item["uid"])
        if self.db.has_source_id(source, uid):
            return None
        segs_in = [x for x in item.get("segments") or [] if (x.get("text") or "").strip()]
        if not segs_in:
            return None
        # Timing: keep real timestamps when the source has them, otherwise pace at ~2.6 words/second.
        t = 0.0
        segments: list[dict] = []
        labels: dict[str, str] = {}
        speaking: dict[str, float] = {}
        for x in segs_in:
            words = x["text"].split()
            start = float(x["start"]) if x.get("start") is not None else t
            end = float(x["end"]) if x.get("end") is not None else start + max(0.6, len(words) / 2.6)
            if end <= start:
                end = start + max(0.6, len(words) / 2.6)
            step = (end - start) / max(1, len(words))
            wl = [[w, round(start + i * step, 2), round(start + (i + 1) * step, 2)] for i, w in enumerate(words)]
            name = str(x.get("speaker") or "Speaker")
            label = labels.setdefault(name, f"SPEAKER_{len(labels):02d}")
            speaking[label] = speaking.get(label, 0.0) + (end - start)
            segments.append({"speaker": label, "start": round(start, 2), "end": round(end, 2), "text": " ".join(words), "words": wl})
            t = end + 0.3
        duration = item.get("duration_sec") or (segments[-1]["end"] if segments else 0)
        rid = self.db.insert_recording(
            sha256=f"{source}:{uid}", original_name=f"{item.get('title') or source}.txt", rel_path="", has_audio=0,
            transmitter=None, file_index=None, recorded_at=item.get("recorded_at"), duration_sec=duration,
            sample_rate=None, channels=None, size_bytes=0, source_volume=source, source_path=None,
            status="done", title=item.get("title"), source=source, source_id=uid, diarizer=source, processed_at=now_iso(),
            summary=item.get("summary"), summary_model=source if item.get("summary") else None,
            summary_at=now_iso() if item.get("summary") else None, summary_status="done" if item.get("summary") else None,
        )
        self.db.replace_segments(rid, segments)
        self.db.replace_speakers(rid, [{"label": lab, "display_name": name, "speaking_sec": round(speaking.get(lab, 0), 2)} for name, lab in labels.items()])
        self.db.log(f"Imported \"{item.get('title') or uid}\" from {source.capitalize()} ({len(segments)} turns)")
        return rid

    def sync_connector(self, name: str) -> list[int]:
        """Pull new items from one integration. Raises on failure; records last sync/error either way."""
        from . import connectors

        s = self.library.settings
        known = self.db.source_ids(name)
        try:
            if name == "granola":
                if not s.granola_api_key:
                    raise RuntimeError("no API key")
                items = connectors.granola_items(s.granola_api_key, known)
            elif name == "omi":
                if not s.omi_api_key:
                    raise RuntimeError("no API key")
                items = connectors.omi_items(s.omi_api_key, known)
            elif name == "notion":
                if not s.notion_token:
                    raise RuntimeError("no integration token")
                items = connectors.notion_items(s.notion_token, s.notion_database_id or None, known)
            else:
                raise RuntimeError(f"unknown connector {name}")
            ids = [rid for it in items if (rid := self.import_transcript(it, name))]
            self.library.state_update(name, last_sync=now_iso(), last_error=None, last_count=len(ids))
            self.on_transcripts_imported(ids)
            return ids
        except Exception as e:
            self.library.state_update(name, last_sync=now_iso(), last_error=str(e)[:300])
            raise

    on_transcripts_imported = staticmethod(lambda ids: None)  # set by main() so new items get summarized

    def _sync_connectors_if_due(self) -> None:
        s = self.library.settings
        st = self.library.state_get()
        now = time.time()
        for name, key, auto in (("granola", s.granola_api_key, s.granola_auto), ("omi", s.omi_api_key, s.omi_auto), ("notion", s.notion_token, s.notion_auto)):
            if not key or not auto:
                continue
            last = st.get(name, {}).get("last_sync")
            try:
                due = not last or (now - datetime.fromisoformat(last).timestamp()) >= s.sync_interval_sec
            except Exception:
                due = True
            if due:
                try:
                    self.sync_connector(name)
                except Exception as e:
                    self.db.log(f"{name.capitalize()} sync failed: {e}", "warn")

    # ---- Apple Voice Memos -------------------------------------------------
    def voice_memos(self) -> dict:
        """Memos on this Mac with an `imported` flag, or the reason they cannot be read."""
        from .voicememos import VoiceMemosError, list_memos, python_executable

        try:
            memos = list_memos()
        except VoiceMemosError as e:
            return {"available": False, "reason": e.kind, "message": str(e), "python": python_executable(), "memos": []}
        out = []
        for m in memos:
            d = m.as_dict()
            d["imported"] = self.db.has_source_id("voicememos", m.uid)
            out.append(d)
        return {"available": True, "reason": None, "message": None, "python": python_executable(), "memos": out}

    def import_voice_memos(self, uids: list[str] | None = None) -> list[int]:
        """Copy memos into the library (never touching Voice Memos). Returns new recording ids."""
        from .voicememos import list_memos

        ids: list[int] = []
        for m in list_memos():
            if uids is not None and m.uid not in uids:
                continue
            if self.db.has_source_id("voicememos", m.uid):
                continue
            safe = "".join(ch if ch.isalnum() or ch in " -_.()" else "_" for ch in m.title).strip() or "Voice Memo"
            rec_at = datetime.fromisoformat(m.recorded_at) if m.recorded_at else None
            rid = self.import_file(
                Path(m.path), source_volume="Voice Memos", delete_source=False,
                source="voicememos", source_id=m.uid, title=m.title,
                recorded_at=rec_at, original_name=f"{safe}{Path(m.path).suffix}", min_age=0,
            )
            if rid:
                ids.append(rid)
        return ids

    # ---- single file -------------------------------------------------------
    def import_file(
        self,
        src: Path,
        source_volume: str | None = None,
        delete_source: bool = False,
        *,
        source: str = "dji",
        source_id: str | None = None,
        title: str | None = None,
        recorded_at: datetime | None = None,
        original_name: str | None = None,
        min_age: float | None = None,
    ) -> int | None:
        """Copy one audio file into the library. Returns the new recording id, or None if skipped."""
        src = Path(src)
        if src.suffix.lower() not in AUDIO_EXT or not src.is_file():
            return None
        st = src.stat()
        if st.st_size == 0:
            return None
        age = self.library.settings.min_file_age_sec if min_age is None else min_age
        if time.time() - st.st_mtime < age:
            return None  # still being written
        with self.lock:
            self.state["importing"] = original_name or src.name
            try:
                return self._import_locked(src, st, source_volume, delete_source, source, source_id, title, recorded_at, original_name)
            finally:
                self.state["importing"] = None

    def _import_locked(
        self, src: Path, st: os.stat_result, source_volume: str | None, delete_source: bool,
        source: str = "dji", source_id: str | None = None, title: str | None = None,
        recorded_at_override: datetime | None = None, original_name: str | None = None,
    ) -> int | None:
        sha = sha256_file(src)
        if self.db.has_sha(sha):
            if delete_source and self._inside_volume(src):
                # Already safely in the library (e.g. a previous run copied it but the delete failed).
                self._delete_source(src)
            return None

        parsed = parse_name(src.name)
        recorded_at = recorded_at_override or parsed.recorded_at or datetime.fromtimestamp(st.st_mtime)
        day_dir = self.library.audio_dir / f"{recorded_at:%Y}" / f"{recorded_at:%Y-%m-%d}"
        day_dir.mkdir(parents=True, exist_ok=True)
        name = original_name or src.name
        dst = day_dir / name
        n = 1
        while dst.exists():
            dst = day_dir / f"{Path(name).stem}_{n}{Path(name).suffix}"
            n += 1

        tmp = dst.with_suffix(dst.suffix + ".part")
        shutil.copyfile(src, tmp)
        if sha256_file(tmp) != sha:
            tmp.unlink(missing_ok=True)
            raise IOError("copy verification failed (hash mismatch)")
        os.replace(tmp, dst)
        try:
            os.utime(dst, (st.st_atime, st.st_mtime))
        except OSError:
            pass

        try:
            meta = probe(dst)
        except Exception:
            meta = {"duration_sec": None, "size_bytes": st.st_size, "sample_rate": None, "channels": None}

        rid = self.db.insert_recording(
            sha256=sha,
            original_name=name,
            source=source,
            source_id=source_id,
            rel_path=str(dst.relative_to(self.library.root)),
            transmitter=parsed.transmitter,
            file_index=parsed.file_index,
            recorded_at=recorded_at.replace(tzinfo=None).isoformat(timespec="seconds") if recorded_at.tzinfo else recorded_at.isoformat(timespec="seconds"),
            duration_sec=meta.get("duration_sec"),
            sample_rate=meta.get("sample_rate"),
            channels=meta.get("channels"),
            size_bytes=meta.get("size_bytes") or st.st_size,
            source_volume=source_volume,
            source_path=str(src),
            status="queued",
            title=title,
        )
        self.db.log(f"Imported {name} ({(st.st_size / 1e6):.1f} MB) from {source_volume or src.parent}")

        if delete_source and self._inside_volume(src):
            self._delete_source(src, rid)
        return rid

    def _inside_volume(self, p: Path) -> bool:
        return str(p).startswith("/Volumes/")

    def _delete_source(self, src: Path, rid: int | None = None) -> None:
        try:
            src.unlink()
            if rid is not None:
                self.db.update_recording(rid, deleted_from_device=1)
            self.db.log(f"Removed {src.name} from the mic to free space")
            # Remove now-empty DJI session folder so the mic stays tidy.
            parent = src.parent
            if parent.parent.parent == Path("/Volumes") and not any(p for p in parent.iterdir() if not p.name.startswith(".")):
                try:
                    for junk in parent.iterdir():
                        junk.unlink()
                    parent.rmdir()
                except OSError:
                    pass
        except OSError as e:
            self.db.log(f"Could not delete {src.name} from the mic: {e}", "warn")
