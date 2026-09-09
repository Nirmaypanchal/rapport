"""Summaries from a local model. Two providers, both on this Mac:

* ``ollama`` - if the Ollama app is running (http://127.0.0.1:11434), use one of its models.
* ``mlx``    - otherwise mlx-lm with a small instruct model downloaded once from Hugging Face.

Nothing is sent anywhere else.

What the summary looks like comes from a *template*: a Markdown file in ``rapport/templates`` whose front matter
names it and whose body tells the model which sections to write. Every template is prefixed with ``PREAMBLE``,
the rules that hold whatever the recording is. Users can also write their own prompt (the ``custom`` template).
"""
from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

OLLAMA = "http://127.0.0.1:11434"
MLX_DEFAULT = "mlx-community/Qwen2.5-3B-Instruct-4bit"

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
DEFAULT_TEMPLATE = "meeting"
CUSTOM_TEMPLATE = "custom"

PREAMBLE = (
    "You summarize transcripts of audio recordings made with a personal microphone. "
    "Write in the language of the transcript. Be concrete and faithful: never invent facts, names or numbers. "
    "Use the speaker names given; refer to people by name and avoid gendered pronouns unless the transcript makes them explicit."
)


@dataclass(frozen=True)
class Template:
    id: str
    name: str
    description: str
    prompt: str
    order: int = 100
    builtin: bool = True

    def to_json(self) -> dict:
        return {"id": self.id, "name": self.name, "description": self.description, "builtin": self.builtin}


def _parse_template(tid: str, text: str) -> Template:
    """`---` front matter with `name`, `description` and `order`, then the prompt body."""
    meta: dict[str, str] = {}
    body = text
    if text.startswith("---"):
        lines = text.splitlines()
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        if end is not None:
            for line in lines[1:end]:
                key, sep, value = line.partition(":")
                if sep:
                    meta[key.strip().lower()] = value.strip()
            body = "\n".join(lines[end + 1:])
    try:
        order = int(meta.get("order", "100"))
    except ValueError:
        order = 100
    return Template(id=tid, name=meta.get("name") or tid, description=meta.get("description", ""), prompt=body.strip(), order=order)


_templates_cache: list[Template] | None = None


def builtin_templates() -> list[Template]:
    """Every template shipped with the app, in display order. Read once, then cached."""
    global _templates_cache
    if _templates_cache is None:
        found = []
        for p in sorted(TEMPLATE_DIR.glob("*.md")):
            try:
                found.append(_parse_template(p.stem, p.read_text(encoding="utf-8")))
            except OSError:
                continue
        _templates_cache = sorted(found, key=lambda t: (t.order, t.name))
    return list(_templates_cache)


def templates(custom_prompt: str = "") -> list[Template]:
    """The built-in templates plus the user's own prompt, which is always offered."""
    custom = Template(
        id=CUSTOM_TEMPLATE, name="Custom prompt",
        description="Your own instructions, written in Settings." if custom_prompt.strip() else "Write your own instructions in Settings.",
        prompt=custom_prompt.strip(), order=1000, builtin=False,
    )
    return builtin_templates() + [custom]


def get_template(tid: str | None, custom_prompt: str = "") -> Template:
    """The template with this id, falling back to the default. A `custom` with no prompt falls back too."""
    by_id = {t.id: t for t in templates(custom_prompt)}
    t = by_id.get(tid or "")
    if t is None or (t.id == CUSTOM_TEMPLATE and not t.prompt):
        t = by_id.get(DEFAULT_TEMPLATE) or next(iter(by_id.values()))
    return t


def build_system(template: Template) -> str:
    """The system prompt sent to the model: the rules that always hold, then the template's own instructions."""
    return f"{PREAMBLE} {template.prompt}" if template.prompt else PREAMBLE


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


def summarize(
    segments: list[dict], names: dict[str, str], provider: str, model: str,
    title: str | None = None, template: Template | None = None,
) -> str:
    system = build_system(template or get_template(DEFAULT_TEMPLATE))
    transcript = _transcript_text(segments, names)
    user = f"Recording: {title or 'untitled'}\nSpeakers: {', '.join(sorted(set(names.values()))) or 'unknown'}\n\nTranscript:\n{transcript}"
    if provider == "ollama":
        return _ollama_chat(model, system, user)
    return _mlx_chat(model, system, user)


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
