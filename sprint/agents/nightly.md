# Nightly on-device QA

Runs on the owner's Mac as a local scheduled task (its prompt is stored on that Mac, not here). It clones the repository to
`~/.rapport-sprint/repo`, checks out main, runs `uv sync`, builds the UI, runs `pytest`, runs `scripts/e2e.py` against the real
pipeline, builds the sidecar and the app, runs `scripts/e2e.py --core …` against the frozen core, writes
`sprint/log/YYYY-MM-DD-nightly.md`, and opens an issue labeled `sprint,bug` on failure. It never touches the owner's real library
or /Applications/Rapport.app. The other agents read its log: Build fixes failures first; Release does not ship on a red nightly.

## Changelog

- 2026-09-09: created (interactive bootstrap session).
