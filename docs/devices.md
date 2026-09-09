# Devices Rapport imports from

The principle: **you don't need a new device.** Rapport reads from whatever already records your voice.
This page lists what's supported, how each one connects, and how to add one that isn't here.

## At a glance

| Device | How it connects | Status |
|---|---|---|
| Apple Voice Memos on Mac, iPhone, Apple Watch | Read from the Mac's Voice Memos library (iCloud sync brings phone and watch memos) | Supported |
| iPhone as a microphone | Continuity: appears as an input, press Record | Supported |
| AirPods, any Bluetooth headset | Pair in macOS, appears as an input, press Record | Supported |
| Built-in Mac microphone, USB microphones and interfaces | Appears as an input, press Record | Supported |
| DJI Mic Mini, Mic Mini 2S, Mic 2, Mic 3 | Transmitter or charging case over USB-C mounts as a drive; auto-detected | Supported |
| Zoom H1n, H4n, H6, F-series | SD card or USB mass storage; switch on in Sources | Supported (generic recorder) |
| Tascam DR-05X, DR-40X, Portacapture | SD card or USB mass storage; switch on in Sources | Supported (generic recorder) |
| Sony ICD-UX, ICD-PX, TX-series | USB mass storage; switch on in Sources | Supported (generic recorder) |
| Any SD card or USB drive with audio files | Switch on in Sources | Supported |
| Omi pendant | Developer API key; conversations with transcript and summary | Supported (API) |
| Plaud Note, Plaud NotePin | Export audio from the Plaud app, drop the files, or watch the export folder | Via export |
| Pocket AI recorder | Export from the Pocket app, drop the files | Via export |
| Limitless Pendant, Bee | Export from their apps, drop the files | Via export |
| Android phones (Recorder app, Samsung Voice Recorder) | Sync the folder to iCloud Drive/Dropbox/Google Drive and watch it | Via folder |
| Rode Wireless GO/PRO, Hollyland Lark | On-board recording mounts over USB; switch on in Sources | Supported (generic recorder) |

## How detection works

- **DJI mics** mount as FAT32 volumes named `NO NAME` with the media name `Mic Tx`, holding folders like
  `TX_MIC001_20260907_184337/TX02_MIC001_20260907_140758_orig.wav`. Rapport recognizes the media name and the file-name
  pattern, parses the recording time from the name, and imports every WAV. Files are 48 kHz 32-bit float mono.
- **Other removable volumes** appear in Sources → USB recorder or SD card with a switch. Once on, every audio file on that
  volume is imported on each poll; the switch is remembered by volume name so the same card imports automatically next time.
- **Live inputs** are enumerated from Core Audio via ffmpeg's avfoundation device. Recordings are saved as 48 kHz WAV.
- **Voice Memos** are read from `~/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings/`, including the
  `CloudRecordings.db` database for titles and dates. Memos evicted to iCloud are skipped until they're downloaded on the Mac.

Nothing is deleted from any device unless you switch on "Clear the mic after import" in Settings, and even then only after
the copy is verified byte-for-byte.

## Devices we'd like help with

Open a [device request](https://github.com/Nirmaypanchal/rapport/issues/new?template=device_request.md) with a sample file name
if yours behaves differently. Particularly interesting:

- Wearables with Bluetooth audio streaming (Omi's BLE protocol is open; a native connector is on the roadmap).
- Recorders that need an app to export (Plaud, Pocket): if they have an API, a connector can replace the manual export.
- Voice recorders that save proprietary formats.

## Adding a device connector

Most devices need no code: anything that shows up as a drive or a folder already works. For anything with an API or a
special layout, see [developers.md](developers.md#adding-a-source-connector).
