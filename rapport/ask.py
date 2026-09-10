"""Ask your library: a question answered from your own transcripts, on this Mac.

Retrieval is the same SQLite full-text index the Search page uses. The excerpts it finds are the answer's only
source material: the local model (Ollama or MLX — the one that writes summaries) turns them into a few sentences
and cites them by number. Nothing is sent anywhere.

When no local model is available the excerpts are returned on their own, which is already an answer of sorts;
nothing is ever invented to fill the gap.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .summarize import chat, resolve_provider

SEARCH_LIMIT = 60      # FTS hits considered before they are thinned into excerpts
MAX_PASSAGES = 8       # excerpts shown, and given to the model
PER_RECORDING = 2      # at most this many from one recording, so a long meeting cannot crowd out the rest
CONTEXT_SEGMENTS = 1   # turns kept on each side of a hit
MAX_KEYWORDS = 12

SYSTEM = (
    "You answer questions about someone's own audio recordings, using only the numbered excerpts you are given. "
    "Answer in the language of the question. Cite the excerpts you used as [1], [2] and so on, right after the "
    "sentence they support. Never invent a fact, a name, a number or a date, and never use knowledge from outside "
    "the excerpts. If the excerpts do not answer the question, say so in one sentence and say what they do cover. "
    "Keep it short: a few sentences or a short list. Refer to people by the names in the excerpts and avoid "
    "gendered pronouns unless an excerpt makes them explicit."
)

# Words that carry no signal in a question. English only: for other languages the terms stay in, where bm25
# discounts them anyway because they are in almost every recording.
STOPWORDS = frozenset("""
a about after all also am an and any anything are as at be because been being but by can could did do does doing
done for from get gets got had has have how i if in into is it its just me mine my of on or our ours out over
said say saying says should so some something tell than that the their theirs them then there these they thing
things this those to told too us was we were what when where which while who whom why will with would you your
yours
""".split())

_WORD = re.compile(r"[^\W_]+(?:['’][^\W_]+)*", re.UNICODE)
_CITATION = re.compile(r"\[(\d{1,2})\]")


def keywords(question: str, limit: int = MAX_KEYWORDS) -> list[str]:
    """The words worth searching for, in the order they were asked, without repeats.

    Punctuation is dropped here rather than in the FTS query, where a token that tokenizes to nothing is a
    syntax error. A question made entirely of stopwords ("what is it about?") keeps them: something is better
    than searching for nothing.
    """
    words = [w.lower() for w in _WORD.findall(question or "")]
    kept = [w for w in words if w not in STOPWORDS and (len(w) > 1 or w.isdigit())]
    return list(dict.fromkeys(kept or words))[:limit]


@dataclass(frozen=True)
class Passage:
    """One moment in one recording: the turn that matched, plus the turns around it."""

    recording_id: int
    segment_id: int
    start: float
    end: float
    speaker: str
    speaker_color: str | None
    text: str
    snippet: str
    title: str
    recorded_at: str | None

    def to_json(self, n: int) -> dict:
        return {
            "n": n, "recording_id": self.recording_id, "segment_id": self.segment_id,
            "start": self.start, "end": self.end,
            "speaker": self.speaker, "person_color": self.speaker_color,
            "text": self.text, "snippet": self.snippet, "title": self.title, "recorded_at": self.recorded_at,
            "cited": True,
        }


def pick_hits(hits: list[dict], max_passages: int = MAX_PASSAGES, per_recording: int = PER_RECORDING) -> list[dict]:
    """Best first (the search is already ranked), with a cap per recording."""
    per: dict[int, int] = {}
    out: list[dict] = []
    for h in hits:
        rid = h["recording_id"]
        if per.get(rid, 0) >= per_recording:
            continue
        per[rid] = per.get(rid, 0) + 1
        out.append(h)
        if len(out) >= max_passages:
            break
    return out


def speaker_name(row: dict) -> str:
    return row.get("person_name") or row.get("speaker_label") or "Unknown"


def passages(db, hits: list[dict], context: int = CONTEXT_SEGMENTS) -> list[Passage]:
    """Turn search hits into readable excerpts. Hits whose turns another excerpt already covers are dropped."""
    covered: set[int] = set()
    out: list[Passage] = []
    for h in hits:
        if h["id"] in covered:
            continue
        rows = db.segment_context(h["id"], context, context) or [
            {"id": h["id"], "speaker_label": h.get("speaker_label"), "text": h.get("snippet", "")}
        ]
        covered |= {r["id"] for r in rows}
        out.append(Passage(
            recording_id=h["recording_id"],
            segment_id=h["id"],
            start=h.get("start") or 0.0,
            end=h.get("end") or 0.0,
            speaker=speaker_name({"person_name": h.get("person_name"), "speaker_label": h.get("speaker_label")}),
            speaker_color=h.get("person_color"),
            text="\n".join(f"{speaker_name(r)}: {r['text']}" for r in rows).strip(),
            snippet=h.get("snippet") or "",
            title=h.get("title") or h.get("original_name") or "Recording",
            recorded_at=h.get("recorded_at"),
        ))
    return out


def clock(seconds: float) -> str:
    s = max(0, int(seconds))
    h, rest = divmod(s, 3600)
    m, sec = divmod(rest, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"


def build_user(question: str, found: list[Passage]) -> str:
    """The question and the numbered excerpts, in the order the model should cite them."""
    blocks = []
    for i, p in enumerate(found, 1):
        when = f", {p.recorded_at[:10]}" if p.recorded_at else ""
        blocks.append(f"[{i}] {p.title}{when}, at {clock(p.start)}\n{p.text}")
    return f"Question: {question}\n\nExcerpts:\n\n" + "\n\n".join(blocks)


def cited(answer: str, count: int) -> list[int]:
    """The excerpt numbers the answer really cites, first use first. Numbers out of range are ignored."""
    nums = (int(m) for m in _CITATION.findall(answer or ""))
    return list(dict.fromkeys(n for n in nums if 1 <= n <= count))


def ask(db, question: str, provider: str = "auto", model: str | None = None, limit: int = SEARCH_LIMIT) -> dict:
    """Answer `question` from the library. Always returns the excerpts, with or without a written answer.

    `reason` says why there is no answer: `no_matches`, `no_model`, `model_error` or `empty_answer`.
    """
    q = (question or "").strip()
    if not q:
        raise ValueError("ask a question")
    terms = keywords(q)
    hits = db.search(" ".join(terms), limit=limit, match="any") if terms else []
    found = passages(db, pick_hits(hits))
    out: dict = {
        "question": q,
        "answer": None,
        "sources": [p.to_json(i) for i, p in enumerate(found, 1)],
        "model": None,
        "reason": None,
        "error": None,
    }
    if not found:
        out["reason"] = "no_matches"
        return out
    target = resolve_provider(provider, model)
    if target is None:
        out["reason"] = "no_model"
        return out
    out["model"] = {"provider": target[0], "model": target[1]}
    try:
        text = chat(target[0], target[1], SYSTEM, build_user(q, found), max_tokens=600, timeout=180).strip()
    except Exception as e:  # a model that is missing, busy or broken must not lose the excerpts
        out["reason"] = "model_error"
        out["error"] = str(e)[:300]
        return out
    if not text:
        out["reason"] = "empty_answer"
        return out
    out["answer"] = text
    used = cited(text, len(found))
    if used:  # an answer that cites nothing still rests on every excerpt, so leave them all marked
        for s in out["sources"]:
            s["cited"] = s["n"] in used
    return out
