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
| An MCP client you connected | wherever that assistant runs | The transcripts, excerpts or summaries **it asks for**, as if you had pasted them in | Don't connect one, or point it at a local model |

That's the whole list. There is no Rapport server, no analytics, no crash reporting, no account, no license check.
Rapport never sends your audio, transcripts, voice fingerprints, summaries or people anywhere. The one way words from
your recordings can leave the Mac is if you connect a cloud assistant to the MCP server yourself, and then only what it
reads — see [The MCP server](#the-mcp-server) below.

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

## The MCP server

The MCP server (`rapport-core --mcp`) opens no port at all: the assistant that uses it starts it as a child process and
talks to it over that process's own stdin and stdout. It reads the library folder and nothing else, and every tool is
read-only, so nothing an assistant does can change or delete a recording, a transcript or a person.

What it cannot control is what the assistant then does with what it read. A cloud assistant — Claude, ChatGPT, Cursor —
sends the excerpts, transcripts or summaries it asked for to its own servers, like anything else you paste into it. That
is the one case where words from your recordings can leave the Mac, and it happens only for the recordings the assistant
actually reads, only while you have it connected, and only because you configured it. A local model over MCP keeps
everything here.

## macOS permissions

- **Microphone**: only when you press Record.
- **Full Disk Access**: only if you connect Apple Voice Memos, because Apple protects that folder with no narrower permission.
  Rapport reads memo files and the Voice Memos database; it never writes there.
- **Bluetooth**: only if you pair a device from Rapport.

## Verifying this yourself

The code is MIT licensed and small. `grep -rn "http" rapport/` shows every URL. The connectors are in `rapport/connectors.py`,
model downloads happen inside `mlx_whisper`, `pyannote.audio` and `mlx_lm`, and there is nothing else.
