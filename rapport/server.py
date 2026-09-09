"""HTTP API + static UI."""
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import Library
from .db import Database
from .importer import Importer
from .speakers import next_color
from .dji import AUDIO_EXT

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
NEXT_DIR = Path(os.environ.get("RAPPORT_UI_DIR") or (Path(__file__).resolve().parent.parent / "frontend" / "out"))  # `npm run build` output; the desktop shell points RAPPORT_UI_DIR at its bundled copy


class SettingsPatch(BaseModel):
    patch: dict


class ImportPath(BaseModel):
    path: str


class RecordingPatch(BaseModel):
    title: str | None = None
    notes: str | None = None


class Assign(BaseModel):
    person_id: int | None = None
    new_name: str | None = None


class SegmentPatch(BaseModel):
    speaker_label: str | None = None   # an existing label in this recording
    person_id: int | None = None       # or any person (a speaker row is created if needed)
    new_person: str | None = None      # or a brand-new person by name
    text: str | None = None


class SplitBody(BaseModel):
    word_index: int


class SystemOpen(BaseModel):
    target: str


class RecordStart(BaseModel):
    device: str


class VoiceMemoImport(BaseModel):
    uids: list[str] | None = None


class ExportBody(BaseModel):
    kind: str


class PeopleReset(BaseModel):
    mode: str = "rematch"


class PersonPatch(BaseModel):
    name: str | None = None
    note: str | None = None
    color: str | None = None


