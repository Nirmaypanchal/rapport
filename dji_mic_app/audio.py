"""ffmpeg helpers: probing, hashing, 16 kHz conversion, playback transcode, waveform peaks."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np


def sha256_file(path: Path, chunk: int = 4 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def probe(path: Path) -> dict:
    out = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "a:0",
            "-show_entries", "format=duration,size:stream=codec_name,sample_rate,channels",
            "-of", "json", str(path),
        ],
        capture_output=True, text=True, check=True,
    ).stdout
    d = json.loads(out)
    stream = (d.get("streams") or [{}])[0]
    fmt = d.get("format") or {}
    return {
        "duration_sec": float(fmt.get("duration") or 0.0),
        "size_bytes": int(fmt.get("size") or 0),
        "codec": stream.get("codec_name"),
        "sample_rate": int(stream.get("sample_rate") or 0),
        "channels": int(stream.get("channels") or 0),
    }


def to_wav16k(src: Path, dst: Path) -> Path:
    """Mono 16 kHz PCM16 - what Whisper, VAD and the speaker models expect."""
    if dst.exists() and dst.stat().st_size > 44:
        return dst
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(src), "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(dst)],
        check=True, capture_output=True,
    )
    return dst


def to_playback(src: Path, dst: Path) -> Path:
    """AAC in .m4a: small, seekable, plays in every browser. Originals are never touched."""
    if dst.exists() and dst.stat().st_size > 0:
        return dst
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(src), "-ac", "1", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(dst)],
        check=True, capture_output=True,
    )
    return dst


def load_wav16k(path: Path) -> np.ndarray:
    import soundfile as sf

    data, sr = sf.read(str(path), dtype="float32", always_2d=False)
    if data.ndim > 1:
        data = data.mean(axis=1)
    if sr != 16000:
        raise ValueError(f"expected 16 kHz audio, got {sr}")
    return data


def waveform_peaks(wav16k: np.ndarray, buckets: int = 1500) -> list[float]:
    """Per-bucket peak amplitude (0..1) for drawing the waveform in the UI."""
    n = len(wav16k)
    if n == 0:
        return []
    buckets = max(1, min(buckets, n))
    edges = np.linspace(0, n, buckets + 1, dtype=int)
    peaks = np.zeros(buckets, dtype=np.float32)
    absd = np.abs(wav16k)
    for i in range(buckets):
        seg = absd[edges[i]:edges[i + 1]]
        peaks[i] = seg.max() if len(seg) else 0.0
    m = float(peaks.max()) or 1.0
    return [round(float(p) / m, 3) for p in peaks]


def condense_regions(regions: list[tuple[float, float]], duration: float, min_gap: float, pad: float) -> list[tuple[float, float]]:
    """Merge speech regions separated by less than min_gap; keep `pad` seconds around each kept block."""
    out: list[list[float]] = []
    for s, e in sorted(regions):
        if out and s - out[-1][1] < min_gap:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    padded = []
    for s, e in out:
        s2, e2 = max(0.0, s - pad), min(duration, e + pad)
        if padded and s2 <= padded[-1][1]:
            padded[-1][1] = max(padded[-1][1], e2)
        else:
            padded.append([s2, e2])
    return [(round(s, 3), round(e, 3)) for s, e in padded]


def export_condensed(src: Path, dst: Path, keep: list[tuple[float, float]]) -> Path:
    """Write an .m4a containing only the `keep` spans, back to back."""
    if dst.exists() and dst.stat().st_size > 0:
        return dst
    if not keep:
        raise ValueError("no speech to keep")
    expr = "+".join(f"between(t,{s},{e})" for s, e in keep)
    filt = f"aselect='{expr}',asetpts=N/SR/TB"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(src), "-af", filt, "-ac", "1", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(dst)],
        check=True, capture_output=True,
    )
    return dst
