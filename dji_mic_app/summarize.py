"""Summaries from a local model. Two providers, both on this Mac:

* ``ollama`` - if the Ollama app is running (http://127.0.0.1:11434), use one of its models.
* ``mlx``    - otherwise mlx-lm with a small instruct model downloaded once from Hugging Face.

Nothing is sent anywhere else.
"""
from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

OLLAMA = "http://127.0.0.1:11434"
MLX_DEFAULT = "mlx-community/Qwen2.5-3B-Instruct-4bit"

SYSTEM = (
    "You summarize transcripts of audio recordings made with a personal microphone. "
    "Write in the language of the transcript. Be concrete and faithful: never invent facts, names or numbers. "
    "Use the speaker names given; refer to people by name and avoid gendered pronouns unless the transcript makes them explicit. Output Markdown with exactly these sections:\n"
    "## Summary\nOne short paragraph (2-4 sentences) saying what this recording is and what happened.\n"
    "## Key points\n3-8 bullets with the substance, each one line.\n"
    "## Action items\nBullets of anything someone said they would do or asked for, with who; write 'None' if there are none.\n"
    "## Notable quotes\nUp to 3 short verbatim quotes with the speaker; omit the section if nothing stands out."
)

_mlx_lock = threading.Lock()
_mlx_cache: dict[str, tuple] = {}


def ollama_models(timeout: float = 1.5) -> list[str]:
    try:
        with urllib.request.urlopen(f"{OLLAMA}/api/tags", timeout=timeout) as r:
            data = json.load(r)
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def resolve_provider(provider: str, model: str | None) -> tuple[str, str] | None:
    """(provider, model) actually usable right now, or None if summaries are off / unavailable."""
    if provider == "off":
        return None
    if provider in ("auto", "ollama"):
        models = ollama_models()
        if models:
            chosen = model if model in models else (model if provider == "ollama" and model else models[0])
            return ("ollama", chosen)
        if provider == "ollama":
            return None
    return ("mlx", model if model and "/" in model else MLX_DEFAULT)


def _transcript_text(segments: list[dict], names: dict[str, str], max_chars: int = 60_000) -> str:
    lines = []
    for s in segments:
        m, sec = divmod(int(s["start"]), 60)
        lines.append(f"[{m:02d}:{sec:02d}] {names.get(s['speaker_label'], s['speaker_label'])}: {s['text']}")
    text = "\n".join(lines)
    if len(text) > max_chars:  # keep head and tail for very long recordings
        text = text[: max_chars // 2] + "\n[...]\n" + text[-max_chars // 2 :]
    return text


def summarize(segments: list[dict], names: dict[str, str], provider: str, model: str, title: str | None = None) -> str:
    transcript = _transcript_text(segments, names)
    user = f"Recording: {title or 'untitled'}\nSpeakers: {', '.join(sorted(set(names.values()))) or 'unknown'}\n\nTranscript:\n{transcript}"
    if provider == "ollama":
        return _ollama_chat(model, SYSTEM, user)
    return _mlx_chat(model, SYSTEM, user)


def _ollama_chat(model: str, system: str, user: str) -> str:
    body = json.dumps({
        "model": model, "stream": False,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "options": {"temperature": 0.2, "num_ctx": 16384},
    }).encode()
    req = urllib.request.Request(f"{OLLAMA}/api/chat", data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Ollama error {e.code}: {e.read().decode(errors='ignore')[:200]}") from e
    return (data.get("message") or {}).get("content", "").strip()


def _mlx_chat(model: str, system: str, user: str) -> str:
    from mlx_lm import generate, load

    with _mlx_lock:
        if model not in _mlx_cache:
            _mlx_cache.clear()
            _mlx_cache[model] = load(model)
        m, tok = _mlx_cache[model]
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        prompt = tok.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
        return generate(m, tok, prompt=prompt, max_tokens=900, verbose=False).strip()
