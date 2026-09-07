"""Background worker: turns an imported recording into transcript + speakers + people."""
from __future__ import annotations

import json
import logging
import threading
import time
import traceback
from pathlib import Path

import numpy as np

from . import audio as audio_utils
from .config import Library
from .db import Database, now_iso
from .diarize import BuiltinDiarizer, PyannoteDiarizer, Turn, load_vad, speech_regions
from .speakers import Embedder, assign_people, to_blob
from .transcribe import transcribe

log = logging.getLogger(__name__)


class Models:
    """Lazy, cached model handles shared by the worker."""

    def __init__(self, library: Library):
        self.library = library
        self._embedder: Embedder | None = None
        self._pyannote: PyannoteDiarizer | None = None
        self._pyannote_failed: str | None = None
        self._builtin: BuiltinDiarizer | None = None
        self._vad = None
        self.lock = threading.RLock()

    def vad(self):
        with self.lock:
            if self._vad is None:
                self._vad = load_vad()
            return self._vad

    def speech_map(self, cache: Path, samples: np.ndarray | None = None) -> list[tuple[float, float]]:
        """Speech regions for a recording, cached as speech.json next to its other artefacts."""
        f = cache / "speech.json"
        if f.exists():
            return [tuple(x) for x in json.loads(f.read_text())]
        if samples is None:
            samples = audio_utils.load_wav16k(cache / "audio16k.wav")
        regions = speech_regions(samples, self.vad())
        f.write_text(json.dumps([[round(a, 3), round(b, 3)] for a, b in regions]))
        return regions

    def embedder(self) -> Embedder:
        with self.lock:
            if self._embedder is None:
                self._embedder = Embedder(self.library.settings.embedding_model, self.library.hf_token())
            return self._embedder

    def diarizer(self):
        mode = self.library.settings.diarizer
        if mode in ("auto", "pyannote"):
            with self.lock:
                if self._pyannote is None and self._pyannote_failed is None:
                    try:
                        self._pyannote = PyannoteDiarizer(self.library.hf_token())
                    except Exception as e:
                        self._pyannote_failed = str(e).splitlines()[0][:300]
                        log.warning("pyannote unavailable, using builtin diarizer: %s", self._pyannote_failed)
                if self._pyannote is not None:
                    return self._pyannote
            if mode == "pyannote":
                raise RuntimeError(f"pyannote diarizer requested but unavailable: {self._pyannote_failed}")
        s = self.library.settings
        with self.lock:
            if self._builtin is None:
                self._builtin = BuiltinDiarizer(self.embedder(), s.cluster_distance_threshold, s.min_speaker_seconds, vad_model=self.vad())
            else:
                self._builtin.distance_threshold = s.cluster_distance_threshold
                self._builtin.min_speaker_seconds = s.min_speaker_seconds
            return self._builtin

    def reset_pyannote(self) -> None:
        with self.lock:
            self._pyannote = None
            self._pyannote_failed = None

    def status(self) -> dict:
        return {
            "embedder_loaded": self._embedder is not None,
            "pyannote_loaded": self._pyannote is not None,
            "pyannote_error": self._pyannote_failed,
            "builtin_loaded": self._builtin is not None,
        }


