# Privacy: what leaves your Mac

Short version: **nothing you record.** Here is the complete list of network activity, so you don't have to take our word for it.

## Network calls Rapport makes

| When | Where | What | Can you turn it off? |
|---|---|---|---|
| First transcription | huggingface.co | Downloads Whisper and the speaker models | Pre-download and go offline |
| First summary with the MLX model | huggingface.co | Downloads Qwen2.5-3B once | Use Ollama instead, or turn summaries off |
| Summaries with Ollama | 127.0.0.1:11434 | Local only | — |
| Granola / Notion / Omi sync | Their APIs | Fetches *your* notes with *your* key. Nothing is sent except the request. | Don't add a key |
| pyannote (optional) | huggingface.co | Downloads the gated pipeline once, with your token | Use the built-in engine |

That's the whole list. There is no Rapport server, no analytics, no crash reporting, no account, no license check.
Audio, transcripts, voice fingerprints, summaries and people never leave the machine.

## What's stored, and where

`~/Rapport` (or `~/DJI Mic Library` for early installs): original audio, a SQLite database with transcripts, speakers,
voice embeddings, people, summaries and notes, a cache of playback files and waveforms, and `settings.json` with your settings
and any connector keys. Delete the folder and Rapport has forgotten everything.

Voice embeddings are 256-number vectors derived from a person's voice. They can match a voice; they cannot reconstruct speech.
They stay in the database.

## The local API

The Python backend listens on `127.0.0.1` only, never on a network interface. In the desktop app every request needs a
random token generated at launch. Running from source (`./run.sh`) there is no token, so other processes on the same Mac
could talk to it; use the app if that matters to you.

## macOS permissions

- **Microphone**: only when you press Record.
- **Full Disk Access**: only if you connect Apple Voice Memos, because Apple protects that folder with no narrower permission.
  Rapport reads memo files and the Voice Memos database; it never writes there.
- **Bluetooth**: only if you pair a device from Rapport.

## Verifying this yourself

The code is MIT licensed and small. `grep -rn "http" rapport/` shows every URL. The connectors are in `rapport/connectors.py`,
model downloads happen inside `mlx_whisper`, `pyannote.audio` and `mlx_lm`, and there is nothing else.
