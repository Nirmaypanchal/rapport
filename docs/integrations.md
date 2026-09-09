# Integrations

Rapport pulls transcripts and recordings from the apps you already use into the same library as your device recordings,
so search, people and summaries cover everything. All integrations are **read-only** and use **your own keys**;
nothing is written back to any service, and nothing else leaves your Mac.

| Integration | What comes in | What you need |
|---|---|---|
| **Granola** | Notes, transcripts (with "me/others" speakers) and Granola's summary | API key from the Granola desktop app (`grn_…`) |
| **Notion AI Meeting Notes** | Pages containing the meeting-notes block, as transcript text | Internal integration token; optionally a database ID to limit the scan |
| **Omi** | Conversations with transcript segments, overview and action items | Developer API key from the Omi app (`omi_dev_…`) |
| **iCloud Drive, Dropbox, Google Drive** | Any audio file that lands in a folder you watch | Nothing; Rapport finds the synced folders on your Mac |
| **Any folder** | Same, for a folder you choose | Nothing |
| **Exports** (Otter, Plaud, Pocket, Zoom cloud recordings, WhatsApp voice notes…) | Whatever you drop on the Recordings list | Nothing |

Connectors sync every 10 minutes when a key is present, or on demand with **Sync now** in Sources.
Keys are stored in `settings.json` inside your library folder.

## Setting up

### Granola
1. In the Granola desktop app, create an API key (Business plan).
2. Sources → Granola → paste the key → **Connect**.
3. Notes appear as text-only recordings with Granola's summary in the Summary tab.

### Notion AI Meeting Notes
1. Create an internal integration at notion.so/profile/integrations and copy its token.
2. Share your meetings database (or the pages) with the integration.
3. Sources → Notion → paste the token; add the database ID to scan only that database.

### Omi
1. In the Omi app: Developer → API keys → create a key with read access to conversations.
2. Sources → Omi → paste → **Connect**.

### Cloud folders
Sources → iCloud Drive / Dropbox / Google Drive shows the synced root; browse to the folder your phone recorder saves to and
click **Watch this folder**. New audio is copied in on every poll.

## Roadmap for integrations

- **MCP server** so Claude, ChatGPT, Cursor and other assistants can search your recordings, read transcripts and summaries,
  and write summaries or tags back. See [roadmap.md](roadmap.md).
- Zoom and Google Meet local recordings, Otter and Plaud direct connectors, Obsidian and Notion write-back.
- Bluetooth streaming from Omi-style pendants.

Want one sooner? [Open an issue](https://github.com/Nirmaypanchal/rapport/issues) or see
[developers.md](developers.md#adding-a-source-connector); a connector is one Python function.