def words_to_segments(words: list[dict], turns: list[Turn], max_gap: float = 2.0, max_turn_sec: float = 25.0, max_turn_words: int = 80) -> list[dict]:
    """Attach a speaker to every word, then group consecutive same-speaker words into turns."""
    if not words:
        return []
    turns = sorted(turns, key=lambda t: t.start)
    starts = np.array([t.start for t in turns]) if turns else np.zeros(0)
    ends = np.array([t.end for t in turns]) if turns else np.zeros(0)

    def speaker_for(ws: float, we: float, prev: str | None) -> str:
        if not turns:
            return "SPEAKER_00"
        ov = np.minimum(ends, we) - np.maximum(starts, ws)
        best = int(ov.argmax())
        if ov[best] > 0:
            return turns[best].speaker
        mid = (ws + we) / 2
        dist = np.where(mid < starts, starts - mid, np.where(mid > ends, mid - ends, 0))
        j = int(dist.argmin())
        if dist[j] <= 1.0 or prev is None:
            return turns[j].speaker
        return prev

    segs: list[dict] = []
    prev = None
    for w in words:
        spk = speaker_for(w["start"], w["end"], prev)
        prev = spk
        same = segs and segs[-1]["speaker"] == spk and w["start"] - segs[-1]["end"] <= max_gap
        if same:
            cur = segs[-1]
            long_enough = (w["start"] - cur["start"] > max_turn_sec) or len(cur["words"]) >= max_turn_words
            ends_sentence = cur["words"][-1][0][-1:] in ".?!"
            gap = w["start"] - cur["end"]
            very_long = (w["start"] - cur["start"] > 2 * max_turn_sec) or len(cur["words"]) >= 2 * max_turn_words
            ends_clause = cur["words"][-1][0][-1:] in ",;:"
            if long_enough and (ends_sentence or gap > 0.7):
                same = False
            elif very_long and (ends_clause or gap > 0.3 or len(cur["words"]) >= 3 * max_turn_words):
                same = False
        if same:
            segs[-1]["end"] = max(segs[-1]["end"], w["end"])
            segs[-1]["words"].append([w["word"], round(w["start"], 2), round(w["end"], 2)])
        else:
            segs.append({"speaker": spk, "start": w["start"], "end": w["end"], "words": [[w["word"], round(w["start"], 2), round(w["end"], 2)]]})
    for s in segs:
        s["text"] = " ".join(x[0] for x in s["words"])
        s["start"] = round(s["start"], 2)
        s["end"] = round(s["end"], 2)
    return segs


