"""Summaries: loading the shipped templates, assembling the prompt, and cutting a written summary
into the blocks the search index and Ask cite.

Nothing here reaches a real model: the prompt that would be sent is checked, and the streaming path is
driven against a fake Ollama.
"""
import io
import json
import urllib.error

import pytest

from rapport.summarize import (
    CUSTOM_TEMPLATE,
    DEFAULT_TEMPLATE,
    MAX_BLOCK_CHARS,
    PREAMBLE,
    _parse_template,
    build_system,
    builtin_templates,
    get_template,
    source_key,
    split_summary,
    stream_chat,
    template_for,
    templates,
)


def test_builtin_templates_load():
    ids = [t.id for t in builtin_templates()]
    assert set(ids) >= {"meeting", "interview", "lecture", "sales-call", "journal"}
    assert ids[0] == DEFAULT_TEMPLATE, "meeting notes come first"
    for t in builtin_templates():
        assert t.name and t.description and t.prompt
        assert t.builtin
        assert "---" not in t.prompt, "front matter must not leak into the prompt"


def test_front_matter_parsing():
    t = _parse_template("demo", "---\nname: Demo\ndescription: A demo.\norder: 5\n---\nWrite three bullets.\n")
    assert (t.id, t.name, t.description, t.order) == ("demo", "Demo", "A demo.", 5)
    assert t.prompt == "Write three bullets."


def test_template_without_front_matter_is_all_prompt():
    t = _parse_template("plain", "Just do it.\n")
    assert t.prompt == "Just do it." and t.name == "plain" and t.order == 100


def test_bad_order_falls_back():
    assert _parse_template("x", "---\nname: X\norder: soon\n---\nBody").order == 100


def test_custom_template_is_always_offered():
    ids = [t.id for t in templates()]
    assert ids[-1] == CUSTOM_TEMPLATE
    assert not templates()[-1].builtin


def test_get_template_falls_back_to_the_default():
    assert get_template("no-such-template").id == DEFAULT_TEMPLATE
    assert get_template(None).id == DEFAULT_TEMPLATE
    assert get_template("interview").id == "interview"


def test_custom_template_needs_a_prompt():
    assert get_template(CUSTOM_TEMPLATE).id == DEFAULT_TEMPLATE, "an empty custom prompt is not usable"
    t = get_template(CUSTOM_TEMPLATE, "Answer in haiku.")
    assert t.id == CUSTOM_TEMPLATE and t.prompt == "Answer in haiku."


def test_template_for_prefers_the_recordings_own_choice():
    # A pick made in the Summary tab, or the shape the last summary was written in, beats both defaults.
    t = template_for("interview", source="granola", by_source={"granola": "sales-call"}, default="lecture")
    assert t.id == "interview"


def test_template_for_uses_the_default_set_for_the_source():
    by_source = {"granola": "meeting", "voicememos": "journal"}
    assert template_for(None, "voicememos", by_source, "meeting").id == "journal"
    assert template_for(None, "granola", by_source, "journal").id == "meeting"
    # A source with nothing set for it falls through to the one default in Settings.
    assert template_for(None, "dji", by_source, "lecture").id == "lecture"
    assert template_for(None, "dji", {}, "lecture").id == "lecture"
    assert template_for(None, None, None, None).id == DEFAULT_TEMPLATE


def test_a_recording_with_no_source_is_filed_as_dji():
    # `source` arrived after the first releases, so rows written before it are NULL and are DJI mic files.
    assert source_key(None) == "dji" and source_key("") == "dji" and source_key(" granola ") == "granola"
    assert template_for(None, None, {"dji": "journal"}, "meeting").id == "journal"


def test_an_unusable_source_default_falls_back_to_the_users_default_not_to_meeting():
    # The distinction that matters: a stale entry must not quietly demote the default the user did choose.
    assert template_for(None, "omi", {"omi": "no-such-template"}, "lecture").id == "lecture"
    assert template_for(None, "omi", {"omi": CUSTOM_TEMPLATE}, "lecture").id == "lecture", "custom with no prompt"
    t = template_for(None, "omi", {"omi": CUSTOM_TEMPLATE}, "lecture", "Answer in haiku.")
    assert t.id == CUSTOM_TEMPLATE


def test_build_system_keeps_the_rules_and_adds_the_shape():
    system = build_system(get_template("interview"))
    assert system.startswith(PREAMBLE)
    assert "## Questions and answers" in system
    assert "## Key points" not in system, "one template's sections must not leak into another"


def test_build_system_with_a_custom_prompt():
    system = build_system(get_template(CUSTOM_TEMPLATE, "Two bullets, nothing else."))
    assert system == f"{PREAMBLE} Two bullets, nothing else."


def test_every_template_produces_a_distinct_prompt():
    systems = {t.id: build_system(t) for t in builtin_templates()}
    assert len(set(systems.values())) == len(systems)


