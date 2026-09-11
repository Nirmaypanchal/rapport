# Rapport compared with Otter, Fireflies, Granola, MacWhisper and Plaud

Honest, and probably incomplete: these products change. Corrections welcome as pull requests.

| | Rapport | Otter | Fireflies | Granola | MacWhisper | Plaud |
|---|---|---|---|---|---|---|
| Runs entirely on your Mac | Yes | No (cloud) | No (cloud) | Partly (cloud transcription) | Yes | No (cloud) |
| Price | Free, MIT | Subscription | Subscription | Subscription | One-time (Pro) | Device + subscription |
| Imports from your own recorders (DJI, Zoom, SD cards) | Yes, automatic | Upload | Upload | No | Drag files | Plaud devices only |
| Apple Voice Memos, iPhone, Apple Watch | Yes | No | No | No | Drag files | No |
| Records from AirPods / any mic | Yes | App | App | App | Yes | Device |
| Speaker labels | Yes | Yes | Yes | Me/them | Yes (with pyannote) | Yes |
| Recognizes the same person across recordings | Yes, by voice | Partly (named per meeting) | Partly | No | No | No |
| Fix speaker mistakes in place | Yes | Yes | Limited | No | Limited | Limited |
| Summaries | Local model (Ollama/MLX) | Cloud | Cloud | Cloud | Cloud or local | Cloud |
| Full-text search across everything | Yes | Yes | Yes | Yes | Per file | Yes |
| Ask a question, answered from your own transcripts | Yes, local model | Yes, cloud | Yes, cloud | Yes, cloud | No | Yes, cloud |
| Inside Claude, Cursor or any MCP client | Yes, local, read-only | No | No | No | No | No |
| Pulls transcripts from Granola / Notion / Omi | Yes | No | No | — | No | No |
| Meeting bot required | No | Optional | Yes | No | No | No |
| Data format | Plain audio + SQLite in a folder | Cloud | Cloud | Cloud | Files | Cloud |
| Open source | Yes | No | No | No | No | No |

## Where Rapport is not the best choice

- **Windows or Linux.** Rapport needs Apple silicon today. The pipeline is portable in principle; contributions welcome.
- **Real-time captions during a meeting.** Rapport processes after the fact.
- **Very large teams needing shared workspaces.** Rapport is personal by design; sharing is "send them the folder".
- **Heavy overlapping conversation** without the optional pyannote pipeline; the built-in engine is tuned for 1 to 4 clean voices.

## Migrating

- **From Otter, Fireflies, Plaud, Pocket:** export audio from their apps and drop the files on Rapport. Transcripts are redone locally.
- **From Granola or Notion:** connect with your key; notes and summaries come across as text-only recordings.
- **From Voice Memos:** grant access once and pick the memos.
