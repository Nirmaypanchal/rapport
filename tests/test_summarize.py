"""Summary templates: loading the shipped Markdown files and assembling the prompt.

Nothing here talks to a model; only the prompt that would be sent is checked.
"""
from rapport.summarize import (
    CUSTOM_TEMPLATE,
    DEFAULT_TEMPLATE,
    PREAMBLE,
    _parse_template,
    build_system,
    builtin_templates,
    get_template,
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