# ---- cutting a summary into citable blocks --------------------------------

SUMMARY = """# Pricing sync

## Decisions

- We settled the pricing at forty euros a seat.
  Maya pushed back on fifty.
  - Nirmay redoes the deck
- Launch stays on the fourth of October.

**Open questions**

Nobody knows who signs the contract.

## Next steps
1. Send the deck before Friday.
2) Book a follow-up.
"""


def test_split_summary_keeps_one_thought_per_block_under_its_heading():
    blocks = split_summary(SUMMARY)
    assert [h for h, _ in blocks] == ["Decisions", "Decisions", "Open questions", "Next steps", "Next steps"]
    assert blocks[0][1] == "We settled the pricing at forty euros a seat.\nMaya pushed back on fifty.\n- Nirmay redoes the deck", \
        "a wrapped line and a sub-bullet stay with the item they belong to"
    assert blocks[1][1] == "Launch stays on the fourth of October."
    assert blocks[3][1] == "Send the deck before Friday.", "the list marker is not part of the text"
    assert all(not t.startswith(("#", "-", "*")) for _, t in blocks), "a heading is a label, never a block"


def test_split_summary_handles_plain_prose_and_nothing_at_all():
    assert split_summary("Just one paragraph,\nwrapped over two lines.") == [(None, "Just one paragraph,\nwrapped over two lines.")]
    assert split_summary("First.\n\nSecond.") == [(None, "First."), (None, "Second.")]
    assert split_summary(None) == [] and split_summary("") == [] and split_summary("  \n\n ") == []
    assert split_summary("## Decisions\n") == [], "a heading with nothing under it indexes nothing"


def test_split_summary_cuts_a_very_long_block_on_sentence_ends():
    blocks = split_summary("One sentence that says something. " * 60)
    assert len(blocks) > 1 and all(len(t) <= MAX_BLOCK_CHARS for _, t in blocks)
    assert all(t.endswith(".") for _, t in blocks), "cuts land between sentences, not mid-word"
    assert "".join(t for _, t in blocks).count("One sentence") == 60, "nothing is lost in the cutting"


# ---- the streaming path ---------------------------------------------------
# `stream_chat` is `chat` delivered as it is written. Ollama answers `/api/chat` with one JSON object per
# line; this checks that the content is read out of each of them and that the request asked for it. The MLX
# side cannot run here (no Apple silicon) and is exercised by the nightly on the owner's Mac.


class FakeResponse:
    """What `urlopen` gives back: an iterable of raw lines."""

    def __init__(self, lines):
        self._lines = [l if isinstance(l, bytes) else l.encode() for l in lines]

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __iter__(self):
        return iter(self._lines)


def fake_ollama(monkeypatch, lines) -> list[dict]:
    """Answer the next `urlopen` with these lines; returns the list the request bodies land in."""
    sent: list[dict] = []

    def urlopen(req, timeout=None):
        sent.append(json.loads(req.data))
        return FakeResponse(lines)

    monkeypatch.setattr("rapport.summarize.urllib.request.urlopen", urlopen)
    return sent


def chunk(content: str, done: bool = False) -> str:
    return json.dumps({"model": "llama3", "message": {"role": "assistant", "content": content}, "done": done})


def test_streaming_reads_the_content_out_of_every_line(monkeypatch):
    fake_ollama(monkeypatch, [chunk("Forty "), chunk("euros"), chunk("", done=True)])
    assert list(stream_chat("ollama", "llama3", "sys", "user")) == ["Forty ", "euros"]


def test_streaming_asks_ollama_to_stream(monkeypatch):
    """Without this the whole answer arrives in one line and the panel blinks for a minute as before."""
    sent = fake_ollama(monkeypatch, [chunk("hi", done=True)])
    list(stream_chat("ollama", "llama3", "sys", "user"))
    assert sent[0]["stream"] is True
    assert [m["role"] for m in sent[0]["messages"]] == ["system", "user"]


def test_streaming_skips_a_line_that_is_not_a_chunk(monkeypatch):
    """A blank keep-alive line, or a shape this does not know, must not end the answer or raise."""
    fake_ollama(monkeypatch, ["", chunk("Forty"), "  ", "{not json}", chunk(" euros", done=True)])
    assert list(stream_chat("ollama", "llama3", "sys", "user")) == ["Forty", " euros"]


def test_streaming_stops_at_an_ollama_error(monkeypatch):
    def urlopen(req, timeout=None):
        raise urllib.error.HTTPError("http://x", 500, "boom", None, io.BytesIO(b"model not found"))

    monkeypatch.setattr("rapport.summarize.urllib.request.urlopen", urlopen)
    with pytest.raises(RuntimeError, match="model not found"):
        list(stream_chat("ollama", "llama3", "sys", "user"))
