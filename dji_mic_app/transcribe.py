"""Whisper on Apple silicon via mlx-whisper. Returns word-level timestamps."""
from __future__ import annotations

from pathlib import Path


def transcribe(wav16k: Path, model: str, language: str | None = None) -> dict:
    import mlx_whisper

    opts = {}
    if language:
        opts["language"] = language
    result = mlx_whisper.transcribe(
        str(wav16k),
        path_or_hf_repo=model,
        word_timestamps=True,
        condition_on_previous_text=False,  # fewer repetition loops on long files
        hallucination_silence_threshold=2.0,
        **opts,
    )
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
