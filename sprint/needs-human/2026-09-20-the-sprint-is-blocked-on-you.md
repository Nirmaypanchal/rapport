# Ten minutes will unblock three weeks of work: four open asks, in the order that unblocks the most

**Why:** this is not a fifth ask. Four `needs-human` issues have been open for 7 to 11 days with no reply
([#3](https://github.com/Nirmaypanchal/rapport/issues/3), [#5](https://github.com/Nirmaypanchal/rapport/issues/5),
[#12](https://github.com/Nirmaypanchal/rapport/issues/12), [#14](https://github.com/Nirmaypanchal/rapport/issues/14)),
and the agents have been correctly re-verifying them rather than re-filing. What nobody has told you is the aggregate:
in week 38 the sprint merged **13 pull requests and shipped 9 user-visible features**, and not one of them has reached a
person. The repository has **1 star, 0 watchers, 0 forks**; `/releases` is empty, so all three "Download for Mac"
buttons on the landing page have led nowhere for 14 days; the on-device nightly has not run for 11 nights; and the
weekly update covering all nine features is sitting unposted for want of a Reddit credential.

The Retrospective removed the one blocker it could remove itself today: the release gate had an exception that could
never stop applying, so Release held the tag twice for a test failure that was fixed on 2026-09-11. That rule is fixed
(`sprint/decisions.md`, 2026-09-20), and **Release can tag a 0.2.0 on its next run without you**. Everything below still
needs you. If you only do one, do #1.

**What to do:**

1. **Get the nightly back (5 minutes) — [#12](https://github.com/Nirmaypanchal/rapport/issues/12).** It is a Desktop
   scheduled task on your Mac and has been silent since 2026-09-10. Nobody has diagnosed it; "start it again" is a retry,
   not a fix. Open the Claude Desktop app → **Code** → **Routines**, find the Rapport nightly task, and check, in order:
   1. Is it still **enabled**? (A routine whose GitHub connection expires skips runs for 72 hours and then switches
      *itself* off — reconnecting after that does not turn it back on.)
   2. Are there **runs that went green and did nothing**? A green status means the session started and exited, not that
      the task succeeded — open the newest run and read the transcript.
   3. Is your **GitHub connection** still live?
   4. Are you hitting the **daily routine run cap** or a subscription limit? Six routines a day count against it, and
      rejected runs are invisible from inside the repository. Check `claude.ai/settings/usage`.

   Then reply on #12 with **which of the four it was** — that is worth more than the restart, because it is the only way
   the next silence gets diagnosed in a minute instead of a fortnight. The watchdog will close #12 by itself once a
   nightly log lands.

2. **Reddit bot credentials (5 minutes) — [#3](https://github.com/Nirmaypanchal/rapport/issues/3).** Nine shipped
   features are queued in `sprint/reddit/failed/2026-09-14-weekly-update.md`. The posting script and workflow are
   verified working end to end (`#17` fixed the bug that would have refused r/rapport itself; the workflow now fails only
   with `Reddit credentials are not configured`). Add `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USERNAME`,
   `REDDIT_PASSWORD` as repository secrets and the queue drains on the next Community run. Exact steps are in
   `sprint/needs-human/2026-09-09-reddit-bot-credentials.md`.
   **Worth knowing before you spend the five minutes:** r/rapport has no audience yet, so this unblocks the channel, not
   the reach. If you would rather the sprint spoke somewhere else first, say so on #3 and we will draft it for you
   instead — public posting anywhere but r/rapport is yours by guardrail.

3. **Apple Developer signing — [#14](https://github.com/Nirmaypanchal/rapport/issues/14).** A decision, not a task, and
   it costs money, so it is yours either way: add the certificate as repository secrets, or reply "ship unsigned" and we
   will stop holding the item and write the right-click instructions into `docs/getting-started.md`. Either answer
   unblocks it; the silence is what does not. Unsigned 0.x releases are fine in the meantime.

4. **Reddit from the cloud — [#5](https://github.com/Nirmaypanchal/rapport/issues/5).** Lowest priority. Confirmed today
   that reddit.com is unreachable from the cloud environment by two independent methods, so Community cannot *read*
   r/rapport; posting is unaffected (it happens from a GitHub Action). Either widen the routine environment's network
   policy to allow `reddit.com`, or reply "listen elsewhere" and we will stop probing it.

**Optional, and genuinely useful (2 minutes each, at `claude.ai/code/routines`):** routines can now be triggered by
GitHub events and by an HTTP call, not only by a clock
([docs](https://code.claude.com/docs/en/routines)). Adding a **release** trigger to the Community routine would post the
announcement the moment a release is published, instead of it waiting for the next day's run. An **API** trigger would
let your Mac's nightly tell the sprint it finished, instead of the sprint inferring its state from a missing file. Notes
in `sprint/skills/all-routines.md`.

**Blocked:** the nightly (#12) blocks the on-device verification of all nine features shipped this week — the MLX
streaming path in Ask has never executed on any machine anywhere. #3 blocks every announcement the sprint has ever
written. #14 blocks **Signed, notarized releases** and, behind it, the auto-updater and the Homebrew cask. #5 blocks
Community's listening. Nothing here blocks the 0.2.0 release any more.
