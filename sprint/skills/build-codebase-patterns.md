# Patterns that work in this codebase (Last verified: 2026-09-18, Build)

Read before writing code. These are things the codebase already decided; following them keeps a diff small and reviewable.

The sprint's own workflows moved out of this file on 2026-09-13 into `all-sprint-automation.md`, so that every role
reads them and not only Build.

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
- **A second thing to search is a second FTS table, not a column.** `segments_fts` is external-content
  (`content='segments'`), so "which kind of thing is this hit" cannot live on it — summaries got their own
  `summary_chunks` table plus `summary_chunks_fts` and the same three triggers (`_ai`/`_au`/`_ad`). Copy that block
  verbatim; the delete trigger is the one people forget, and without it a deleted row stays findable forever.
- **Two bm25 rankings are not one ranking.** Scores over one-line turns and over summary blocks are not on the same
  scale, so merging them by score is a guess dressed up as a number. Give each index a budget instead and say why in
  the docstring (`ask.retrieve`: three summaries at most, one per recording, then moments fill the rest).
- **When a trigger cannot do the work, use the choke point instead of the callers.** Splitting Markdown into rows
  needs Python, so `db.index_summary()` is called from `insert_recording` and `update_recording` — the two functions
  every writer already goes through — rather than from the pipeline and the importer separately. Then add a backfill
  in `Database.__init__` (`WHERE … AND id NOT IN (SELECT recording_id FROM …)`) for rows written before the index
  existed: it costs one query that returns nothing on an indexed library, and it self-heals if anything ever drifts.

- **A chain of defaults is one function, and the UI reads it back from the API rather than re-deriving it.**
  `summarize.template_for()` resolves recording → source → Settings; the route hands the frontend the pieces
  (`by_source`, the resolved `default`) so `defaultTemplateFor()` in `lib/api.ts` is a lookup, not a second copy of
  the rules. Also: decide deliberately where a *stale* entry falls. `get_template` answers `DEFAULT_TEMPLATE` for an
  unknown id, which for a per-source override would quietly demote the default the user did choose — so
  `template_for` ignores it and falls through to that default instead. Validate on write too, but never rely on it:
  `settings.json` is a file a user can edit.
- **A settings value that is a map gets cleaned in the route**, next to the `•••` secret handling in `put_settings`,
  not in `Library.update_settings` (which is the plain dataclass writer every caller shares).

- **Two ways of delivering one answer share their decisions, not just their retrieval.** `ask()` returns the whole
  thing and `ask_stream()` yields it in pieces, but both go through `_prepare` (excerpts, provider, the skeleton),
  `_finish` (the text and which excerpts it cited) and `_failed` — and a test asserts the stream's final event
  *equals* what `ask()` returns for the same input. Without that, the panel and the MCP tool drift and nobody
  notices until one of them cites the wrong number.
- **A streamed route validates before the generator starts.** Once a `StreamingResponse` has begun there is no
  status code left to set, so `POST /api/ask` checks the empty question in the route body and raises `HTTPException`
  there; inside the generator it would have looked like a successful answer to nothing.
- **Newline-delimited JSON is only safe because `json.dumps` escapes newlines.** Model output is full of them (a
  bulleted answer is mostly newlines), and one raw newline splits an event in two and hands the client half an
  object. There is a test for it; add one to anything else that frames on `\n`.
- **Changing a route's response shape? Grep for the route string, not for the type.** `/api/search` went from a
  list to `{moments, summaries}`; `frontend/` catches that at `tsc`, but `scripts/e2e.py` calls the same route and
  is typechecked by nothing, and only the owner's Mac ever runs it — a stale reader there surfaces as a nightly
  failure days later with no obvious cause. `grep -rn "api/<route>"` across the repository, including `scripts/`
  and `docs/`, is the whole technique. (`rapport/mcp.py` is the reassuring case: it opens SQLite directly, so a
  route change never touches it.)
- **Two things fetched for one answer fail together or not at all.** Compute both inside the one `try` and
  return them in one expression, so a raising half cannot come back as the other half plus a missing key — which a
  UI renders as a confident empty result ("nothing in your summaries matched") rather than as the error it is.
  It also means the only way to reach that branch may be a monkeypatched raise: in `/api/search` every term is
  quoted before it reaches `MATCH`, and `""""`, `"*"`, `"?"` and `"NEAR"` all come back empty from SQLite rather
  than erroring, so there is no query a user can type that fails. Test the branch you have, not one you wish for.
- **A provider path you cannot run says so in its own docstring.** `_mlx_stream` has never executed anywhere —
  there is no Apple silicon in the cloud and the nightly has not run since 09-10 — so it reads both shapes
  `mlx_lm.stream_generate` is known to yield (a response object with `.text`, or the text itself) and the docstring
  names it as untested. Marking it beats pretending, and it tells the nightly where to look first.

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
- **When two lists show the same card, extract the card and pass the ornament as a prop.** The summary card lives in
  `summary-hit.tsx` and knows nothing about who is rendering it: Ask hands it a `badge` (the citation number) and a
  `dim` flag, Search hands it neither. The alternative — a `kind`/`mode` prop, or copying the classes — is how the
  two lists come to disagree about what a summary hit looks like. The signal that an extraction is right: the shared
  component has no conditional that names a caller.
- **`frontend/AGENTS.md` is generated, and its claim checks out.** `next dev` writes that block (verified 2026-09-18:
  `node_modules/next/dist/server/lib/generate-agent-files.js` and `node_modules/next/dist/docs/` both exist after
  `npm ci`). So read `node_modules/next/dist/docs/` before using a Next.js API you are recalling rather than reading,
  and commit the block with your work rather than trying to drop it from a diff.
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

## Packaging

- Anything read from disk at runtime must be added to `desktop/sidecar/rapport-core.spec` as `datas` (that is how
  `rapport/templates` got there). Plain Python modules need nothing, even when imported inside a function —
  PyInstaller sees those.
