# Roadmap

Rapport already holds what was said. The next steps make it remember who it was said with, and let the tools you already use
read from it. Everything here stays local and free. Order is a guess; issues and PRs change it.

## Next

- **People memory.** The small things people tell you (a daughter starting school, a marathon in October, a move to Lisbon),
  extracted by the local model, filed under the person, kept with the date and the recording it came from.
- **Reminders that know why.** "Ask Sam how the marathon went", on your calendar, built from people memory.
- **MCP write-back.** The read-only half has shipped (see Done); next an assistant can write a summary, a tag or a note
  back to a recording, with a confirmation in the app.
- **Signed, notarized releases** with an auto-updater, and a Homebrew cask.
- **Templates you can edit in the app**, stored in the library folder instead of inside the app bundle.
- **Zoom and Google Meet local recordings**, watched automatically like iCloud Drive or Dropbox today.
- **Obsidian and Markdown export**, one file per recording, so your library is never locked inside Rapport.

## Later

- Calendar and contacts matching: recordings attached to the meeting they came from, people matched to contacts.
- Otter and Plaud connectors, Notion write-back.
- Omi BLE streaming and other wearables.
- iPhone companion (Tauri mobile) for recording and browsing, syncing to the Mac, not a server.
- Smaller bundle: the frozen backend is 1.3 GB, mostly torch; moving the speaker engine to MLX would roughly halve it.
- Windows and Linux via a CUDA/CPU backend.

## Done

- Import from DJI Mic, USB recorders, microphones and Bluetooth, Voice Memos, Omi, Granola, Notion, cloud folders, files.
- On-device transcription, speaker detection, cross-recording speaker recognition, in-place corrections.
- Local summaries (Ollama/MLX), search, skip silences, exports.
- Native macOS app with a separate worker process and progress reporting.
- Summary templates: meeting notes, interview, lecture, sales call, journal or your own prompt, per recording or per
  source — a Granola sync and a voice memo on a walk can take different shapes without you picking each time. Sources
  are named by where a recording came from, so a watched iCloud Drive or Dropbox folder is set separately from any
  other folder you watch.
- Ask your library: a question answered from your transcripts, with every claim linked to the moment it came from,
  written as the model writes it.
- Search finds your summaries as well as your transcripts: the sentence that already answers the word you typed comes
  first, above the turns that led up to it.
- MCP server: Claude, Cursor and any MCP client can search your recordings, ask them a question, and read transcripts,
  summaries and people, read-only, on your Mac. See [integrations.md](integrations.md#mcp-server-your-recordings-inside-claude-cursor-or-any-mcp-client).
