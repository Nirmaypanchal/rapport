# How Rapport works

A plain-language tour of the pipeline, then the technical detail for people who want to change it.
Everything described here runs on your Mac; the only network calls are model downloads and the connectors you enable.

## The pipeline

```
recorder / file / app  ─►  import  ─►  transcribe  ─►  find speakers  ─►  recognize people  ─►  summarize  ─►  library
                           copy+hash    Whisper (MLX)   VAD + embeddings   voice fingerprints   Ollama / MLX     SQLite + files
```

### 1. Import

Sources are polled every few seconds. New audio files are copied into `audio/YYYY/YYYY-MM-DD/`, hashed with SHA-256,
and compared against the library so the same file is never imported twice, even if it comes from two devices.
Devices are read-only by default. Transcripts from apps without audio (Granola, Notion, Omi) are imported as text-only
recordings: everything works except playback.

### 2. Transcription

Audio is converted to 16 kHz mono with ffmpeg and transcribed by **Whisper large-v3-turbo running on MLX**, Apple's
machine-learning framework for Apple silicon. Word-level timestamps are kept, which is what makes click-to-seek and the live
word highlight possible. Language is auto-detected, or fixed in Settings. Other Whisper sizes are available for speed.

### 3. Speaker detection (diarization)

Two engines:

- **Built-in** (default, no accounts): Silero VAD finds speech, the WeSpeaker ResNet34 model turns 2-second windows into
  256-dimensional voice embeddings, and agglomerative clustering groups them into speakers. Tuned for the 1 to 4 clean voices
  a lavalier mic or a call typically has.
- **pyannote** (optional, better on overlapping conversation): pyannote's diarization pipeline is gated on Hugging Face.
  Accept its terms, add a read token in Settings, and Rapport switches automatically.

Either way the output is "who spoke when", and words are assigned to speakers by overlap.

### 4. Speaker recognition across recordings

This is the part most tools don't do. For each speaker in a recording, Rapport computes one voice embedding from that
speaker's longest turns and compares it with the centroid of every known person. Above the similarity threshold
(default 0.60, tunable), the speaker is linked to that person; otherwise a new "Speaker N" is created. Name a person once
and the name follows the voice into later recordings. Embeddings never leave the database.

Corrections are edits, not retraining: renaming, reassigning a turn, splitting or merging turns updates the database only,
so they're instant and reversible. **Reset speakers** on the People page re-runs matching from the stored fingerprints.

### 5. Summaries

Written by a model on your Mac: Ollama if it's running (any model you've pulled), otherwise Qwen2.5-3B on MLX, downloaded once.
The prompt asks for a summary, key points, action items and notable quotes, in the language of the transcript, using the
speaker names you've set. Notes that arrive from Granola or Omi keep the summary those apps wrote.

### 6. Playback and search

The transport shows a waveform, a speaker lane, and a playhead synced to the transcript. Skip silences removes pauses on the fly.
Search is SQLite full-text search across every transcript; a hit opens the recording at that second.

## Architecture

```
┌──────────────────────────── Rapport.app (Tauri 2, Rust) ────────────────────────────┐
│  window (WebKit)  ──►  http://127.0.0.1:<port>/?token=…                              │
└──────────────────────────────────────────────┬──────────────────────────────────────┘
                                               │ spawns, watches, kills
┌──────────────────────────────────────────────▼──────────────────────────────────────┐
│  rapport-core (Python, frozen with PyInstaller)                                      │
│  FastAPI on 127.0.0.1  ·  serves the Next.js static UI  ·  bearer token per launch   │
│  importer thread (devices, folders, connectors)  ·  recorder (ffmpeg avfoundation)   │
│        └── worker process: Whisper · VAD · embeddings · clustering · summaries       │
│  SQLite (WAL) + plain files in ~/Rapport                                              │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

- The UI is a Next.js static export served by the Python process, so it behaves identically in a browser and in the app.
- Heavy work runs in a separate worker process so the API and UI stay responsive; progress is written to the database.
- The Tauri shell owns OS integration only (window, permissions attribution, updates later). Everything else is in the sidecar.
- Run from source, the same code serves on port 8765 without a token.

## Models and where they come from

| Task | Model | Source | License | Size |
|---|---|---|---|---|
| Transcription | Whisper large-v3-turbo (MLX) | Hugging Face `mlx-community` | MIT | 1.6 GB |
| Voice activity | Silero VAD | pip `silero-vad` | MIT | 2 MB |
| Voice embeddings | WeSpeaker ResNet34-LM | Hugging Face `pyannote` | Apache-2.0 | 26 MB |
| Diarization (optional) | pyannote speaker-diarization | Hugging Face (gated) | MIT | 30 MB |
| Summaries | Any Ollama model, or Qwen2.5-3B-Instruct 4-bit (MLX) | Ollama / Hugging Face | varies / Apache-2.0 | 2 GB |

Models are cached in `~/.cache/huggingface` and shared with any other tool that uses them.

## Performance on Apple silicon

Measured on an M1 Pro with 32 GB: a 3-minute recording is transcribed and speaker-tagged in about 50 seconds;
an hour of audio takes 15 to 20 minutes end to end. Summaries take seconds with the MLX model and a minute or two with
a large Ollama model. Later Macs are faster roughly in proportion to their GPU.
