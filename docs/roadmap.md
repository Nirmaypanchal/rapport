# Roadmap

Rapport already holds what was said. The next steps make it remember who it was said with, and let the tools you already use
read from it. Everything here stays local and free. Order is a guess; issues and PRs change it.

## Next

- **People memory.** The small things people tell you (a daughter starting school, a marathon in October, a move to Lisbon),
  extracted by the local model, filed under the person, kept with the date and the recording it came from.
- **Reminders that know why.** "Ask Sam how the marathon went", on your calendar, built from people memory.
- **MCP server.** Claude, ChatGPT, Cursor and any MCP client can search recordings, read transcripts and summaries, and write
  summaries, tags or people notes back. Runs inside the local backend; nothing new leaves the Mac.
- **Signed, notarized releases** with an auto-updater, and a Homebrew cask.
- **Templates you can edit in the app**, stored in the library folder instead of inside the app bundle.

## Later

- Calendar and contacts matching: recordings attached to the meeting they came from, people matched to contacts.
- Zoom and Google Meet local recordings, Otter and Plaud connectors, Obsidian and Notion write-back.
- Omi BLE streaming and other wearables.
- iPhone companion (Tauri mobile) for recording and browsing, syncing to the Mac, not a server.
- Smaller bundle: the frozen backend is 1.3 GB, mostly torch; moving the speaker engine to MLX would roughly halve it.
- Windows and Linux via a CUDA/CPU backend.

## Done

- Import from DJI Mic, USB recorders, microphones and Bluetooth, Voice Memos, Omi, Granola, Notion, cloud folders, files.
- On-device transcription, speaker detection, cross-recording speaker recognition, in-place corrections.
- Local summaries (Ollama/MLX), search, skip silences, exports.
- Native macOS app with a separate worker process and progress reporting.
- Summary templates: meeting notes, interview, lecture, sales call, journal or your own prompt, per recording.
- Ask your library: a question answered from your transcripts, with every claim linked to the moment it came from.
