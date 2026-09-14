# Competitors and adjacent products

Kept by the Research agent. Each entry: what they ship, what users praise, what users complain about, what it means for
Rapport. Cite sources with dates. `docs/comparison.md` is the public, shorter version of this file; keep them consistent.

## Watch list

| Product | Type | Why we watch it |
|---|---|---|
| MacWhisper | Mac app, one-time price, local Whisper | Closest local competitor; strong on formats, batch, dictation; weak on cross-recording people, library |
| Superwhisper | Mac app, dictation focus | Sets the bar for on-device speed and UX polish |
| Granola | Mac/Windows meeting notes, cloud LLM | Best-in-class notes UX and templates; no local option; no speaker library |
| Otter, Fireflies, Fathom | Cloud meeting bots | What "AI note taker" means to most searchers; the price and privacy pain we solve |
| Plaud, Limitless, Omi, Pocket | Hardware recorders with subscriptions | Their users own lots of audio and want to keep it; import path for us |
| Notion AI Meeting Notes, Apple Notes call recording | Bundled features | Free-ish defaults that shape expectations |
| Whisper.cpp, faster-whisper, WhisperKit | Engines | Speed and accuracy baselines; possible future backends |
| Note67 | Mac/Windows app, open source, local (Whisper + Ollama) | Architecturally closest thing to Rapport that isn't Rapport; added 2026-09-14, see below |

## Notes

### 2026-09-14

- **MacWhisper** — no new changelog found since MacWhisper 11 (transcript-view redesign). Still explicitly a
  file/batch transcriber, not live-meeting capture, per reviewers. No change to how we compare. [MacWhisper 11 press
  release](https://macwhisper.pressdeck.io/press-releases/macwhisper-11-released), [review](https://lumevoice.com/blog/macwhisper-review-2026/)
- **Superwhisper** — shipped v2.18.0 with **S1-mini**, an on-device LLM that cleans up dictation with tone control,
  fully local; all local Whisper models are now free on Mac. Commoditizes "free local transcription," which is not
  where Rapport competes (diarization, cross-recording people, Ask, MCP are). Reviewers separately flag default
  audio retention with no opt-out and plaintext API key storage, at $249 lifetime. [changelog](https://superwhisper.com/changelog),
  [review](https://www.getvoibe.com/blog/superwhisper-alternatives/)
- **Granola** — repositioning from "notetaker" to "enterprise AI context layer": new **Spaces** (team workspaces)
  and its own **MCP server** feeding meeting data to Claude/ChatGPT; new Business tier at $14/user/mo replaces the
  old Pro tier. Rapport already ships an MCP server (2026-09-11) — Granola making MCP a headline feature is reason to
  say so more loudly, not to build anything new. Silent capture failures remain the top complaint
  ([anarlog.so](https://anarlog.so/blog/granola-ai-complaints/)); diarization past two speakers still degrades to a
  wall of text. [SaaSworthy](https://www.saasworthy.com/product/granola-software)
- **Otter, Fireflies, Fathom** — Otter's free tier added its own MCP server and multi-language support; 30-minute
  meeting cap remains on the free tier (a real gap next to a local tool with no caps at all). Fireflies gates AI
  features (summaries, Q&A) behind monthly "AI credits" with reported $15–50/mo overages even on paid tiers — direct
  contrast with unlimited local Ask. Fathom 3.0 (Apr 2026) went bot-free (no visible meeting-bot participant), which
  is the capture model Rapport already has. Otter is in litigation over its bot's recording practices (wiretap/CIPA/
  biometric claims proceeding to discovery, 2026-08-13); Fireflies faces four BIPA voiceprint suits since Dec 2025.
  Treat the legal claims as reported, not verified against filings. [Claap](https://www.claap.io/blog/otter-pricing),
  [UC Today](https://www.uctoday.com/security-compliance-risk/otter-ai-on-trial-and-the-ai-notetaker-industry-with-it/),
  [Workplace Privacy Report](https://www.workplaceprivacyreport.com/2026/04/articles/artificial-intelligence/ai-meeting-assistants-and-biometric-privacy-governance-lessons-from-the-fireflies-ai-lawsuit/)
- **Plaud, Limitless, Omi** — Plaud shipped NotePin S (CES 2026) plus a Plaud Desktop app and a team tier, encroaching
  on desktop note-taking. Omi moved from no-subscription to tiered plans gating transcription capacity. **Limitless
  was acquired by Meta in Dec 2025**: pendant sales and the Rewind app stopped, EU/UK users lost access, users lost
  HIPAA protection. All three moves point the same way: hardware vendors adding paywalls or vanishing outright, which
  is the strongest current argument for free, local, MIT-licensed software. [pastok.com](https://pastok.com/blog/best-ai-wearables)
- **Notion AI Meeting Notes** — added consent-control policies, org-wide custom summary instructions, and (Jul 2026)
  speaker identification from the active microphone signal plus post-meeting Custom Agents. Still has the same
  "wall of text past two speakers" complaint as Granola. [tldv.io review](https://tldv.io/blog/notion-ai-meeting-notes-review/)
- **Whisper engines** — `parakeet-mlx` (NVIDIA's Parakeet transducer on Apple silicon) has a Feb 2026 release and a
  Jul 2026 M5 Max benchmark claiming lower WER and latency than Whisper large-v3 on clean English streaming, less
  compute. Separately, Argmax shipped **WhisperKit + SpeakerKit (pyannote diarization) + TTSKit as one MIT Swift
  package (v1.0.0, May 2026)** — notable because SpeakerKit does the same job as Rapport's built-in diarizer, but
  bundled for Swift, not Python. Sized in `sprint/research/trends.md`; the Swift point in particular conflicts with
  the "Python backend" architecture decision and needs a real decision, not a quiet adoption.
- **Note67** (new to the watch list) — open-source, local-first Mac/Windows meeting notetaker (Whisper + Ollama, mic
  + system-audio speaker separation), launched on Hacker News pitched as an "Otter/Granola replacement." The closest
  thing to Rapport that isn't Rapport. Worth a look at its issue tracker and HN thread each week for feature gaps and
  what its users ask for that ours haven't yet. [HN thread](https://news.ycombinator.com/item?id=46435651),
  [github.com/ZapYap-com/note67](https://github.com/ZapYap-com/note67)
