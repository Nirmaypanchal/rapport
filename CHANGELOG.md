# Changelog

All notable changes to Rapport. The format follows Keep a Changelog; versions follow semver.

## [Unreleased]

### Added

- **Ask your library.** A second tab on the Search page answers a question from your own transcripts: full-text
  retrieval picks the moments, the local model writes a few sentences and cites each one, and every citation jumps to
  the excerpt and opens the recording where the words were said. With no local model installed you still get the
  moments that match. `POST /api/ask`.

## [0.1.0] - 2026-09-09

First public version.

- Import from DJI Mic and any USB recorder, the Mac microphone and Bluetooth mics, Apple Voice Memos (with a picker),
  Omi, Granola, Notion AI Meeting Notes, watched folders and dropped files. Imports are copy-only by default.
- On-device transcription with Whisper large-v3-turbo on MLX, word timestamps, 100+ languages.
- Speaker detection (Silero VAD + WeSpeaker + clustering, or pyannote when available) and recognition of the same
  person across recordings by voice. Rename, reassign, split and merge turns in place; reset speakers.
- Summaries with a local model (Ollama or MLX). Full-text search. Skip-silence playback. Exports.
- Native macOS app (Tauri 2) with a separate worker process and progress bars.
