"""Voice embeddings and the cross-recording people registry.

Every diarized speaker in every recording gets one 256-d voice embedding
(WeSpeaker ResNet34, via pyannote.audio). A *person* is a set of those
embeddings. To recognise someone in a new recording we compare the new
speaker's embedding with each person's centroid; above the similarity
threshold we link them, otherwise we create a new auto-named person which
the user can rename later. Renaming/merging never needs re-processing.
"""
from __future__ import annotations

import numpy as np

from .db import Database

SR = 16000
COLORS = ["sky", "blush", "sage", "orchid", "butter", "aqua", "periwinkle", "peach", "mint", "rose", "lime", "steel", "lilac", "apricot", "seafoam", "dusk"]  # Cue Sheet pastel palette; the UI maps names to tokens


class Embedder:
    def __init__(self, model_name: str, token: str | None):
        import torch
        from pyannote.audio import Model

        self.model_name = model_name
        self.model = Model.from_pretrained(model_name, token=token)
        self.model.eval()
        self.device = torch.device("cpu")
        self.model.to(self.device)

    def embed_batch(self, clips: list[np.ndarray], batch_size: int = 32, on_progress=None) -> np.ndarray:
        """Equal-length clips -> (n, d) L2-normalised embeddings."""
        import torch

        out = []
        with torch.inference_mode():
            for i in range(0, len(clips), batch_size):
                if on_progress:
                    on_progress(i / max(1, len(clips)))
                batch = np.stack(clips[i:i + batch_size]).astype(np.float32)
                x = torch.from_numpy(batch).unsqueeze(1).to(self.device)  # (b, 1, samples)
                e = self.model(x)
                out.append(e.detach().cpu().numpy())
        emb = np.concatenate(out, axis=0)
        return emb / (np.linalg.norm(emb, axis=1, keepdims=True) + 1e-9)

    def embed_speaker(self, audio: np.ndarray, turns: list[tuple[float, float]], max_seconds: float = 90.0) -> np.ndarray | None:
        """Average embedding of a speaker's longest turns (up to max_seconds of audio)."""
        turns = sorted(turns, key=lambda t: -(t[1] - t[0]))
        pieces: list[np.ndarray] = []
        total = 0.0
        for s, e in turns:
            if e - s < 0.5:
                continue
            pieces.append(audio[int(s * SR):int(e * SR)])
            total += e - s
            if total >= max_seconds:
                break
        if not pieces:
            return None
        cat = np.concatenate(pieces)
        chunk = int(6.0 * SR)
        clips = []
        for i in range(0, len(cat), chunk):
            c = cat[i:i + chunk]
            if len(c) < int(1.0 * SR):
                continue
            if len(c) < chunk:
                c = np.tile(c, int(np.ceil(chunk / len(c))))[:chunk]
            clips.append(c)
        if not clips:
            clips = [np.tile(cat, int(np.ceil(chunk / len(cat))))[:chunk]]
        emb = self.embed_batch(clips).mean(axis=0)
        return (emb / (np.linalg.norm(emb) + 1e-9)).astype(np.float32)


def to_blob(v: np.ndarray) -> bytes:
    return np.asarray(v, dtype=np.float32).tobytes()


def from_blob(b: bytes) -> np.ndarray:
    return np.frombuffer(b, dtype=np.float32)


def person_centroids(db: Database, model: str) -> dict[int, np.ndarray]:
    sums: dict[int, np.ndarray] = {}
    weights: dict[int, float] = {}
    for pid, blob, sec in db.person_embeddings(model):
        v = from_blob(blob)
        w = max(1.0, float(sec))
        sums[pid] = sums.get(pid, 0) + v * w
        weights[pid] = weights.get(pid, 0.0) + w
    return {pid: sums[pid] / (np.linalg.norm(sums[pid]) + 1e-9) for pid in sums}


def next_color(db: Database) -> str:
    """Least-used palette name, ties broken by palette order (keeps neighbours distinct)."""
    used = [p.get("color") for p in db.list_people()]
    counts = {c: used.count(c) for c in COLORS}
    return min(COLORS, key=lambda c: (counts[c], COLORS.index(c)))


def next_auto_name(db: Database) -> str:
    existing = {p["name"] for p in db.list_people()}
    i = 1
    while f"Speaker {i}" in existing:
        i += 1
    return f"Speaker {i}"


def assign_people(db: Database, speakers: list[dict], model: str, threshold: float) -> None:
    """Link each diarized speaker (with 'embedding' ndarray) to a person, creating people as needed.

    Greedy by similarity so two speakers in one recording never map to the same person.
    """
    cents = person_centroids(db, model)
    pids = list(cents)
    matrix = np.stack([cents[p] for p in pids]) if pids else np.zeros((0, 1))

    candidates = []
    for i, sp in enumerate(speakers):
        emb = sp.get("embedding_vec")
        if emb is None or not pids:
            continue
        sims = matrix @ emb
        for j, s in enumerate(sims):
            if s >= threshold:
                candidates.append((float(s), i, pids[j]))
    candidates.sort(reverse=True)
    used_people: set[int] = set()
    done: set[int] = set()
    for s, i, pid in candidates:
        if i in done or pid in used_people:
            continue
        speakers[i]["person_id"] = pid
        speakers[i]["similarity"] = s
        done.add(i)
        used_people.add(pid)

    for i, sp in enumerate(speakers):
        if i in done:
            continue
        if sp.get("embedding_vec") is None:
            sp["person_id"] = None
            continue
        pid = db.create_person(next_auto_name(db), auto=True, color=next_color(db))
        sp["person_id"] = pid
        sp["similarity"] = None


def rematch_all(db: Database, threshold: float) -> dict:
    """Forget all people, then re-run voice matching over every recording in chronological order
    using the embeddings stored at processing time. Fast: no audio is touched."""
    removed = db.reset_people()
    recs = sorted(db.list_recordings(), key=lambda r: (r.get("recorded_at") or "", r["id"]))
    matched = 0
    for r in recs:
        speakers = db.speakers_with_embeddings(r["id"])
        if not speakers:
            continue
        model = next((sp["embedding_model"] for sp in speakers if sp.get("embedding_model")), None)
        for sp in speakers:
            sp["embedding_vec"] = from_blob(sp["embedding"]) if sp.get("embedding") else None
        if model is None:
            continue
        assign_people(db, speakers, model, threshold)
        for sp in speakers:
            if sp.get("person_id"):
                db.set_speaker_person(r["id"], sp["label"], sp["person_id"])
                if sp.get("similarity") is not None:
                    c = db.connect()
                    with c:
                        c.execute("UPDATE recording_speakers SET similarity=? WHERE recording_id=? AND label=?", (sp["similarity"], r["id"], sp["label"]))
                matched += 1
    return {"people_removed": removed, "speakers_matched": matched, "people_now": len(db.list_people())}
