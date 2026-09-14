# Trends and opportunities

Kept by the Research agent. New models, engines, APIs and market shifts Rapport can capitalize on. Dated entry per
trend: the evidence, the concrete move, a size. Turn the best one or two into backlog items each run; the rest wait.

## Entries

### 2026-09-14

- **Parakeet on MLX is a real alternative engine, not yet a proven replacement.** `parakeet-mlx` runs NVIDIA's
  Parakeet transducer on Apple silicon; a Jul 2026 M5 Max benchmark claims lower WER and lower latency than Whisper
  large-v3 on clean English, and it streams tokens as audio arrives, which Whisper cannot.
  [benchmark](https://contracollective.com/blog/local-speech-to-text-whisper-parakeet-mlx-m5-max-2026),
  [WhisperKit → Parakeet piece](https://macparakeet.com/blog/whisper-to-parakeet-neural-engine/). **Sizing** (this
  was queued from the week-37 retro): a measured comparison against Whisper on the owner's own Mac is **M** — not a
  swap, an evaluation, because every number above is someone else's benchmark on someone else's hardware and Rapport
  has never run Parakeet at all. Streaming is the interesting part (it is the only realistic route to "real-time
  captions" in Later), but a streaming *engine* is not a streaming *feature* — the pipeline, diarization and UI would
  all need to change to use it. Kept in `backlog.md` under Next at M, unchanged in kind, now sized.
- **Argmax's WhisperKit now ships diarization in the same Swift package (SpeakerKit), and that is a bigger question
  than an engine swap.** `WhisperKit` + `SpeakerKit` (pyannote-based) + `TTSKit` shipped as one MIT Swift SDK
  (v1.0.0, May 2026) with Swift 6 concurrency. Rapport's diarizer is exactly the kind of thing SpeakerKit replaces —
  but Rapport's backend is Python (FastAPI, no ORM), and that is a named architecture decision
  (`sprint/decisions.md`, "Keep the architecture" in `AGENTS.md`), not an oversight. Adopting a Swift-only SDK for
  one piece of a Python pipeline is either a rewrite of that piece into a separate Swift helper process (real
  complexity: another binary, another IPC boundary) or a reason to reconsider the backend language, and both of
  those are calls for a decision, not a Ready backlog item. **Not promoted to the backlog.** Flagged here and in
  `messages.md` for the Retrospective and, if it goes further, the owner — this is a "worth a look," not a "worth
  building." [github.com/argmaxinc/WhisperKit](https://github.com/argmaxinc/WhisperKit)
- **16 GB Macs have better local-LLM options than when "Ask your library" shipped.** Qwen3 14B (Q4_K_M, ~8.5 GB) and
  Gemma 3/4 12B are reported as the current sweet spot for on-device summarization and Q&A quality at that memory
  budget. Rapport does not pick a model for the user today — `summarize.chat()` calls whatever Ollama or MLX model
  the user already has configured — so this is not a code change, it is documentation: `docs/getting-started.md` and
  any "which model should I pull" guidance should name a current good default instead of staying silent or naming
  something older. **Size: S**, a docs task, not on the code backlog. Left for whoever next touches
  `docs/getting-started.md` (Build or Release) — noted in `messages.md` rather than promoted, since it touches no
  acceptance criteria a test could check.
- **Apple's Foundation Models framework has grown a third-party model surface, per WWDC26 materials** — session
  content describes opening the on-device model to third-party providers and adding token-counting and custom
  transcript-segment APIs in a 26.4-era release. If accurate, this could let Rapport offer a zero-download local
  model option on recent macOS, alongside Ollama and MLX, through the same `summarize.resolve_provider()` seam that
  already picks between the two. **This is the least verified claim in this file** — it comes from search results
  describing a developer session, not from reading Apple's documentation directly, and I have no way to check macOS
  version availability or the actual API shape from this Linux session. **Not promoted to the backlog** for that
  reason; added to Next in `backlog.md` as a spec question rather than a Ready item, so Build does not start
  building against an API I have not confirmed exists in the form described. [WWDC26 session, reported](https://developer.apple.com/videos/play/wwdc2026/241/)
- **Displaced Limitless users and Otter/Fireflies' legal exposure are a live marketing opportunity, not a product
  one.** See `sprint/research/feedback.md` and `sprint/research/competitors.md` for the sourcing. No backlog item —
  this is positioning copy for Release/Community to use, and public posting is human-only per `AGENTS.md`. Left a
  note in `messages.md`.
- **No new recorder/wearable hardware changes the calculus this month.** Plaud's NotePin S (CES 2026) and a reported
  Meta pendant-in-development are the only launches found; neither undercuts Rapport's software-only, any-Mac-mic
  approach enough to need a reaction.

## Changelog

- 2026-09-14: created (first Research run to reach this step; the file was missing per the week-37 retro and
  `messages.md`).
