# FAQ

**Is it really free?**
Yes. MIT licensed, no tiers, no trial. If you want to support the project, contribute code, docs or a device you own.

**Does anything get uploaded?**
No. See [privacy.md](privacy.md) for the complete list of network calls (model downloads and the connectors you enable).

**Which Macs work?**
Apple silicon (M1 and later), macOS 14 or newer. Intel Macs aren't supported because transcription runs on MLX.

**Windows or Linux?**
Not yet. The pipeline could run on CUDA with faster-whisper; it's a good contribution if you want it.

**How accurate is the transcription?**
Whisper large-v3-turbo is close to the best available for most languages. Clean lavalier or headset audio is near-perfect;
crowded rooms and heavy accents degrade like every system. You can pick a larger or smaller Whisper model in Settings.

**Which languages?**
Over 100, auto-detected per recording. Set a fixed language in Settings if detection guesses wrong on short clips.

**How fast is it?**
About a minute for a 3-minute recording on an M1 Pro; 15 to 20 minutes for an hour. Processing runs in the background and
shows progress; the app stays usable.

**How does it know who's speaking?**
Voice activity detection, voice embeddings and clustering find the speakers in one recording; each speaker's voice fingerprint
is then matched against everyone heard before. [How it works](how-it-works.md) has the detail.

**It got a speaker wrong.**
Click the speaker's name on that turn and pick the right person, or split the turn at a word. Rename a person once and it applies
everywhere. If matching drifted badly, People → Reset speakers re-matches from the stored fingerprints in seconds.

**Why does Voice Memos need Full Disk Access?**
Apple stores memos in a protected folder and offers no narrower permission. Rapport only reads there. The alternative is
dragging memos out of the Voice Memos window onto Rapport.

**Does it delete files from my mic?**
Not unless you switch on "Clear the mic after import" in Settings, and then only after the copy is verified byte-for-byte.

**Which summary models can I use?**
Anything in Ollama (Rapport uses whatever is running), or the built-in Qwen2.5-3B on MLX. Change it in Settings.

**Can I use my own LLM or Claude on my library?**
Yes. Rapport ships an MCP server, so Claude, Cursor or any MCP client can search your recordings and read transcripts,
summaries and people — locally, read-only, with no key and no network. See [integrations.md](integrations.md#mcp-server-your-recordings-inside-claude-cursor-or-any-mcp-client).
Letting an assistant write back is the next step. Everything is also in SQLite and plain files, so scripts already work.

**How big does the library get?**
Originals dominate. DJI Mic files are ~700 MB per hour (32-bit float WAV); Voice Memos ~1 MB per minute. Transcripts are tiny.

**Can I move the library or back it up?**
It's one folder. Copy it anywhere; point Rapport at it with `RAPPORT_LIBRARY=/path`.

**Is the Mac app signed?**
Not yet; right-click → Open on first launch. Signing and notarization are planned once there's a Developer ID.

**Where do I ask something else?**
[Discussions](https://github.com/Nirmaypanchal/rapport/discussions).
