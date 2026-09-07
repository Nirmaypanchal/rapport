"""Who spoke when.

Two engines:

* ``pyannote``  - pyannote's pretrained diarization pipeline. Best quality, but the
                  models are gated on Hugging Face: you must accept their terms once
                  and have a token. Used automatically when that works.
* ``builtin``   - no accounts needed. Silero VAD finds speech, the (ungated)
                  WeSpeaker model embeds 2 s windows, and agglomerative clustering
                  groups the windows into speakers. Good for the 1-4 clean lavalier
                  voices a DJI mic usually records.

Both return a list of turns: ``[{"start", "end", "speaker": "SPEAKER_00"}, ...]``
sorted by time, labels ordered by total speaking time.
"""
from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass

import numpy as np

log = logging.getLogger(__name__)
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

SR = 16000
WIN = 2.0     # s
STEP = 0.75   # s
FRAME = 0.1   # s, label resolution
PYANNOTE_PIPELINES = ["pyannote/speaker-diarization-community-1", "pyannote/speaker-diarization-3.1"]


@dataclass
class Turn:
    start: float
    end: float
    speaker: str

    def as_dict(self) -> dict:
        return {"start": round(self.start, 3), "end": round(self.end, 3), "speaker": self.speaker}


def _relabel_by_duration(turns: list[Turn]) -> list[Turn]:
    total: dict[str, float] = {}
    for t in turns:
        total[t.speaker] = total.get(t.speaker, 0.0) + (t.end - t.start)
    order = sorted(total, key=lambda k: -total[k])
    mapping = {old: f"SPEAKER_{i:02d}" for i, old in enumerate(order)}
    out = [Turn(t.start, t.end, mapping[t.speaker]) for t in turns]
    out.sort(key=lambda t: (t.start, t.end))
    return out


def _merge_adjacent(turns: list[Turn], gap: float = 0.3) -> list[Turn]:
    turns = sorted(turns, key=lambda t: t.start)
    out: list[Turn] = []
    for t in turns:
        if out and out[-1].speaker == t.speaker and t.start - out[-1].end <= gap:
            out[-1].end = max(out[-1].end, t.end)
        else:
            out.append(Turn(t.start, t.end, t.speaker))
    return out


# --------------------------------------------------------------------------- VAD
def load_vad():
    from silero_vad import load_silero_vad

    return load_silero_vad()


def speech_regions(audio: np.ndarray, vad_model) -> list[tuple[float, float]]:
    """Silero VAD speech regions in seconds for 16 kHz mono audio."""
    import torch
    from silero_vad import get_speech_timestamps

    ts = get_speech_timestamps(
        torch.from_numpy(np.ascontiguousarray(audio, dtype=np.float32)), vad_model, sampling_rate=SR, return_seconds=True,
        min_speech_duration_ms=250, min_silence_duration_ms=300, speech_pad_ms=60,
    )
    return [(float(t["start"]), float(t["end"])) for t in ts]


# --------------------------------------------------------------------------- pyannote
class PyannoteDiarizer:
    name = "pyannote"

    def __init__(self, token: str | None):
        from pyannote.audio import Pipeline

        self.pipeline = None
        last_err: Exception | None = None
        for repo in PYANNOTE_PIPELINES:
            try:
                self.pipeline = Pipeline.from_pretrained(repo, token=token)
                if self.pipeline is not None:
                    self.repo = repo
                    break
            except Exception as e:  # gated / offline / no token
                last_err = e
        if self.pipeline is None:
            raise RuntimeError(f"pyannote pipeline unavailable: {last_err}")

    def __call__(self, audio: np.ndarray) -> list[Turn]:
        import torch

        wav = torch.from_numpy(np.ascontiguousarray(audio, dtype=np.float32)).unsqueeze(0)
        out = self.pipeline({"waveform": wav, "sample_rate": SR})
        ann = getattr(out, "exclusive_speaker_diarization", None) or getattr(out, "speaker_diarization", None) or out
        turns = [Turn(float(seg.start), float(seg.end), str(label)) for seg, _, label in ann.itertracks(yield_label=True)]
        return _relabel_by_duration(_merge_adjacent(turns))


