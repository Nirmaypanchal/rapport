# Patterns that work in this codebase (Last verified: 2026-09-10, Build run "Ask your library")

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

## Packaging

- Anything read from disk at runtime must be added to `desktop/sidecar/rapport-core.spec` as `datas` (that is how
  `rapport/templates` got there). Plain Python modules need nothing, even when imported inside a function —
  PyInstaller sees those.
