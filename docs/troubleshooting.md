# Troubleshooting

Start with **Settings → Activity**: it's the log, newest first, and most problems explain themselves there.
Logs from the desktop app also land in `~/Library/Logs/com.rapport.app/rapport.log`.

## The app opens but stays on "Starting…"
The backend didn't report ready. Check the log file above for the `core=` line and any error after it.
Running from source: make sure `./run.sh` isn't already running on port 8765.

## "Processing failed: … metallib" or MLX errors
The frozen backend must keep its internal symlinks. If you copied `Rapport.app` with a tool that dereferences symlinks
(some sync clients do), reinstall from the DMG. Building yourself: use `desktop/app/build.sh`, not `tauri build` alone.

## Two copies importing the same files
Only one Rapport should run against a library. Don't run `./run.sh` while the app is open on the same library, or set
`RAPPORT_LIBRARY` to a different folder for development.

## Voice Memos shows "Needs access" after granting Full Disk Access
Toggle the switch off and on again in System Settings, then click **Check again**. If you granted access to Terminal rather
than Rapport, that only helps when running from source. The desktop app must be granted itself.

## No microphone appears, or Record fails
ffmpeg enumerates inputs via Core Audio. Check System Settings → Privacy & Security → Microphone for Rapport (or Terminal when
running from source). Bluetooth devices must be connected, not just paired.

## A DJI transmitter isn't detected
It should mount as a drive named `NO NAME` with media name `Mic Tx`. If Finder doesn't show a drive, the mic isn't in
mass-storage mode; unplug, wait, and plug in again. Other recorders: switch them on in Sources → USB recorder.

## Transcription is slow
Large recordings on an M1 take 15 to 20 minutes per hour. Choose a smaller Whisper model in Settings for drafts.
Close other GPU-heavy apps. Summaries with a very large Ollama model can take minutes; the MLX model is much faster.

## The speaker engine merges or splits people wrongly
Tune **Voice match threshold** (higher = stricter matching across recordings) and **Split sensitivity** (lower = more speakers
found within a recording) in Settings, then re-process that recording. For overlapping conversation, enable pyannote.

## Summaries say "No local model available"
Start Ollama, or set the summary provider to MLX in Settings so the built-in model downloads.

## Reset everything
Quit Rapport and delete `~/Rapport` (or move it away). The next launch starts a fresh library.
Models stay cached in `~/.cache/huggingface`; delete that too to reclaim about 4 GB.

## Still stuck
Open a [bug report](https://github.com/Nirmaypanchal/rapport/issues/new?template=bug_report.md) with the last lines of the Activity log.