def create_app(library: Library, db: Database, importer: Importer, worker, recorder, token: str | None = None) -> FastAPI:
    app = FastAPI(title="DJI Mic Library")
    # The Next.js dev server (localhost:3000) talks to this API directly; the exported build is same-origin.
    from fastapi.middleware.cors import CORSMiddleware

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "tauri://localhost", "http://tauri.localhost"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health():
        return {"ok": True}

    if token:
        from starlette.responses import JSONResponse as _JR

        @app.middleware("http")
        async def require_token(request, call_next):
            if request.url.path.startswith("/api/") and request.url.path != "/api/health":
                auth = request.headers.get("authorization", "")
                supplied = auth[7:] if auth.lower().startswith("bearer ") else request.query_params.get("token", "")
                if supplied != token:
                    return _JR({"detail": "unauthorized"}, status_code=401)
            return await call_next(request)

    # ---- status ------------------------------------------------------------
    @app.get("/api/status")
    def status():
        return {
            "library": str(library.root),
            "importer": importer.state,
            "worker": worker.status(),
            "stats": db.stats(),
            "settings": _public_settings(),
            "hf_token_present": library.hf_token() is not None,
            "recording": recorder.status(),
        }

    def _public_settings():
        s = library.settings.to_json()
        for k in ("hf_token", "granola_api_key", "omi_api_key", "notion_token"):
            s[k] = "•••" if s.get(k) else ""
        return s

    @app.get("/api/log")
    def get_log(limit: int = 100):
        return db.recent_log(limit)

    # ---- settings ----------------------------------------------------------

    @app.put("/api/settings")
    def put_settings(body: SettingsPatch):
        patch = dict(body.patch)
        for k in ("hf_token", "granola_api_key", "omi_api_key", "notion_token"):
            if patch.get(k) == "•••":
                patch.pop(k)
        before = library.settings.to_json()
        library.update_settings(patch)
        after = library.settings.to_json()
        if any(before.get(k) != after.get(k) for k in ("hf_token", "diarizer")):
            worker.models.reset_pyannote()
        importer.scan_now()
        return _public_settings()

    # ---- import ------------------------------------------------------------
    @app.post("/api/import/scan")
    def scan():
        importer.scan_now()
        return {"ok": True}


    @app.post("/api/import/path")
    def import_path(body: ImportPath):
        p = Path(body.path).expanduser()
        if not p.exists():
            raise HTTPException(404, f"{p} does not exist")
        files = [p] if p.is_file() else sorted(x for x in p.rglob("*") if x.is_file())
        ids = []
        old_age = library.settings.min_file_age_sec
        library.settings.min_file_age_sec = 0
        try:
            for f in files:
                try:
                    rid = importer.import_file(f, source_volume=str(p), delete_source=False)
                    if rid:
                        ids.append(rid)
                except Exception as e:
                    db.log(f"Failed to import {f.name}: {e}", "error")
        finally:
            library.settings.min_file_age_sec = old_age
        worker.wake()
        return {"imported": ids}

    # ---- Brand icons from apps installed on this Mac, system helpers -----------
    BRAND_APPS = {
        "voicememos": ["/System/Applications/VoiceMemos.app"],
        "granola": ["/Applications/Granola.app", str(Path.home() / "Applications/Granola.app")],
        "notion": ["/Applications/Notion.app", str(Path.home() / "Applications/Notion.app")],
        "omi": ["/Applications/Omi.app", str(Path.home() / "Applications/Omi.app")],
        "ollama": ["/Applications/Ollama.app"],
    }

    @app.get("/api/brand/{key}.png")
    def brand_icon(key: str):
        import plistlib
        import subprocess

        if key not in BRAND_APPS:
            raise HTTPException(404)
        out = library.cache_dir / "_brands" / f"{key}.png"
        if not out.exists():
            for app_path in BRAND_APPS[key]:
                info = Path(app_path) / "Contents" / "Info.plist"
                if not info.exists():
                    continue
                try:
                    icon = plistlib.loads(info.read_bytes()).get("CFBundleIconFile") or "AppIcon"
                except Exception:
                    icon = "AppIcon"
                if not icon.endswith(".icns"):
                    icon += ".icns"
                icns = Path(app_path) / "Contents" / "Resources" / icon
                if not icns.exists():
                    continue
                out.parent.mkdir(parents=True, exist_ok=True)
                subprocess.run(["sips", "-s", "format", "png", "-Z", "256", str(icns), "--out", str(out)], capture_output=True, timeout=20)
                break
        if not out.exists():
            raise HTTPException(404)
        return FileResponse(out, media_type="image/png", headers={"Cache-Control": "max-age=86400"})

    @app.post("/api/system/open")
    def system_open(body: SystemOpen):
        """Open the right System Settings pane, or reveal a file in Finder. Nothing is changed on the user's behalf."""
        import subprocess
        from .voicememos import python_executable

        targets = {
            "fulldisk": ["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles"],
            "microphone": ["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone"],
            "bluetooth": ["open", "x-apple.systempreferences:com.apple.BluetoothSettings"],
            "reveal-app": ["open", "-R", os.environ.get("RAPPORT_APP_PATH") or python_executable()],
            "reveal-python": ["open", "-R", os.environ.get("RAPPORT_APP_PATH") or python_executable()],
            "voicememos-app": ["open", "-a", "Voice Memos"],
        }
        if body.target.startswith("url:"):
            url = body.target[4:]
            if not url.startswith(("http://", "https://")):
                raise HTTPException(400, "only http(s) links")
            cmd = ["open", url]
        elif body.target.startswith("reveal:"):
            p = Path(body.target[7:]).expanduser()
            if not p.exists():
                raise HTTPException(404, "path not found")
            cmd = ["open", "-R" if p.is_file() else "", str(p)]
            cmd = [c for c in cmd if c]
        elif body.target in targets:
            cmd = targets[body.target]
        else:
            raise HTTPException(400, "unknown target")
        subprocess.run(cmd, capture_output=True, timeout=10)
        return {"ok": True}

    @app.get("/api/fs/roots")
    def fs_roots():
        """Cloud-synced folders present on this Mac, for one-click watching."""
        home = Path.home()
        cands = [
            ("icloud", "iCloud Drive", home / "Library/Mobile Documents/com~apple~CloudDocs"),
            ("dropbox", "Dropbox", home / "Library/CloudStorage/Dropbox"),
            ("dropbox", "Dropbox", home / "Dropbox"),
            ("onedrive", "OneDrive", home / "Library/CloudStorage/OneDrive-Personal"),
            ("downloads", "Downloads", home / "Downloads"),
            ("desktop", "Desktop", home / "Desktop"),
        ]
        for g in sorted((home / "Library/CloudStorage").glob("GoogleDrive-*")):
            cands.insert(3, ("googledrive", "Google Drive", g / "My Drive"))
        seen: set[str] = set()
        out = []
        for key, label, p in cands:
            if p.is_dir() and key not in seen:
                seen.add(key)
                out.append({"key": key, "label": label, "path": str(p)})
        return out

    @app.get("/api/fs/list")
    def fs_list(path: str):
        p = Path(path).expanduser()
        if not p.is_dir():
            raise HTTPException(404, "not a folder")
        dirs, audio = [], 0
        try:
            for child in sorted(p.iterdir(), key=lambda c: c.name.lower()):
                if child.name.startswith("."):
                    continue
                if child.is_dir():
                    dirs.append({"name": child.name, "path": str(child)})
                elif child.suffix.lower() in AUDIO_EXT:
                    audio += 1
        except PermissionError:
            raise HTTPException(403, "macOS is blocking this folder")
        return {"path": str(p), "parent": str(p.parent) if p.parent != p else None, "dirs": dirs[:200], "audio_files": audio}

    # ---- Sources: devices & integrations ------------------------------------
    @app.get("/api/sources")
    def sources():
        from .dji import list_removable_volumes
        from .recorder import list_inputs

        s = library.settings
        st = library.state_get()
        vm = importer.voice_memos()
        vm.pop("memos", None)
        return {
            "volumes": [{**v, "enabled": v["is_dji"] or v["name"] in s.usb_volumes} for v in list_removable_volumes()],
            "microphones": list_inputs(),
            "recording": recorder.status(),
            "recording_error": recorder.last_error,
            "voice_memos": vm,
            "watched_folders": s.watched_folders,
            "connectors": {
                name: {"configured": bool(key), "auto": auto, **st.get(name, {})}
                for name, key, auto in (("granola", s.granola_api_key, s.granola_auto), ("omi", s.omi_api_key, s.omi_auto), ("notion", s.notion_token, s.notion_auto))
            },
            "counts": db.source_counts(),
        }

    @app.post("/api/sources/{name}/sync")
    def sync_source(name: str):
        if name == "voicememos":
            ids = importer.import_voice_memos()
            worker.wake()
            return {"imported": ids}
        try:
            ids = importer.sync_connector(name)
        except Exception as e:
            raise HTTPException(400, str(e))
        return {"imported": ids}

    @app.post("/api/record/start")
    def record_start(body: RecordStart):
        try:
            return recorder.start(body.device)
        except Exception as e:
            raise HTTPException(400, str(e))

    @app.post("/api/record/stop")
    def record_stop():
        path = recorder.stop()
        if not path:
            raise HTTPException(400, "nothing was recorded")
        from datetime import datetime as _dt

        rid = importer.import_file(path, source_volume="microphone", delete_source=False, source="microphone", title=f"Recording {_dt.now():%-d %b, %H:%M}", min_age=0)
        try:
            path.unlink()
        except OSError:
            pass
        worker.wake()
        return {"imported": rid}

    # ---- Apple Voice Memos -------------------------------------------------
    @app.get("/api/voicememos")
    def voicememos():
        """Listing doubles as the access probe: a denied read is what makes macOS list the app under Full Disk Access."""
        d = importer.voice_memos()
        d["app_name"] = os.environ.get("RAPPORT_APP_NAME") or "this app"
        d["app_path"] = os.environ.get("RAPPORT_APP_PATH")
        d["in_app"] = bool(os.environ.get("RAPPORT_APP_PATH"))
        return d

    @app.post("/api/voicememos/import")
    def voicememos_import(body: VoiceMemoImport):
        try:
            ids = importer.import_voice_memos(body.uids)
        except Exception as e:
            raise HTTPException(400, str(e))
        worker.wake()
        return {"imported": ids}

    # ---- upload / drag-and-drop --------------------------------------------
    @app.post("/api/import/upload")
    async def import_upload(files: list[UploadFile]):
        import tempfile

        ids: list[int] = []
        skipped: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            for f in files:
                name = Path(f.filename or "upload").name
                dst = Path(tmp) / name
                with open(dst, "wb") as out:
                    while True:
                        chunk = await f.read(4 * 1024 * 1024)
                        if not chunk:
                            break
                        out.write(chunk)
                try:
                    rid = importer.import_file(dst, source_volume="upload", delete_source=False, source="file", min_age=0)
                    if rid:
                        ids.append(rid)
                    else:
                        skipped.append(name)
                except Exception as e:
                    db.log(f"Failed to import {name}: {e}", "error")
                    skipped.append(name)
        worker.wake()
        return {"imported": ids, "skipped": skipped}

    # ---- recordings --------------------------------------------------------
    _mini_cache: dict[int, list[float]] = {}

    def _mini_peaks(rid: int, n: int = 28) -> list[float]:
        if rid in _mini_cache:
            return _mini_cache[rid]
        f = library.cache_dir / str(rid) / "peaks.json"
        if not f.exists():
            return []
        peaks = json.loads(f.read_text())
        if not peaks:
            return []
        step = len(peaks) / n
        out = [round(max(peaks[int(i * step):max(int(i * step) + 1, int((i + 1) * step))] or [0]), 3) for i in range(n)]
        _mini_cache[rid] = out
        return out

    @app.get("/api/recordings")
    def recordings():
        recs = db.list_recordings()
        spk = db.speakers_for_recordings()
        for r in recs:
            r["speakers"] = spk.get(r["id"], [])
            r["peaks_mini"] = _mini_peaks(r["id"]) if r["status"] == "done" else []
        return recs

    @app.get("/api/recordings/{rid}")
    def recording(rid: int):
        r = db.get_recording(rid)
        if not r:
            raise HTTPException(404)
        r["speakers"] = db.get_speakers(rid)
        r["segments"] = db.get_segments(rid)
        peaks = library.recording_cache(rid) / "peaks.json"
        r["peaks"] = json.loads(peaks.read_text()) if peaks.exists() else []
        return r


    @app.patch("/api/recordings/{rid}")
    def patch_recording(rid: int, body: RecordingPatch):
        cols = {k: v for k, v in body.model_dump().items() if v is not None}
        db.update_recording(rid, **cols)
        return db.get_recording(rid)

    @app.post("/api/recordings/{rid}/summarize")
    def summarize_recording(rid: int):
        r = db.get_recording(rid)
        if not r:
            raise HTTPException(404)
        if r["status"] != "done":
            raise HTTPException(409, "recording is not processed yet")
        if not worker.summarize_later(rid):
            raise HTTPException(503, "No local model available. Start Ollama, or choose the MLX model in Settings.")
        return {"ok": True}

    @app.get("/api/summary/providers")
    def summary_providers():
        from .summarize import MLX_DEFAULT, ollama_models, resolve_provider

        s = library.settings
        active = resolve_provider(s.summary_provider, s.summary_model or None)
        return {"ollama": ollama_models(), "mlx_default": MLX_DEFAULT, "active": {"provider": active[0], "model": active[1]} if active else None}

    @app.post("/api/recordings/{rid}/reprocess")
    def reprocess(rid: int):
        if not db.get_recording(rid):
            raise HTTPException(404)
        db.update_recording(rid, status="queued", error=None, stage=None)
        _mini_cache.pop(rid, None)
        worker.wake()
        return {"ok": True}

    @app.delete("/api/recordings/{rid}")
    def delete_recording(rid: int):
        r = db.get_recording(rid)
        if not r:
            raise HTTPException(404)
        db.delete_recording(rid)
        # Auto-named people who no longer appear anywhere go too; named people are kept.
        for p in db.list_people():
            if p["auto"] and p["appearances"] == 0:
                db.delete_person(p["id"])
        # Only the database entry and cache are removed; the original audio stays in the library folder.
        import shutil
        shutil.rmtree(library.cache_dir / str(rid), ignore_errors=True)
        return {"ok": True}

    @app.get("/api/recordings/{rid}/audio")
    def audio(rid: int):
        p = library.cache_dir / str(rid) / "playback.m4a"
        if p.exists():
            return FileResponse(p, media_type="audio/mp4")
        r = db.get_recording(rid)
        if not r:
            raise HTTPException(404)
        return FileResponse(library.root / r["rel_path"])

    @app.get("/api/recordings/{rid}/original")
    def original(rid: int):
        r = db.get_recording(rid)
        if not r:
            raise HTTPException(404)
        return FileResponse(library.root / r["rel_path"], filename=r["original_name"])

    @app.get("/api/recordings/{rid}/speech")
    def speech(rid: int):
        r = db.get_recording(rid)
        if not r:
            raise HTTPException(404)
        cache = library.recording_cache(rid)
        if not (cache / "audio16k.wav").exists():
            raise HTTPException(409, "recording not processed yet")
        return {"duration": r["duration_sec"], "regions": worker_models_speech(cache)}

    @app.get("/api/recordings/{rid}/condensed")
    def condensed(rid: int, min_gap: float = 0.7, pad: float = 0.15):
        from .audio import condense_regions, export_condensed

        r = db.get_recording(rid)
        if not r:
            raise HTTPException(404)
        cache = library.recording_cache(rid)
        if not (cache / "audio16k.wav").exists():
            raise HTTPException(409, "recording not processed yet")
        keep = condense_regions(worker_models_speech(cache), r["duration_sec"] or 0, min_gap, pad)
        dst = cache / f"condensed_{min_gap:g}_{pad:g}.m4a"
        try:
            export_condensed(library.root / r["rel_path"], dst, keep)
        except ValueError as e:
            raise HTTPException(400, str(e))
        base = Path(r["original_name"]).stem
        return FileResponse(dst, media_type="audio/mp4", filename=f"{base}_condensed.m4a")

    @app.post("/api/recordings/{rid}/export")
    def export_recording(rid: int, body: ExportBody):
        """Write an export to ~/Downloads/Rapport and reveal it in Finder (downloads don't work inside the desktop WebView)."""
        import shutil
        import subprocess

        r = db.get_recording(rid)
        if not r:
            raise HTTPException(404)
        out_dir = Path.home() / "Downloads" / "Rapport"
        out_dir.mkdir(parents=True, exist_ok=True)
        base = "".join(ch if ch.isalnum() or ch in " -_()" else "_" for ch in (r.get("title") or Path(r["original_name"]).stem)).strip() or f"recording-{rid}"
        if body.kind == "transcript":
            names = {sp["label"]: (sp["person_name"] or sp.get("display_name") or sp["label"]) for sp in db.get_speakers(rid)}
            lines = [f"# {r.get('title') or r['original_name']}  ({r.get('recorded_at')})", ""]
            for seg in db.get_segments(rid):
                m, sec = divmod(int(seg["start"]), 60)
                lines.append(f"[{m:02d}:{sec:02d}] {names.get(seg['speaker_label'], seg['speaker_label'])}: {seg['text']}")
            dst = out_dir / f"{base}.txt"
            dst.write_text("\n".join(lines) + "\n")
        elif body.kind == "original":
            if not r.get("rel_path"):
                raise HTTPException(400, "this recording has no audio")
            src = library.root / r["rel_path"]
            dst = out_dir / f"{base}{src.suffix}"
            shutil.copyfile(src, dst)
        elif body.kind == "condensed":
            from .audio import condense_regions, export_condensed

            if not r.get("rel_path"):
                raise HTTPException(400, "this recording has no audio")
            cache = library.recording_cache(rid)
            s_ = library.settings
            keep = condense_regions(worker_models_speech(cache), r["duration_sec"] or 0, s_.skip_silence_min_gap, s_.skip_silence_pad)
            tmp = cache / f"condensed_{s_.skip_silence_min_gap:g}_{s_.skip_silence_pad:g}.m4a"
            export_condensed(library.root / r["rel_path"], tmp, keep)
            dst = out_dir / f"{base} (condensed).m4a"
            shutil.copyfile(tmp, dst)
        else:
            raise HTTPException(400, "unknown export kind")
        subprocess.run(["open", "-R", str(dst)], capture_output=True, timeout=10)
        return {"path": str(dst)}

    def worker_models_speech(cache: Path):
        """Speech map without the worker: compute here if the cache lacks it (VAD is small)."""
        f = cache / "speech.json"
        if f.exists():
            return [tuple(x) for x in json.loads(f.read_text())]
        from .audio import load_wav16k
        from .diarize import load_vad, speech_regions

        regions = speech_regions(load_wav16k(cache / "audio16k.wav"), load_vad())
        f.write_text(json.dumps([[round(a, 3), round(b, 3)] for a, b in regions]))
        return regions

    @app.get("/api/recordings/{rid}/transcript.txt")
    def transcript_txt(rid: int):
        r = db.get_recording(rid)
        if not r:
            raise HTTPException(404)
        names = {s["label"]: (s["person_name"] or s.get("display_name") or s["label"]) for s in db.get_speakers(rid)}
        lines = [f"# {r.get('title') or r['original_name']}  ({r.get('recorded_at')})", ""]
        for s in db.get_segments(rid):
            m, sec = divmod(int(s["start"]), 60)
            lines.append(f"[{m:02d}:{sec:02d}] {names.get(s['speaker_label'], s['speaker_label'])}: {s['text']}")
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse("\n".join(lines) + "\n")

    # ---- speakers / people -------------------------------------------------

    @app.post("/api/recordings/{rid}/speakers/{label}/assign")
    def assign_speaker(rid: int, label: str, body: Assign):
        pid = body.person_id
        if body.new_name and body.new_name.strip():
            pid = db.create_person(body.new_name.strip(), auto=False, color=next_color(db))
        db.set_speaker_person(rid, label, pid)
        return db.get_speakers(rid)

    # ---- transcript corrections -------------------------------------------
    def _seg_or_404(rid: int, sid: int) -> dict:
        seg = db.get_segment(sid)
        if not seg or seg["recording_id"] != rid:
            raise HTTPException(404)
        return seg

    @app.patch("/api/recordings/{rid}/segments/{sid}")
    def patch_segment(rid: int, sid: int, body: SegmentPatch):
        seg = _seg_or_404(rid, sid)
        cols: dict = {}
        if body.new_person and body.new_person.strip():
            pid = db.create_person(body.new_person.strip(), auto=False, color=next_color(db))
            cols["speaker_label"] = db.ensure_speaker_for_person(rid, pid)
        elif body.person_id is not None:
            if not db.get_person(body.person_id):
                raise HTTPException(404, "person not found")
            cols["speaker_label"] = db.ensure_speaker_for_person(rid, body.person_id)
        elif body.speaker_label:
            if body.speaker_label not in {s["label"] for s in db.get_speakers(rid)}:
                raise HTTPException(400, "unknown speaker label")
            cols["speaker_label"] = body.speaker_label
        if body.text is not None:
            new_words = body.text.split()
            old_words = seg["words"]
            if len(new_words) == len(old_words):
                words = [[w, o[1], o[2]] for w, o in zip(new_words, old_words)]
            else:  # spread the new words evenly over the turn
                n = max(1, len(new_words))
                step = (seg["end"] - seg["start"]) / n
                words = [[w, round(seg["start"] + i * step, 2), round(seg["start"] + (i + 1) * step, 2)] for i, w in enumerate(new_words)]
            cols["text"] = " ".join(new_words)
            cols["words"] = words
        if cols:
            db.update_segment(sid, **cols)
            db.recompute_speaking(rid)
        return _recording_payload(rid)

    @app.post("/api/recordings/{rid}/segments/{sid}/split")
    def split_segment(rid: int, sid: int, body: SplitBody):
        seg = _seg_or_404(rid, sid)
        words = seg["words"]
        i = body.word_index
        if not (0 < i < len(words)):
            raise HTTPException(400, "word_index must be inside the turn")
        left, right = words[:i], words[i:]
        db.update_segment(sid, end=left[-1][2], text=" ".join(w[0] for w in left), words=left)
        db.insert_segment_after(rid, seg["idx"], {"speaker": seg["speaker_label"], "start": right[0][1], "end": seg["end"], "text": " ".join(w[0] for w in right), "words": right})
        return _recording_payload(rid)

    @app.post("/api/recordings/{rid}/segments/{sid}/merge_prev")
    def merge_prev(rid: int, sid: int):
        seg = _seg_or_404(rid, sid)
        segs = db.get_segments(rid)
        pos = next((k for k, s in enumerate(segs) if s["id"] == sid), None)
        if pos is None or pos == 0:
            raise HTTPException(400, "no previous turn")
        prev = segs[pos - 1]
        db.update_segment(prev["id"], end=max(prev["end"], seg["end"]), text=(prev["text"] + " " + seg["text"]).strip(), words=prev["words"] + seg["words"], speaker_label=prev["speaker_label"])
        db.delete_segment(sid)
        db.recompute_speaking(rid)
        return _recording_payload(rid)

    def _recording_payload(rid: int) -> dict:
        r = db.get_recording(rid)
        r["speakers"] = db.get_speakers(rid)
        r["segments"] = db.get_segments(rid)
        return r

    @app.post("/api/people/reset")
    def people_reset(body: PeopleReset):
        """mode=rematch: forget all people, re-match voices from stored fingerprints (seconds).
        mode=reprocess: also re-run transcription and speaker detection on every recording (slow)."""
        from .speakers import rematch_all

        if body.mode == "reprocess":
            db.reset_people()
            n = db.queue_all_audio()
            _mini_cache.clear()
            worker.wake()
            db.log(f"Speaker reset: all people removed, {n} recordings queued for full re-processing")
            return {"mode": "reprocess", "queued": n}
        res = rematch_all(db, library.settings.person_match_threshold)
        db.log(f"Speaker reset: {res['people_removed']} people removed, voices re-matched into {res['people_now']} people")
        return {"mode": "rematch", **res}

    @app.get("/api/people")
    def people():
        return db.list_people()

    @app.get("/api/people/{pid}")
    def person(pid: int):
        p = db.get_person(pid)
        if not p:
            raise HTTPException(404)
        p["appearances"] = db.person_appearances(pid)
        return p


    @app.patch("/api/people/{pid}")
    def patch_person(pid: int, body: PersonPatch):
        cols = {k: v for k, v in body.model_dump().items() if v is not None}
        if "name" in cols:
            cols["name"] = cols["name"].strip() or "Unnamed"
            cols["auto"] = 0
        db.update_person(pid, **cols)
        return db.get_person(pid)

    @app.post("/api/people/{keep}/merge/{remove}")
    def merge(keep: int, remove: int):
        if keep == remove or not db.get_person(keep) or not db.get_person(remove):
            raise HTTPException(400)
        db.merge_people(keep, remove)
        return db.list_people()

    @app.delete("/api/people/{pid}")
    def delete_person(pid: int):
        db.delete_person(pid)
        return {"ok": True}

    # ---- search ------------------------------------------------------------
    @app.get("/api/search")
    def search(q: str = ""):
        try:
            return db.search(q)
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=400)

    # ---- UI ----------------------------------------------------------------
    @app.middleware("http")
    async def no_cache_ui(request, call_next):
        resp = await call_next(request)
        if not request.url.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-cache"
        return resp

    ui_dir = NEXT_DIR if (NEXT_DIR / "index.html").exists() else WEB_DIR
    if ui_dir.exists():
        app.mount("/", StaticFiles(directory=ui_dir, html=True), name="web")
    else:
        @app.get("/")
        def no_ui():
            from fastapi.responses import PlainTextResponse
            return PlainTextResponse("UI not built. Run: cd frontend && npm install && npm run build", status_code=503)
    return app
