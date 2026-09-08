"""Whisper on Apple silicon via mlx-whisper. Returns word-level timestamps."""
from __future__ import annotations

from pathlib import Path


class _Progress:
    """Stand-in for tqdm inside mlx_whisper.transcribe: turns its frame updates into a 0-1 callback."""

    def __init__(self, cb):
        self.cb = cb

    def tqdm(self, *args, total=None, **kwargs):
        outer = self

        class Bar:
            def __init__(bar):
                bar.n = 0

            def __enter__(bar):
                return bar

            def __exit__(bar, *a):
                return False

            def update(bar, n=1):
                bar.n += n
                if total and outer.cb:
                    outer.cb(min(1.0, bar.n / total))

            def close(bar):
                pass

        return Bar()


def transcribe(audio, model: str, language: str | None = None, on_progress=None) -> dict:
    """`audio` is a 16 kHz float32 numpy array (or a path; arrays avoid Whisper shelling out to ffmpeg).
    `on_progress(frac)` is called as Whisper advances through the audio."""
    import sys

    import mlx_whisper

    mwt = sys.modules["mlx_whisper.transcribe"]  # the package re-exports a function of the same name; we need the module

    opts = {}
    if language:
        opts["language"] = language
    saved = mwt.tqdm
    mwt.tqdm = _Progress(on_progress)  # single worker process: safe to swap for the duration of the call
    try:
        result = mlx_whisper.transcribe(
            audio if not isinstance(audio, Path) else str(audio),
            path_or_hf_repo=model,
            word_timestamps=True,
            condition_on_previous_text=False,  # fewer repetition loops on long files
            hallucination_silence_threshold=2.0,
            verbose=None,
            **opts,
        )
    finally:
        mwt.tqdm = saved
    words: list[dict] = []
    for seg in result.get("segments", []):
        ws = seg.get("words") or []
        if ws:
            for w in ws:
                text = (w.get("word") or "").strip()
                if not text:
                    continue
                words.append({"word": text, "start": float(w["start"]), "end": float(w["end"]), "p": float(w.get("probability", 1.0))})
        else:
            text = (seg.get("text") or "").strip()
            if text:
                words.append({"word": text, "start": float(seg["start"]), "end": float(seg["end"]), "p": 1.0})
    return {"language": result.get("language"), "text": (result.get("text") or "").strip(), "words": words}
