# Release checklist (Last verified: 2026-09-20, retro week 38)

- **The download button is the product.** `site/index.html` has three "Download for Mac" buttons and all three point at
  `https://github.com/Nirmaypanchal/rapport/releases`. With no tag ever cut, that page reads "There aren't any releases
  here yet" — which is what every visitor got for the whole of week 37, including the run that edited the copy around
  those buttons without following one. Open the link. A held tag is not free, and this is what it costs.
- **The nightly gate expires after seven silent days.** The gate exists to stop a bad build reaching users, not to make
  shipping conditional on a machine that has stopped answering. If the newest `sprint/log/*-nightly.md` is over a week
  old: macOS CI green on the exact commit + an open `needs-human` issue for the silent nightly + the release notes
  saying plainly that the end-to-end test has not run since `<date>` = you may tag a 0.x release. Full rule in
  `sprint/agents/release.md` step 1.
- **A nightly failure blocks while it stands, and a spent one does not.** This line used to read "the gate is literal,
  not root-cause-fixed" and told Release not to ship even when the cause was fixed and merged. Applied to the only
  nightly that has ever run — a *harness* bug (`scripts/e2e.py` had no `__main__` guard), fixed the next day in
  [#9](https://github.com/Nirmaypanchal/rapport/pull/9), regression-tested in `tests/test_e2e_harness.py`, in a log whose
  verdict on the product was "the real pipeline is fine" and which passed it twice — that rule held every release for
  twelve days and would have held them forever, because the newest nightly log can only change when the Mac runs again.
  A failure is **spent** when its cause is named, fixed by a merged commit, covered by a test, and the same log reports
  the product passing. Anything else — unknown cause, unfixed, untested, or in the product itself — blocks absolutely
  and no clock expires it.
- **Name what has never run on a Mac, every time you ship unverified.** CI's `backend` job on `macos-14` runs the whole
  pytest suite on real Apple silicon, which is more coverage than "unverified" suggests — but it does not run
  `scripts/e2e.py`, does not freeze the sidecar, and does not build the app. As of 2026-09-20 the things no Mac has ever
  executed are the MLX streaming path in Ask (#26), the MCP server against a real client (#10, #22), and the frozen
  bundle for anything after 0.1.0. List them in the release notes rather than writing one vague sentence.
- **`release.yml` has never run once.** The first tag is the first test of it. Budget the run for fixing it, and treat a
  published release with a `.dmg` attached — not the tag — as the thing that shipped.
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
