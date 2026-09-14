# User feedback digest

Kept by the Research agent. Summaries of what people ask for in this repository's issues and discussions and in
public communities (Reddit r/macapps, r/productivity, Hacker News, MacWhisper and Granola communities, App Store reviews
of competitors). Quote sparingly; link the source; date every entry. Feed conclusions into `../backlog.md`.

## Themes so far

- From the owner's own use (2026-09-07 to 09): speakers get mixed up on short recordings; wanting to fix names in place;
  wanting Voice Memos and other recorders in one place; processing must not freeze the UI; progress must be visible.

## Entries

### 2026-09-14

**This repository has no external feedback yet.** Checked every open and closed issue (7 total), the PR history, issue
comments, and `https://github.com/Nirmaypanchal/rapport/discussions` (enabled, six empty categories). Every issue and
every comment was authored by `github-actions` or the owner's own account closing agent-filed escalations — zero
issues, comments or discussion posts from an outside GitHub user. Not a gap in our listening; a fact about a project
with no users yet. Nothing to answer, nothing to file. Re-check every run; the first real one matters.

Since there is no Rapport-specific feedback, the themes below are drawn from what people say about the products
Raport will be compared against — read as "what our first users will expect," not literal requests.

- **Silent capture failure is Granola's most-repeated complaint, not a missing feature.** "Open all day, produced
  notes for ~60% of calls"; a founder had two calls that looked recorded and weren't, no error shown.
  ([anarlog.so](https://anarlog.so/blog/granola-ai-complaints/)) *Implies:* Rapport's mic recording already shows a
  live pill and timer while recording (`sources-view.tsx` `MicPanel`), which Granola's cloud bot cannot promise — but
  nothing today would warn a user if the input device stopped delivering audio mid-recording. Added to Later below.
- **Diarization degrading into a wall of text past two speakers is a complaint on both Granola and Notion AI Meeting
  Notes, worded almost identically.** ([aitooldiscovery.com](https://www.aitooldiscovery.com/guides/granola-ai-reddit),
  [tldv.io](https://tldv.io/blog/notion-ai-meeting-notes-review/)) *Implies:* Rapport's speaker ID and cross-recording
  recognition are not a nice-to-have next to these two — they are a thing two well-funded competitors visibly cannot
  do. This is a comparison-page and marketing point, not a build item (`docs/comparison.md` already has the row; left
  a note for Release/Community in `messages.md`).
- **Superwhisper reviewers describe setup as "configuring a server," and flag that audio is retained by default with
  no opt-out and API keys stored in plaintext.** ($249 lifetime.) ([getvoibe.com](https://www.getvoibe.com/blog/superwhisper-alternatives/))
  *Implies:* two things worth checking rather than building — (a) our own onboarding should read as simpler than
  "configuring a server" by contrast, worth keeping in mind when Onboarding (Next) gets a spec; (b) audit Rapport's
  own key storage (`settings.json`) before someone writes the same review about us. Not urgent; nothing found wrong,
  just flagging the question.
- **The visible participant-list bot is a named complaint against Fathom** ("loud on pitch calls, board calls,
  interviews") **and Otter is mid-lawsuit** over exactly that pattern — a federal judge let wiretap, CIPA and Illinois
  biometric claims against Otter proceed to discovery on 2026-08-13.
  ([uctoday.com](https://www.uctoday.com/security-compliance-risk/otter-ai-on-trial-and-the-ai-notetaker-industry-with-it/),
  [recordinglaw.com](https://www.recordinglaw.com/news/otter-ai-wiretap-lawsuit-explained/),
  [anarlog.so](https://anarlog.so/blog/fathom-ai-complaints/)) Fireflies faces four parallel BIPA voiceprint suits
  since Dec 2025 over undisclosed retention and no consent from non-account-holder attendees.
  ([workplaceprivacyreport.com](https://www.workplaceprivacyreport.com/2026/04/articles/artificial-intelligence/ai-meeting-assistants-and-biometric-privacy-governance-lessons-from-the-fireflies-ai-lawsuit/))
  *Implies:* a genuine, verifiable-by-anyone positioning point — Rapport has no bot, no cloud voiceprint database,
  ever — but this is legal/marketing material, not a product decision I should act on unilaterally. Left for
  Release/Community in `messages.md`; not written into `docs/` myself beyond the one factual correction below.
  Treat the lawsuit and suit counts as claims from secondary sources, not verified against court filings.
- **MacWhisper reviewers redirect anyone wanting live meeting notes elsewhere** — it is a file/batch transcriber, not
  built for live capture. ([lumevoice.com](https://lumevoice.com/blog/macwhisper-review-2026/)) *Implies:* confirms
  Rapport's live-meeting-plus-summary scope is a different, less crowded lane than MacWhisper's rather than a
  head-on feature race. No action; supports the existing framing in `docs/comparison.md`.
- **Limitless was acquired by Meta in December 2025**: pendant sales stopped, the Rewind app shut down, EU/UK users
  cut off, and users lost HIPAA protections in the move.
  ([pastok.com](https://pastok.com/blog/best-ai-wearables)) *Implies:* a real, current pitch for local-first,
  MIT-licensed software — "the company can't be acquired out from under your data" — aimed at displaced Limitless
  users. Marketing material, not a build item; flagged for Release/Community.
- **A direct open-source competitor exists: Note67**, a local-first macOS/Windows meeting notetaker (Whisper +
  Ollama, mic + system-audio speaker separation, free, no accounts), launched on Hacker News pitched as an
  "Otter/Granola replacement." ([news.ycombinator.com](https://news.ycombinator.com/item?id=46435651),
  [github.com/ZapYap-com/note67](https://github.com/ZapYap-com/note67)) *Implies:* added to the watch list in
  `sprint/research/competitors.md` — architecturally close enough to be worth checking for feature gaps and
  community reaction each week, not a one-time read.
