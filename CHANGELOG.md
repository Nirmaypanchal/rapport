# Changelog

All notable changes to Rapport. The format follows Keep a Changelog; versions follow semver.

## [Unreleased]

### Added

- **Ask your library.** A second tab on the Search page answers a question from your own transcripts: full-text
  retrieval picks the moments, the local model writes a few sentences and cites each one, and every citation jumps to
  the excerpt and opens the recording where the words were said. With no local model installed you still get the
  moments that match. `POST /api/ask`.
- **MCP server.** Claude, Cursor and any other MCP client can now search your recordings and read transcripts,
  summaries and people, on your Mac, with no key and no network: `rapport-core --mcp`, or
  `uv run python -m rapport.mcp` from a checkout. Six read-only tools — `search`, `list_recordings`,
  `get_recording`, `get_transcript`, `get_summary`, `list_people`. Nothing an assistant does can change or delete
  anything; write-back comes later. Setup for Claude Desktop is in [docs/integrations.md](docs/integrations.md).

## [0.1.0] - 2026-09-09

First public version.

- Import from DJI Mic and any USB recorder, the Mac microphone and Bluetooth mics, Apple Voice Memos (with a picker),
  Omi, Granola, Notion AI Meeting Notes, watched folders and dropped files. Imports are copy-only by default.
- On-device transcription with Whisper large-v3-turbo on MLX, word timestamps, 100+ languages.
- Speaker detection (Silero VAD + WeSpeaker + clustering, or pyannote when available) and recognition of the same
  person across recordings by voice. Rename, reassign, split and merge turns in place; reset speakers.
- Summaries with a local model (Ollama or MLX). Full-text search. Skip-silence playback. Exports.
- Native macOS app (Tauri 2) with a separate worker process and progress bars.
