# Decide on Apple Developer signing: add the certificate as repository secrets, or tell us to ship unsigned

**Why:** "Signed, notarized releases" has been the single item at the top of `sprint/backlog.md` under **Now** all week,
blocked on credentials only you can provide — and until today nobody had actually asked you for them. The item said
"see `needs-human/`" and pointed at a file that did not exist, so the block was recorded in the backlog and never
escalated. That is a week of the board's top item waiting on a request that was never sent. It also costs money (an
Apple Developer Program membership is about $99/year), which makes it yours to decide either way: agents do not spend
your money and do not sign anything.

This matters more than it did on Monday. Without signing, every person who downloads the DMG gets macOS telling them
the app cannot be opened because the developer cannot be verified, and has to right-click → Open to get past it. For a
privacy-first note taker asking people to trust it with their recordings, that first impression is the worst possible
one. It is the biggest install-time drop-off any unsigned Mac app has.

**A decision either way unblocks us. We are not asking you to buy anything — we are asking you to choose.**

**What to do:** pick one.

**Option A — you have (or will get) an Apple Developer membership.** Add five repository secrets at
https://github.com/Nirmaypanchal/rapport/settings/secrets/actions:

1. `APPLE_CERTIFICATE` — your "Developer ID Application" certificate exported from Keychain Access as a `.p12`, then
   base64-encoded: `base64 -i certificate.p12 | pbcopy`
2. `APPLE_CERTIFICATE_PASSWORD` — the password you set when exporting the `.p12`
3. `APPLE_ID` — the Apple ID email of the developer account
4. `APPLE_TEAM_ID` — the 10-character team ID from https://developer.apple.com/account (Membership details)
5. `APPLE_APP_PASSWORD` — an app-specific password from https://account.apple.com → Sign-In and Security →
   App-Specific Passwords (**not** your Apple ID password)

Then reply on the issue saying they are in. The Build agent will make `release.yml` sign and notarize when all five are
present and skip cleanly when they are not, so nothing breaks for contributors without them.

**Option B — not now.** Say so on the issue. We will move the item from Now to Later, and instead ship unsigned with a
short, honest "first launch" section in `docs/getting-started.md` and on the landing page explaining the right-click →
Open step and why it appears. That is a smaller job than signing and it stops the top of the board being permanently
blocked.

**Blocked:** `sprint/backlog.md` → Now → "Signed, notarized releases" (M); and behind it in Next, "Auto-updater" (the
Tauri updater needs signed builds) and "Homebrew cask" (wants a signed release first).

**Not blocking this, but you are the only one who can do it, and it is worth doing in the same ten minutes:**
[#12](https://github.com/Nirmaypanchal/rapport/issues/12) — the nightly on-device QA task on your Mac has not run since
2026-09-10. It is the only thing in the whole loop that ever runs the real pipeline, it is what Release is holding the
v0.2.0 tag on, and everything shipped since 09-10 (Ask, the MCP server, the summary index) has never met a real model
on real hardware. That issue has the exact commands.

**One small thing we could not verify ourselves:** cloud routines can reportedly now be triggered by a GitHub event
rather than only a schedule. If that is true and available on your account, it would fix two structural problems at
once — a weekly Research agent that cannot keep a daily Build agent supplied, and a nightly whose silence nothing
notices. Worth a look next time you have the routine settings open. Not an ask, just a lead.
