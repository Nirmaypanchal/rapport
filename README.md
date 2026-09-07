# Voice Library

A local Mac app that gathers every voice recording you make (DJI Mic, any USB recorder, a microphone,
Voice Memos, Omi, Granola, Notion…) into one searchable library. Plug a DJI transmitter in and it will:

1. **Import** every recording from the mic into `~/DJI Mic Library/audio/YYYY/YYYY-MM-DD/`,
   verify the copy byte-for-byte (SHA-256), and then delete it from the mic so the
   transmitter never fills up. The originals in the library are never modified.
2. **Transcribe** it on-device with Whisper (`mlx-whisper`, Apple silicon GPU), with word timestamps.
3. **Find the speakers** (who spoke when) and compute a voice embedding for each one.
4. **Recognise people across recordings**: a new voice becomes "Speaker N"; rename it once
   and every later recording with that voice is labelled with the name automatically.
5. Show everything in a browser UI: waveform player, speaker-coloured transcript with
   click-to-seek and live word highlighting, people directory, full-text search across
   all transcripts, plain-text transcript export.

Nothing leaves your Mac. Models are downloaded once from Hugging Face and cached.

## Run

```bash
./run.sh
```

Then open http://127.0.0.1:8765 (it opens automatically). Leave it running; it watches
`/Volumes` every few seconds for a DJI transmitter.

Requirements: macOS on Apple silicon, [uv](https://docs.astral.sh/uv/), ffmpeg and Node 20+
(`brew install uv ffmpeg node`). The first run installs the Python environment, builds the UI, and
downloads ~1.6 GB of models.

To start it automatically at login:

```bash
./scripts/install_launchd.sh      # ./scripts/install_launchd.sh --remove to undo
```

## Where things live

Everything is in one folder, `~/DJI Mic Library` (override with `DJI_MIC_LIBRARY=/path`):

| Path | What |
|---|---|
| `audio/YYYY/YYYY-MM-DD/*.wav` | untouched original recordings, your backup |
| `library.sqlite` | transcripts, speakers, people, notes |
| `cache/<id>/` | 16 kHz copy, playback `.m4a`, waveform peaks (safe to delete, rebuilt on re-process) |
| `settings.json` | settings, also editable in the UI |

Back up that folder and you have everything.

## Speaker engine

Two engines exist; the app picks automatically:

* **Built-in** (works out of the box, no accounts): Silero VAD + WeSpeaker voice embeddings +
  clustering. Good for the 1-4 clean lavalier voices a DJI mic records.
* **pyannote** (better turn boundaries and overlap handling): its models are gated on Hugging Face.
  Accept the terms on [pyannote/speaker-diarization-community-1](https://huggingface.co/pyannote/speaker-diarization-community-1)
  and [pyannote/segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0) with your
  Hugging Face account, make sure a read token is available (`huggingface-cli login` or paste it
  in Settings), and the app switches over on the next recording.

Cross-recording person matching always uses the same WeSpeaker embedding, so switching engines
does not invalidate the people you have already named.

## Tuning

In **Activity & Settings**:

* *Voice match threshold* (default 0.60): cosine similarity needed to link a voice to a known person.
  If the same person keeps showing up as a new "Speaker N", lower it; if different people get merged, raise it.
* *Split sensitivity* (built-in engine, default 0.55): lower finds more speakers in one file.
* *Whisper model*: `large-v3-turbo` is the sweet spot; `small`/`base` are much faster for drafts.

Fixing mistakes never needs re-processing: click a speaker chip in a recording to rename the
person, assign the voice to someone else, or create a new person. Merge duplicates on the People page.

## Sources: devices and integrations

The **Sources** page is where recorders and note-takers plug in. Audio is copied into the library
and processed here; transcripts from other apps are imported as text (no player, everything else works).

| Source | How |
|---|---|
| DJI Mic transmitters | Plug in over USB. Detected, verified, cleared from the mic. |
| Any USB recorder, SD card, drive | Plug in and switch it on in Sources. Copied from, never deleted. |
| Microphone, Bluetooth mic, AirPods, iPhone (Continuity) | Pick the input and press Record. Saved as 48 kHz WAV. |
| Apple Voice Memos, iPhone, Apple Watch | Grant Full Disk Access once; memos (including those synced through iCloud) are imported with titles and dates. |
| Omi pendant | Paste a Developer API key (`omi_dev_…`). Conversations arrive with transcript, overview and action items. |
| Granola | Paste an API key (`grn_…`, Business plan). Notes, transcripts and Granola's summary. |
| Notion AI Meeting Notes | Paste an internal integration token, optionally a database ID. Pages with meeting-notes blocks. |
| Watched folders | Any folder (iCloud Drive, Dropbox, an export folder) is checked on every poll. |
| Files and exports | Drop files on the Recordings list, or choose them in Sources. Otter, Plaud and Pocket exports work this way. |

Integrations are read-only and sync every 10 minutes when a key is present; nothing is written back.
Keys live in `settings.json` inside the library folder and never leave the Mac except to call that one service.

## Landing page

`site/index.html` is the Rapport landing page, a single self-contained file. It deploys to
Vercel as a static site: `vercel.json` points the output at `site/` and `.vercelignore` hides
the rest of the repository, so Vercel never tries to build the Python app (which only runs on a Mac).

## Correcting the transcript

Speaker detection is occasionally wrong for a turn. Fix it in place; every correction is
saved to the database and survives restarts:

* Click the **speaker name** on a turn to pick who really said it (anyone in this recording,
  any known person, or a brand-new person).
* **Split at a word…** when the mistake starts mid-turn: click the word where the new turn
  begins, then change that new turn's speaker.
* **Merge with previous** joins a turn back into the one before it.
* **Edit text** fixes transcription typos. Search picks up the new text immediately.

Corrections do not retrain the voice model, and *Re-process* replaces them, so it asks first.

## Skipping silences

In the player, tick **Skip silences**: playback jumps over every pause longer than the
configured minimum (default 0.7 s), the waveform dims the skipped parts, and the label shows how
much time it saves. Timestamps in the transcript stay original. **Download condensed audio**
exports the same thing as an `.m4a` with the pauses physically removed. Both thresholds are in
Settings.

## Importing older files

Files you already copied off the mic: **Settings → Import from folder…**. They are copied into the
library (never moved) and processed like everything else.

## Developing the UI

The interface is a Next.js app in `frontend/` (App Router, Tailwind v4, shadcn/ui on Base UI),
styled from the Cue Sheet design tokens in `frontend/src/app/globals.css`. It is statically exported
and served by the Python server, so distribution stays one process.

```bash
./run.sh                      # API + processing on :8765, serves frontend/out
cd frontend && npm run dev    # hot-reloading UI on :3000, talking to the API on :8765
npm run build                 # refresh frontend/out (run.sh does this when sources change)
```

## Layout

```
frontend/       Next.js UI (src/app pages, src/components, src/lib/api.ts types)
dji_mic_app/
  config.py     settings + library paths
  db.py         SQLite schema and queries (FTS5 for search)
  dji.py        detect DJI volumes, parse TXnn_MICnnn_YYYYMMDD_HHMMSS names
  importer.py   /Volumes watcher, copy + verify + delete
  audio.py      ffmpeg conversion, hashing, waveform peaks
  transcribe.py mlx-whisper
  diarize.py    pyannote / built-in diarizers
  speakers.py   voice embeddings + people registry matching
  pipeline.py   background worker
  server.py     FastAPI API
  main.py       entry point
```