# --------------------------------------------------------------------------- builtin
class BuiltinDiarizer:
    name = "builtin"

    def __init__(self, embedder, distance_threshold: float = 0.55, min_speaker_seconds: float = 2.0, vad_model=None):
        self.vad = vad_model if vad_model is not None else load_vad()
        self.embedder = embedder  # speakers.Embedder
        self.distance_threshold = distance_threshold
        self.min_speaker_seconds = min_speaker_seconds

    def speech_regions(self, audio: np.ndarray) -> list[tuple[float, float]]:
        return speech_regions(audio, self.vad)

    def __call__(self, audio: np.ndarray) -> list[Turn]:
        regions = self.speech_regions(audio)
        if not regions:
            return []

        # Sliding windows inside speech regions.
        centers: list[float] = []
        clips: list[np.ndarray] = []
        n_win = int(WIN * SR)
        for s, e in regions:
            if e - s < 0.6:
                continue
            t = s
            while True:
                a = int(t * SR)
                clip = audio[a:a + n_win]
                if len(clip) < n_win:  # tail: take the last full window of the region if possible
                    a = max(int(s * SR), int(e * SR) - n_win)
                    clip = audio[a:a + n_win]
                    if len(clip) < n_win:
                        clip = np.tile(clip, int(np.ceil(n_win / max(1, len(clip)))))[:n_win]
                clips.append(clip)
                centers.append(a / SR + WIN / 2)
                if t + WIN >= e:
                    break
                t += STEP
        if not clips:
            return _relabel_by_duration([Turn(s, e, "A") for s, e in regions])

        emb = self.embedder.embed_batch(clips)  # (n, d) L2-normalised
        labels = self._cluster(emb)

        # Drop tiny clusters into their nearest neighbour.
        labels = self._absorb_small(emb, labels, centers)

        # Frame-level assignment inside speech regions: nearest window centre, then smooth.
        turns: list[Turn] = []
        centers_arr = np.asarray(centers)
        for s, e in regions:
            frames = np.arange(s, e, FRAME)
            if len(frames) == 0:
                continue
            idx = np.abs(frames[:, None] - centers_arr[None, :]).argmin(axis=1)
            fl = labels[idx]
            fl = self._median_smooth(fl, k=7)
            cur = fl[0]
            cur_start = s
            for i in range(1, len(fl)):
                if fl[i] != cur:
                    turns.append(Turn(cur_start, float(frames[i]), f"C{cur}"))
                    cur, cur_start = fl[i], float(frames[i])
            turns.append(Turn(cur_start, e, f"C{cur}"))
        return _relabel_by_duration(_merge_adjacent(turns))

    def _cluster(self, emb: np.ndarray) -> np.ndarray:
        n = len(emb)
        if n < 2:
            return np.zeros(n, dtype=int)
        from sklearn.cluster import AgglomerativeClustering

        cl = AgglomerativeClustering(n_clusters=None, metric="cosine", linkage="average", distance_threshold=self.distance_threshold)
        labels = cl.fit_predict(emb)
        # One refinement pass: re-assign each window to its closest centroid, then merge near-duplicate centroids.
        for _ in range(2):
            cents = self._centroids(emb, labels)
            sims = emb @ cents.T
            labels = sims.argmax(axis=1)
            cents = self._centroids(emb, labels)
            k = len(cents)
            merged = False
            for i in range(k):
                for j in range(i + 1, k):
                    if cents[i] @ cents[j] > 1 - self.distance_threshold:
                        labels[labels == j] = i
                        merged = True
            labels = self._compact(labels)
            if not merged:
                break
        return labels

    @staticmethod
    def _compact(labels: np.ndarray) -> np.ndarray:
        uniq = {v: i for i, v in enumerate(sorted(set(labels.tolist())))}
        return np.asarray([uniq[v] for v in labels.tolist()], dtype=int)

    @staticmethod
    def _centroids(emb: np.ndarray, labels: np.ndarray) -> np.ndarray:
        cents = []
        for lab in sorted(set(labels.tolist())):
            c = emb[labels == lab].mean(axis=0)
            cents.append(c / (np.linalg.norm(c) + 1e-9))
        return np.stack(cents)

    def _absorb_small(self, emb: np.ndarray, labels: np.ndarray, centers: list[float]) -> np.ndarray:
        while True:
            uniq = sorted(set(labels.tolist()))
            if len(uniq) <= 1:
                return labels
            dur = {lab: float((labels == lab).sum()) * STEP for lab in uniq}
            small = [lab for lab in uniq if dur[lab] < self.min_speaker_seconds]
            if not small:
                return labels
            victim = min(small, key=lambda lab: dur[lab])
            keep = [lab for lab in uniq if lab != victim]
            cents = np.stack([emb[labels == lab].mean(axis=0) for lab in keep])
            cents /= np.linalg.norm(cents, axis=1, keepdims=True) + 1e-9
            for i in np.where(labels == victim)[0]:
                labels[i] = keep[int((cents @ emb[i]).argmax())]
            labels = self._compact(labels)

    @staticmethod
    def _median_smooth(x: np.ndarray, k: int = 5) -> np.ndarray:
        if len(x) < k:
            return x
        out = x.copy()
        h = k // 2
        for i in range(len(x)):
            win = x[max(0, i - h): i + h + 1]
            vals, counts = np.unique(win, return_counts=True)
            out[i] = vals[counts.argmax()]
        return out
