"""Guards for scripts/reddit_post.py, the only way anything this team writes reaches r/rapport.

On 2026-09-14 the first weekly update failed with `subreddit 'apport' is not allowed` (issue #16): the
allow-list check did `.lstrip("r/")`, which strips leading `r` and `/` *characters* rather than the prefix,
so the literal word "rapport" — the only value any real file ever carries — could never pass it. The same
`parse()` truncated any frontmatter value starting with a lowercase `t` word to that one word. Neither bug
needed credentials to fire and nothing tested this script, so both were invisible until a post was written.

These tests cover the decision the script makes about a file — post this, refuse that — and never touch the
network: `prepare()` stops one step short of `token()` and `call()`.
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "reddit_post.py"


def load():
    spec = importlib.util.spec_from_file_location("reddit_post", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rp = load()


@pytest.fixture
def outbox(tmp_path):
    """A scratch outbox with sent/ and failed/ beside it, the shape sprint/reddit/ has."""
    d = tmp_path / "outbox"
    d.mkdir()
    (d / "README.md").write_text("Files here are posted by the workflow. Not a post itself.\n")
    return d


def write(folder: Path, name: str, head: str, body: str = "A body.\n") -> Path:
    path = folder / name
    path.write_text(f"---\n{head.strip()}\n---\n{body}")
    return path


# --- the bug that blocked every post ------------------------------------------------------------


@pytest.mark.parametrize("raw", ["rapport", "r/rapport", "/r/rapport", "R/Rapport", " rapport ", "RAPPORT"])
def test_the_subreddit_we_actually_write(raw):
    """`rapport` with no prefix is the shape every real outbox file uses, and it is what `.lstrip("r/")`
    turned into `apport`."""
    assert rp.subreddit(raw) == "rapport"


def test_a_post_to_rapport_is_prepared(outbox):
    f = write(outbox, "2026-09-14-weekly-update.md", "kind: post\nsubreddit: rapport\ntitle: This week in Rapport")
    kind, api, form = rp.prepare(f)
    assert (kind, api) == ("post", "/api/submit")
    assert form["sr"] == "rapport"
    assert form["title"] == "This week in Rapport"


def test_another_subreddit_is_still_refused(outbox):
    """The one rule this script exists to enforce. r/rapport is the project's only public channel."""
    f = write(outbox, "post.md", "kind: post\nsubreddit: r/macapps\ntitle: Hello")
    with pytest.raises(RuntimeError, match="is not allowed"):
        rp.prepare(f)


def test_a_missing_subreddit_is_refused(outbox):
    f = write(outbox, "post.md", "kind: post\ntitle: Hello")
    with pytest.raises(RuntimeError, match="is not allowed"):
        rp.prepare(f)


# --- the bug beside it: values starting with a lowercase `t` --------------------------------------


def test_a_title_starting_with_a_lowercase_word_survives(outbox):
    """`the` is the word that broke it: the old rule kept only the first word of any value starting with
    the letter `t`, so this title would have been posted as "the"."""
    f = write(outbox, "post.md", "kind: post\nsubreddit: rapport\ntitle: the week Rapport learned to answer")
    _, _, form = rp.prepare(f)
    assert form["title"] == "the week Rapport learned to answer"


@pytest.mark.parametrize("raw,want", [
    ("  the week in Rapport  ", "the week in Rapport"),
    ("comment            # post | comment", "comment"),
    ("t1_abc123        # the fullname you reply to", "t1_abc123"),
    ("Rapport #1 in local note takers", "Rapport #1 in local note takers"),  # a hash inside the text, not a comment
    ("# nothing but a comment", ""),
    ("", ""),
])
def test_an_inline_comment_ends_a_value_but_a_bare_hash_does_not(raw, want):
    assert rp.value(raw) == want


def test_a_title_with_a_colon_keeps_everything_after_it(outbox):
    """The real weekly update's title, which only the first `:` may split."""
    title = "This week in Rapport: Ask your library, summaries by source, and an MCP server"
    f = write(outbox, "post.md", f"kind: post\nsubreddit: rapport\ntitle: {title}")
    _, _, form = rp.prepare(f)
    assert form["title"] == title


