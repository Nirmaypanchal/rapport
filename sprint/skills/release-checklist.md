# Release checklist (Last verified: 2026-09-13, retro week 37)

- **The download button is the product.** `site/index.html` has three "Download for Mac" buttons and all three point at
  `https://github.com/Nirmaypanchal/rapport/releases`. With no tag ever cut, that page reads "There aren't any releases
  here yet" — which is what every visitor got for the whole of week 37, including the run that edited the copy around
  those buttons without following one. Open the link. A held tag is not free, and this is what it costs.
- **The nightly gate expires after seven silent days.** The gate exists to stop a bad build reaching users, not to make
  shipping conditional on a machine that has stopped answering. If the newest `sprint/log/*-nightly.md` is over a week
  old: macOS CI green on the exact commit + an open `needs-human` issue for the silent nightly + the release notes
  saying plainly that the end-to-end test has not run since `<date>` = you may tag a 0.x release. A nightly that ran and
  **failed** is a different thing and still blocks absolutely. Full rule in `sprint/agents/release.md` step 1.
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
