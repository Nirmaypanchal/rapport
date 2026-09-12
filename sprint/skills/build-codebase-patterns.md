# Patterns that work in this codebase (Last verified: 2026-09-12, Build run "file each escalation once")

Read before writing code. These are things the codebase already decided; following them keeps a diff small and reviewable.

## Backend

- **A feature that has retrieval or prompt logic gets its own module** in `rapport/` with the pure parts at the top
  (`keywords`, `pick_hits`, `build_user`, `cited` in `ask.py`). Everything above the model call is then testable on
  Linux, which is where the Build agent runs. Only the last function touches the model.
- **The model is reached through `summarize.chat(provider, model, system, user)`**, and the pair comes from
  `resolve_provider(settings.summary_provider, settings.summary_model or None)`, which returns `None` when summaries
  are off or nothing is installed. Never import `mlx_lm` at module level: it does not exist on Linux.
- **A missing model is a state, not an error.** Return what you do have (the excerpts, the transcript) with a
  `reason` field saying why the model part is missing, and let the UI say it. `POST /api/ask` never 503s.
- **SQLite only, no ORM.** New columns go in `Database._migrate_columns` (add-only, guarded by `PRAGMA table_info`).
  New queries are methods on `Database` so tests can call them without the API.
- **FTS5 quoting**: every term is wrapped in `"…"` before it reaches `MATCH`, because raw punctuation is a syntax
  error there. A token that tokenizes to nothing (`"?"`) is also an error, so strip non-word tokens before you get
  that far. Terms joined by a space are AND; joined by ` OR ` they are OR (`db.search(..., match="any")`).
- **Routes stay a few lines**: validate, call a module, return. Heavy imports go inside the function body.

## A second way in (MCP, and anything else that is not HTTP)

- `rapport/mcp.py` talks JSON-RPC over stdio and opens SQLite directly — no port, no token, no running app. If you
  add another entry point, copy that shape: `Database(root / "library.sqlite")` and **refuse a folder that has no
  `library.sqlite`**, because `Database()` and `Library()` both happily create an empty one, so a typo'd path would
  silently serve nothing instead of failing.
- **Nothing but protocol on stdout.** `print(..., file=sys.stderr)` for anything else, and flush after every message
  (`stdout.write(json.dumps(msg) + "\n"); stdout.flush()`) — PyInstaller's stdout is block-buffered, so without the
  flush a frozen server hangs with the answer still in the buffer.
- A tool is an entry in `TOOLS` (name, description, JSON Schema) plus a `tool_*` in `HANDLERS`; a test asserts the
  two sets are equal, so neither can drift. Handlers take `(db, args)`, return a plain dict and raise `ToolError`
  for anything the caller got wrong — the model reads that and corrects itself, where a protocol error just breaks.
- **Clamp, don't refuse**, what is only a size (`limit=9999` → the maximum). Refuse what is meaningfully wrong
  (`to_sec` before `from_sec`).
- Test a protocol by driving it, not only by calling the handlers: `mcp.serve(db, io.StringIO(lines), out)` runs the
  real loop, and one test then covers framing, a parse error, a notification that must get no reply, and the rule
  that a message never spans two lines. Then run it for real once over a pipe (`printf '%s\n' … | python -m
  rapport.mcp --library /tmp/lib`) — that is what catches what the unit tests share your assumptions about.
- **Assert read-only if you claim read-only**: snapshot every table (`SELECT * FROM` each name in `sqlite_master`),
  run every tool, compare. Do not compare the file bytes — WAL means a write may not touch `library.sqlite` at all.

## Frontend

- Read two or three neighbouring components first. The vocabulary is small and repeats: `rounded-lg border
  border-hairline bg-surface px-5 py-4` for a card, `border-dashed` for an empty or explanatory state,
  `.eyebrow` for a section label, `.tc` for anything monospaced or numeric, `.blink` + `bg-signal` for "working",
  `text-clip` for failure, `speakerStyle()` + `.speaker` + `var(--c)` for anything that belongs to a person.
- **Shared renderers live in `frontend/src/components/`**: `markdown.tsx` (the small Markdown subset the local
  models are asked for) and `snippet.tsx` (the `[[…]]` marks SQLite puts in a search snippet). Both were duplicated
  in two features before; if you need a third copy, move it here instead.
- **Base UI tabs keep panel state with `keepMounted`** on `TabsContent`. Without it, switching tabs throws the
  panel's state away — an answer the user waited a minute for. With it, don't use `autoFocus` in a hidden panel:
  pass the active tab down and focus with a ref in an effect.
- React 19: `ref` is a plain prop, and the shadcn `Input` forwards it (`React.ComponentProps<"input">`).
- `useSearchParams()` needs the page's existing Suspense boundary; keep it in a component under the same page.

## Tests

- `tests/conftest.py` gives you `library` (a scratch folder, `summary_provider` already `"off"`) and `db`.
  A test that wants the no-model path gets it for free.
- Monkeypatch the model at the module that imported it: `monkeypatch.setattr("rapport.ask.chat", …)`, not
  `rapport.summarize.chat`.
- **Gotcha**: `db.set_speaker_person()` updates a `recording_speakers` row and silently does nothing if there is
  none. `replace_segments()` does not create speaker rows. To give a segment a named person in a test, call
  `db.replace_speakers(rid, [{"label": "SPEAKER_01", "person_id": pid, "speaking_sec": 9}])`.
- 20 new tests cost about 0.5 s. `scripts/test-light.sh` builds `.venv-light` on the first run only.

## The sprint's own automation (`.github/workflows/`)

- **The merge bot can merge a pull request that touches `.github/workflows/`.** Verified 2026-09-12: #11 changed
  `needs-human.yml` and `sprint-merge` squash-merged it unattended, and pushing the branch from a cloud agent was
  accepted too. The backlog carried a warning that this might be refused; it was a guess, and it was wrong. Fix
  workflows like any other code.
- **Logic in a workflow is untested logic.** Put the decision in `scripts/<thing>.py` (stdlib only, a `main()`, a
  `--dry-run`) and leave the YAML as checkout plus one `run:` line that passes `GH_TOKEN`. Then `tests/` can cover
  it, which is the difference between "#3 and #6 are the same request" being caught by CI and being caught by a
  human three weeks later. `scripts/needs_human_issues.py` is the shape to copy.
- **Never ask the GitHub *search* index whether something exists.** `gh issue list --search '"<title>" in:title'`
  is fuzzy and eventually consistent: on 2026-09-09 it found a two-and-a-half-hour-old issue for one file and
  missed one of the same age for another. Use `gh issue list --label … --state all --json …` (the list API is
  immediate and exact) and match in your own code, on a marker you wrote (`<!-- needs-human-file: … -->`), not on
  text a human may edit.
- `--state all`: a closed issue still means "already filed". Anything that files-once must look at closed ones too,
  or it re-files everything the owner has just finished.
- A guard test is cheap and stops the regression coming back through the back door:
  `assert "--search" not in WORKFLOW.read_text()`.
- Job logs are readable long after the fact and are the fastest way to find out what a workflow actually did —
  list the run's jobs, then read the job's log. That is how the #3/#6 cause was pinned down rather than guessed.

## Packaging

- Anything read from disk at runtime must be added to `desktop/sidecar/rapport-core.spec` as `datas` (that is how
  `rapport/templates` got there). Plain Python modules need nothing, even when imported inside a function —
  PyInstaller sees those.
