# Getting started with Rapport

Rapport is a free, open-source AI note taker for macOS that keeps everything on your Mac.
This page takes you from nothing to your first transcribed, speaker-tagged recording.

## Requirements

- A Mac with Apple silicon (M1 or later). Transcription uses Apple's MLX framework, which needs it.
- macOS 14 Sonoma or newer.
- About 3 GB of free disk for the app and models, plus space for your recordings (a 1-hour WAV from a DJI Mic is ~700 MB; Voice Memos are ~1 MB per minute).
- No account, no API key, no internet after the first model download.

## Option A: the Mac app

1. Download `Rapport.dmg` from the [latest release](https://github.com/Nirmaypanchal/rapport/releases) and drag Rapport to Applications.
2. The build isn't notarized yet, so the first time right-click `Rapport.app` and choose **Open**.
3. Rapport creates its library at `~/Rapport` (a folder you can open in Finder at any time).
4. Drop an audio file on the Recordings list, or plug in a recorder, or go to **Sources** and pick something to connect.

On the first recording, Rapport downloads Whisper (about 1.6 GB) and the speaker model (about 30 MB) from Hugging Face. That happens once.

## Option B: run from source

```bash
brew install uv ffmpeg node
git clone https://github.com/Nirmaypanchal/rapport
cd rapport
./run.sh
```

`run.sh` installs the Python environment with uv, builds the web UI once, starts the local server on
http://127.0.0.1:8765 and opens it in your browser. Leave it running; it watches for devices.

To work on the UI with hot reload:

```bash
cd frontend && npm run dev     # http://localhost:3000, talking to the API on :8765
```

## Your first recording

Any of these gets a recording in:

- **Drag a file** (WAV, M4A, MP3, AAC, FLAC) onto the Recordings list.
- **Plug in a DJI Mic transmitter or any USB recorder.** DJI is recognized automatically; other drives get a switch in Sources.
- **Press Record** in Sources → Microphone & Bluetooth, using the built-in mic, AirPods, a USB mic or your iPhone via Continuity.
- **Connect Voice Memos** (see permissions below) and pick memos to import.

Processing runs in the background with a progress bar. A 3-minute recording takes about a minute on an M1 Pro;
an hour takes roughly 15 to 20 minutes the first time and less afterwards as models stay loaded.

## Permissions macOS will ask for

- **Microphone**: the first time you press Record. Standard macOS prompt.
- **Full Disk Access**: only for Apple Voice Memos. Apple keeps memos in a protected folder with no narrower permission, so
  Rapport shows a one-time flow: click **Allow access**, switch Rapport on in System Settings → Privacy & Security → Full Disk Access,
  and the panel connects by itself. Voice Memos is never modified; memos are copied.
- **Bluetooth**: only if you pair a device from within Rapport.

If you run from source, macOS attributes these permissions to Terminal (or the Python binary) instead of Rapport.
The desktop app asks as itself.

## Where things live

```
~/Rapport/
  audio/YYYY/YYYY-MM-DD/     untouched original recordings
  library.sqlite             transcripts, speakers, people, summaries, notes
  cache/<id>/                playback file, waveform, pause map (safe to delete)
  settings.json              settings, also editable in the app
```

Back up that folder and you have everything. Move it to another Mac and point Rapport at it with
`RAPPORT_LIBRARY=/path/to/folder`.

## Next steps

- Name yourself: open a recording, click your speaker chip, type your name. Every future recording with your voice is labelled.
- Set the summary model in **Settings** (Ollama if you have it, otherwise the built-in MLX model).
- Read [how it works](how-it-works.md) to understand what the numbers on speaker chips mean.