class Worker:
    def __init__(self, library: Library, db: Database):
        self.library = library
        self.db = db
        self.models = Models(library)
        self._stop = threading.Event()
        self._wake = threading.Event()
        self.current: dict | None = None
        self.progress: str = ""

    def start(self) -> None:
        threading.Thread(target=self._run, name="worker", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()

    def wake(self) -> None:
        self._wake.set()

    def _run(self) -> None:
        # Anything left "processing" from a crashed run goes back to the queue.
        for r in self.db.list_recordings():
            if r["status"] == "processing":
                self.db.update_recording(r["id"], status="queued", stage=None)
        while not self._stop.is_set():
            rec = self.db.next_queued()
            if rec is None:
                self._wake.wait(timeout=3.0)
                self._wake.clear()
                continue
            self.process(rec)

    def _stage(self, rid: int, stage: str) -> None:
        self.progress = stage
        self.db.update_recording(rid, stage=stage)

    def process(self, rec: dict) -> None:
        rid = rec["id"]
        self.current = rec
        t0 = time.time()
        try:
            self.db.update_recording(rid, status="processing", error=None)
            src = self.library.root / rec["rel_path"]
            cache = self.library.recording_cache(rid)
            s = self.library.settings

            self._stage(rid, "converting audio")
            wav = audio_utils.to_wav16k(src, cache / "audio16k.wav")
            audio_utils.to_playback(src, cache / "playback.m4a")
            samples = audio_utils.load_wav16k(wav)
            (cache / "peaks.json").write_text(json.dumps(audio_utils.waveform_peaks(samples)))
            duration = len(samples) / 16000.0
            (cache / "speech.json").unlink(missing_ok=True)
            self.models.speech_map(cache, samples)

            self._stage(rid, f"transcribing ({s.whisper_model.split('/')[-1]})")
            tr = transcribe(samples, s.whisper_model, s.language)

            self._stage(rid, "finding speakers")
            diarizer_name = "none"
            turns: list[Turn] = []
            try:
                diarizer = self.models.diarizer()
                diarizer_name = diarizer.name
                turns = diarizer(samples)
            except Exception as e:
                self.db.log(f"Diarization failed for {rec['original_name']}: {e}", "warn")
            if not turns:
                turns = [Turn(0.0, duration, "SPEAKER_00")]

            self._stage(rid, "matching voices to people")
            embedder = self.models.embedder()
            by_label: dict[str, list[tuple[float, float]]] = {}
            for t in turns:
                by_label.setdefault(t.speaker, []).append((t.start, t.end))
            speakers: list[dict] = []
            for label, spans in by_label.items():
                emb = embedder.embed_speaker(samples, spans)
                speakers.append({
                    "label": label,
                    "speaking_sec": round(sum(e - b for b, e in spans), 2),
                    "embedding_vec": emb,
                    "embedding": to_blob(emb) if emb is not None else None,
                    "embedding_model": embedder.model_name,
                })
            assign_people(self.db, speakers, embedder.model_name, s.person_match_threshold)

            self._stage(rid, "saving")
            segments = words_to_segments(tr["words"], turns)
            self.db.replace_segments(rid, segments)
            self.db.replace_speakers(rid, speakers)
            self.db.update_recording(
                rid, status="done", stage=None, language=tr.get("language"), whisper_model=s.whisper_model,
                diarizer=diarizer_name, processed_at=now_iso(), duration_sec=duration,
            )
            names = []
            for sp in speakers:
                p = self.db.get_person(sp["person_id"]) if sp.get("person_id") else None
                names.append(p["name"] if p else sp["label"])
            self.db.log(f"Processed {rec['original_name']} in {time.time() - t0:.0f}s: {len(segments)} turns, speakers: {', '.join(names)}")
            if s.auto_summarize and segments:
                self.db.update_recording(rid, summary_status="queued", summary_error=None)
        except Exception as e:
            log.error("processing failed: %s", traceback.format_exc())
            self.db.update_recording(rid, status="error", stage=None, error=f"{type(e).__name__}: {e}")
            self.db.log(f"Processing failed for {rec['original_name']}: {e}", "error")
        finally:
            self.current = None
            self.progress = ""

    # ---- summaries (own thread so transcription is never blocked) -------------
    _summary_lock = threading.Lock()

    def summarize_later(self, rid: int) -> bool:
        """Queue a summary for a processed recording. Returns False if no local model is usable."""
        from .summarize import resolve_provider

        s = self.library.settings
        target = resolve_provider(s.summary_provider, s.summary_model or None)
        if target is None:
            return False
        self.db.update_recording(rid, summary_status="queued", summary_error=None)
        threading.Thread(target=self._summarize, args=(rid, target), name=f"summary-{rid}", daemon=True).start()
        return True

    def summarize_now(self, rid: int) -> None:
        """Run a queued summary in this (worker) process."""
        from .summarize import resolve_provider

        s = self.library.settings
        target = resolve_provider(s.summary_provider, s.summary_model or None)
        if target is None:
            self.db.update_recording(rid, summary_status="error", summary_error="No local model available (start Ollama or choose MLX in Settings).")
            return
        self._summarize(rid, target)

    def _summarize(self, rid: int, target: tuple[str, str]) -> None:
        from .summarize import summarize

        provider, model = target
        with self._summary_lock:
            rec = self.db.get_recording(rid)
            if not rec or rec["status"] != "done":
                return
            self.db.update_recording(rid, summary_status="running")
            try:
                names = {sp["label"]: (sp["person_name"] or sp.get("display_name") or sp["label"]) for sp in self.db.get_speakers(rid)}
                text = summarize(self.db.get_segments(rid), names, provider, model, rec.get("title") or rec["original_name"])
                if not text:
                    raise RuntimeError("the model returned nothing")
                self.db.update_recording(rid, summary=text, summary_model=f"{provider}:{model}", summary_at=now_iso(), summary_status="done", summary_error=None)
                self.db.log(f"Summarized {rec['original_name']} with {model}")
            except Exception as e:
                self.db.update_recording(rid, summary_status="error", summary_error=f"{type(e).__name__}: {e}"[:400])
                self.db.log(f"Summary failed for {rec['original_name']}: {e}", "warn")

    def status(self) -> dict:
        return {
            "current": {"id": self.current["id"], "name": self.current["original_name"], "stage": self.progress} if self.current else None,
            "models": self.models.status(),
        }