# --- everything else a file can get wrong ---------------------------------------------------------


def test_a_comment_needs_a_fullname_parent(outbox):
    f = write(outbox, "reply.md", "kind: comment\nsubreddit: rapport\nparent: 12345")
    with pytest.raises(RuntimeError, match="parent"):
        rp.prepare(f)


def test_a_comment_with_a_parent_is_prepared(outbox):
    f = write(outbox, "reply.md", "kind: comment\nsubreddit: rapport\nparent: t3_abc123  # the post")
    kind, api, form = rp.prepare(f)
    assert (kind, api) == ("comment", "/api/comment")
    assert form == {"thing_id": "t3_abc123", "text": "A body."}


def test_a_post_needs_a_title(outbox):
    f = write(outbox, "post.md", "kind: post\nsubreddit: rapport")
    with pytest.raises(RuntimeError, match="title"):
        rp.prepare(f)


def test_an_empty_body_is_refused(outbox):
    f = write(outbox, "post.md", "kind: post\nsubreddit: rapport\ntitle: Hello", body="\n")
    with pytest.raises(RuntimeError, match="empty body"):
        rp.prepare(f)


def test_an_unknown_kind_is_refused(outbox):
    f = write(outbox, "post.md", "kind: crosspost\nsubreddit: rapport\ntitle: Hello")
    with pytest.raises(RuntimeError, match="unknown kind"):
        rp.prepare(f)


def test_a_file_without_frontmatter_is_refused(outbox):
    (outbox / "post.md").write_text("Just a body, no frontmatter.\n")
    with pytest.raises(ValueError, match="frontmatter"):
        rp.prepare(outbox / "post.md")


def test_a_long_title_is_cut_to_reddits_limit(outbox):
    f = write(outbox, "post.md", "kind: post\nsubreddit: rapport\ntitle: " + "x" * 400)
    _, _, form = rp.prepare(f)
    assert len(form["title"]) == 300


# --- the script itself -----------------------------------------------------------------------------


def run(*args, **kw):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, timeout=60, **kw)


def test_the_script_runs():
    """`--help` must actually print: a script without an entry point exits 0 saying nothing, which is how
    scripts/e2e.py silently tested nothing for two days."""
    p = run("--help")
    assert p.returncode == 0, p.stderr
    assert "--dry-run" in p.stdout


def test_a_dry_run_posts_nothing_moves_nothing_and_needs_no_credentials(outbox):
    """No REDDIT_* secrets in this environment, so a run that reached `token()` would fail; this one must
    not, and the file must still be in the outbox afterwards."""
    write(outbox, "post.md", "kind: post\nsubreddit: rapport\ntitle: the week in Rapport")
    p = run("--outbox", str(outbox), "--dry-run")
    assert p.returncode == 0, p.stderr
    assert "would post post.md: post" in p.stdout
    assert (outbox / "post.md").exists()
    assert not (outbox.parent / "sent").exists() and not (outbox.parent / "failed").exists()


def test_a_dry_run_reports_a_file_it_would_refuse(outbox):
    write(outbox, "post.md", "kind: post\nsubreddit: r/elsewhere\ntitle: Hello")
    p = run("--outbox", str(outbox), "--dry-run")
    assert p.returncode == 1
    assert "would fail post.md" in p.stderr and "not allowed" in p.stderr


def test_an_empty_outbox_is_not_a_failure(outbox):
    p = run("--outbox", str(outbox), "--dry-run")
    assert p.returncode == 0 and "outbox empty" in p.stdout


def test_the_real_outbox_and_the_file_waiting_to_be_resent_would_pass():
    """sprint/reddit/failed/2026-09-14-weekly-update.md is the post that hit #16. Whatever is queued now,
    and that file with the error line the failure added, must survive the check that refused it."""
    for path in sorted((ROOT / "sprint/reddit/outbox").glob("*.md")):
        if path.name != "README.md":
            rp.prepare(path)
    stale = ROOT / "sprint/reddit/failed/2026-09-14-weekly-update.md"
    if stale.exists():
        kind, _, form = rp.prepare(stale)
        assert kind == "post" and form["sr"] == "rapport"
        assert form["title"].startswith("This week in Rapport")
