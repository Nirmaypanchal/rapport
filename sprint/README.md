# The sprint

Rapport is built by a continuous, mostly autonomous product sprint. This folder is its shared memory: agents and
humans read and write the same files. Everything is plain Markdown so anyone can follow along.

| File | What it is |
|---|---|
| [backlog.md](backlog.md) | The board. Ordered. "Ready" items are specified well enough to build in one run. |
| [decisions.md](decisions.md) | Product and technical decisions with the reason, newest first. Read before overturning one. |
| [research/](research/) | Market notes, competitor teardowns, user feedback digests. Dated, with sources. |
| [log/](log/) | One entry per agent run. The memory of the next run. |
| [needs-human/](needs-human/) | Escalations. A GitHub Action turns each new file into an issue for the owner. |
| [marketing/](marketing/) | Drafts of announcements, posts, and release notes for the owner to publish. |

## How the loop runs

1. **Research & planning (Mondays).** Reads open issues, discussions and PR comments; checks what MacWhisper,
   Superwhisper, Granola, Otter, Plaud, Notion AI Meeting Notes, Apple's built-in call recording, Limitless and Omi
   shipped; looks at what people ask for in those communities. Updates `research/`, reprioritizes `backlog.md`,
   promotes items to Ready with a written spec, keeps `docs/roadmap.md` and `docs/comparison.md` truthful.
2. **Build (daily).** Takes the first Ready item, designs it within the Cue Sheet design language, implements backend,
   UI and tests on a `sprint/<slug>` branch, and pushes. CI runs; the `sprint-merge` workflow opens and merges the PR
   when green. The agent also fixes any red PRs from earlier runs first.
3. **Nightly on-device test.** On the owner's Mac: pull `main`, build the sidecar and app, run `scripts/e2e.py` against
   the real pipeline and the real bundle, log the result, open an issue on failure.
4. **Release & marketing (Fridays).** If `main` has user-visible changes since the last tag: bump the version, write the
   changelog, tag. CI builds the DMG and publishes the GitHub Release. Then refresh docs and the landing page,
   and draft posts in `marketing/` for the owner.

Rules for all of the above are in [AGENTS.md](../AGENTS.md).

## Backlog conventions

- Sections: **Now** (Ready, ordered), **Next** (needs a spec), **Later** (ideas), **Done** (with the date and link).
- One line per item: `- [ ] **Title** — one-sentence outcome. _Why:_ evidence (issue #, research note). _Size:_ S/M/L.`
- A Ready item has a spec block underneath: user story, acceptance criteria, UI notes, files likely touched.
- Move, don't delete. Done items keep their link.
