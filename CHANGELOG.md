# Changelog

All notable changes to Rapport. The format follows Keep a Changelog; versions follow semver.

## [Unreleased]

### Added

- **Sources are named by where a recording came from.** A watched folder inside iCloud Drive, Dropbox, Google Drive
  or OneDrive is now listed as that service rather than as a generic "watched folder", everywhere you pick a source:
  Settings → Template by source, the counts on the Sources page, and a recording's Details panel. Three watched
  folders used to arrive as one indistinguishable source, so "a template for my iCloud recorder" could not be
  expressed; now it can. Nothing about how a file is imported changed, and existing settings keep working.

- **Search finds your summaries, not just your transcripts.** Typing "pricing" used to search the words people said
  and miss the summary that states the answer in one sentence. Summary hits now lead the results, each with a
  **Summary** badge and the block's heading instead of a timestamp, and open that recording's Summary tab.
  `GET /api/search` answers `{moments, summaries}` — two lists, because two full-text rankings cannot be ranked
  against each other.
- **A summary template per source.** A Granola sync is a meeting; a voice memo on a walk is not. Settings → Template
  by source gives each source you import from a template of its own, and new summaries take that shape without
  anyone picking: a recording's own template still wins, then its source's, then the one default. The list shows the
  sources your library actually holds recordings from, nothing is set for you, and existing summaries are untouched
  until you press Regenerate.
- **Ask your library.** A second tab on the Search page answers a question from your own transcripts: full-text
  retrieval picks the moments, the local model writes a few sentences and cites each one, and every citation jumps to
  the excerpt and opens the recording where the words were said. With no local model installed you still get the
  moments that match. `POST /api/ask`.
- **Ask writes the answer where you can see it.** A large local model takes tens of seconds to think, and the panel
  used to show a blinking dot for all of it. The answer now appears as it is written, a few words at a time. The
  citations turn into links at the end, when the list of sources they point at is complete. `POST /api/ask` answers
  newline-delimited JSON: a `delta` per piece, then the same body it always returned.
- **Ask reads your summaries too.** What a meeting decided is usually written in its summary in one sentence, and
  often in words nobody said out loud — so summaries are now in the search index as well, block by block. Ask leads
  with up to three of them (one per recording) and fills the rest with the moments; a cited summary opens that
  recording's Summary tab, since a summary has no second to jump to. The MCP `search` tool returns them too, marked
  `kind: "summary"`. Summaries already in your library are indexed the next time Rapport opens it.
- **MCP server.** Claude, Cursor and any other MCP client can now search your recordings and read transcripts,
  summaries and people, on your Mac, with no key and no network: `rapport-core --mcp`, or
  `uv run python -m rapport.mcp` from a checkout. Seven read-only tools — `search`, `ask`, `list_recordings`,
  `get_recording`, `get_transcript`, `get_summary`, `list_people`. Nothing an assistant does can change or delete
  anything; write-back comes later. Setup for Claude Desktop is in [docs/integrations.md](docs/integrations.md).
- **An MCP client can ask, not only search.** The `ask` tool answers a question from your library the way the Ask
  tab does: the same retrieval, then your own local model writes the answer and cites the excerpts by number. It is
  there for when an answer written on your Mac is the point; `search` remains the faster way for an assistant to
  read the excerpts and answer for itself. With no local model set up you get the excerpts and a `reason`, never an
  error.

## [0.1.0] - 2026-09-09

First public version.

- Import from DJI Mic and any USB recorder, the Mac microphone and Bluetooth mics, Apple Voice Memos (with a picker),
  Omi, Granola, Notion AI Meeting Notes, watched folders and dropped files. Imports are copy-only by default.
- On-device transcription with Whisper large-v3-turbo on MLX, word timestamps, 100+ languages.
- Speaker detection (Silero VAD + WeSpeaker + clustering, or pyannote when available) and recognition of the same
  person across recordings by voice. Rename, reassign, split and merge turns in place; reset speakers.
- Summaries with a local model (Ollama or MLX). Full-text search. Skip-silence playback. Exports.
- Native macOS app (Tauri 2) with a separate worker process and progress bars.
