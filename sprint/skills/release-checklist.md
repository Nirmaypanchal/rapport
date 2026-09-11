# Release checklist (Last verified: 2026-09-11, first Release run)

- **The nightly gate is literal, not "root cause fixed."** `sprint/agents/release.md` step 1 requires the *newest*
  `sprint/log/*-nightly.md` to report the end-to-end test passing before tagging. If the newest one reports FAIL,
  don't release even when the cause is already fixed and merged on `main` — a fresh nightly run is the only thing
  that has ever caught a real pipeline bug (the harness's missing `__main__` guard shipped past two macOS CI runs
  and several agent runs undetected; only the nightly script running for real found it). CI's `backend` job on
  `macos-14` runs the pytest suite on real Apple silicon, but it does not run `scripts/e2e.py`, so it cannot stand
  in for a nightly pass. If a brand-new subsystem (like the MCP server) has never been touched by nightly, that's
  a real gap worth naming even when everything else is green.
- **`site/index.html` is safe to edit by hand for copy fixes.** The animation JS at the bottom selects children
  generically (e.g. `const chatEls=$$("#chat > *")`, `$$("#memo .memoline")`) rather than keying off specific text,
  so rewording or swapping the content of existing `<div class="msg">`/`<div class="tool">` elements inside a
  `.card` doesn't require touching the `<script>` block, as long as the element count/classes stay compatible with
  what the animation loop expects. Don't touch the huge single-line `<style>` (~line 6-10) or `<script>` blocks
  unless the change requires it. Sanity-check afterwards with a lenient parse:
  `python3 -c "from html.parser import HTMLParser; HTMLParser().feed(open('site/index.html').read())"` (won't
  catch everything, but catches gross breakage).
- **A "coming next" pill (`<span class="pill soon tag">`) left on a shipped feature is a real bug**, not a nitpick —
  it tells users a shipped thing hasn't shipped. Grep `coming next` across `site/index.html` every release run and
  check each hit against `docs/roadmap.md`'s Done section.
- **`docs/comparison.md` doesn't get touched by Build**, only by whoever remembers it exists — it's easy for a new
  shipped feature to go two releases without a row there. Check it every run against what's newly Done.
