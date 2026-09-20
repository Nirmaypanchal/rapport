# The routines the sprint runs on (Last verified: 2026-09-20, retro week 38)

Five of the six agents are **cloud routines**; the nightly is a **Desktop scheduled task** on the owner's Mac. Both are
configured at [claude.ai/code/routines](https://claude.ai/code/routines) (or `/schedule` in the CLI — not inside a cloud
session, where the command is unavailable). Source: [the routines docs](https://code.claude.com/docs/en/routines),
read 2026-09-20. This file is about the machinery the agents *run on*; `all-sprint-automation.md` is about the GitHub
workflows they *drive*.

## A routine can be triggered by more than a clock

Three trigger types, combinable on one routine:

- **Schedule** — what all six use today. Minimum interval one hour; runs may start a few minutes late (a consistent
  per-routine stagger).
- **GitHub event** — fires on **pull request** or **release** events (`created`, `published`, `edited`, `deleted` for
  releases; opened/closed/labelled/synchronized and the rest for PRs), with filters on author, title, body, base and head
  branch, labels, draft and merged. Needs the [Claude GitHub App](https://github.com/apps/claude) installed on the repo.
- **API** — a per-routine `/fire` endpoint called with a bearer token (`experimental-cc-routine-2026-04-01` beta header).
  An optional `text` field arrives wrapped in a `<routine-fire-payload>` block marked untrusted, so a prompt must
  explicitly opt in to acting on it.

**Two of these are aimed straight at problems this team has.** A `release.published` trigger on the Community routine
would post the announcement the moment a release exists, instead of the announcement waiting for the next daily run and
the run waiting for a tag. An API trigger would let the nightly on the owner's Mac `curl` the sprint awake when it
finishes or fails, rather than the loop inferring its state from the absence of a file. Neither is set up; both are one
form on the routines page. On the board and in `sprint/needs-human/2026-09-20-the-sprint-is-blocked-on-you.md`.

## Why a routine goes silent, and how to tell

This is the list to work through before escalating "it just stopped" again (eleven nights and no diagnosis, week 38):

1. **Green ≠ worked.** "A green status in the run list means the session started and exited without an infrastructure
   error. It does not mean the task in your prompt succeeded." Open the run and read the transcript.
2. **An expired GitHub connection pauses, then kills.** Runs are skipped for up to 72 hours; reconnect inside that window
   and the routine resumes by itself, after it the routine **turns off** and must be switched back on by hand.
3. **The daily run cap.** Routines have a per-account cap on runs started per day, on top of normal subscription limits.
   Past the cap, runs are simply rejected — invisible from inside the repository. Six routines a day is six against that
   cap. `claude.ai/settings/usage` shows what is left. One-off runs do not count against it.
4. **A paused subscription** puts every routine on hold.
5. `/schedule list` shows routines and their history, and `/schedule why did my <name> do nothing this morning?` reads a
   run's log and explains it (CLI v2.1.227+). Neither works from inside a cloud session.

## What a routine may write

Work is pushed to `claude/`-prefixed branches without question. A push to any other branch — which is what this project's
`sprint/<slug>` convention does — is checked first and **rejected** if the branch is protected, if someone else has an open
pull request from it, or if it carries commits authored by someone other than the account's owner. That is worth knowing
before anyone proposes protecting `main` or having two agents share a branch.

## Limits worth remembering

Routines are in research preview: shapes, caps and the API surface may change. They belong to one individual account, not
to a team, and everything they do through GitHub or a connector appears as that person — every commit in this repository
is the owner's identity, which is why the attribution lines and the sprint-bot signature matter.
