# Integrations

Rapport pulls transcripts and recordings from the apps you already use into the same library as your device recordings,
so search, people and summaries cover everything. Every connector on this page is **read-only** and uses **your own
keys**; nothing is written back to any service, and nothing else leaves your Mac.

The one integration that works the other way round is the [MCP server](#mcp-server-your-recordings-inside-claude-cursor-or-any-mcp-client)
below, which lets an assistant read *your* library — read-only too, but if that assistant runs in the cloud, what it
reads reaches it.

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

## MCP server: your recordings inside Claude, Cursor or any MCP client

Rapport speaks the [Model Context Protocol](https://modelcontextprotocol.io), so an assistant can look things up in your
own recordings while you talk to it: *"what did we agree about the Lisbon move?"*, *"read me the part where Maya
explains the pricing"*, *"summarise every call with Tom this month"*.

It runs on your Mac, reads the same library folder as the app, and needs no network and no key. The app does not have
to be running. **Today every tool is read-only** — nothing an assistant does can change or delete a recording,
a transcript, a summary or a person. Writing notes back is a later, opt-in step.

One thing to know before you connect a cloud assistant: what it reads, it sends to its own servers, exactly as if you
had pasted the transcript into the chat yourself. That is the only way words from your recordings can leave your Mac —
see [Privacy](privacy.md#the-mcp-server).

| Tool | What the assistant gets |
|---|---|
| `search` | The moments that match a question, each with the turn before and after, the recording id and the timestamp |
| `list_recordings` | Recordings newest first, filtered by title or date |
| `get_recording` | One recording: title, date, length, source, who speaks and for how long |
| `get_transcript` | The transcript as speaker-labelled turns, or just the window you ask for |
| `get_summary` | The summary Rapport wrote, as Markdown, with its template |
| `list_people` | Everyone Rapport recognizes, with speaking time and when they were last heard |

### Claude Desktop

Settings → Developer → Edit Config, and add Rapport to `mcpServers` (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "rapport": {
      "command": "/Applications/Rapport.app/Contents/Resources/core/rapport-core",
      "args": ["--mcp"]
    }
  }
}
```

Restart Claude Desktop; Rapport appears under the tools icon. Add `"--library", "/path/to/library"` to the `args` if your
library is not in the default place (the Settings page shows where it is).

### Cursor, Cline, and other clients

Any client that starts an MCP server over stdio takes the same command. From a source checkout, run it with uv instead:

```bash
uv run python -m rapport.mcp --library ~/Rapport
```

It reads JSON-RPC on stdin and answers on stdout, so on its own in a terminal it will just sit there waiting — that is
the protocol working, not a hang.

## Roadmap for integrations

- **MCP write-back:** let an assistant add a note, a tag or a summary to a recording, with a confirmation in the app.
- Zoom and Google Meet local recordings, Otter and Plaud direct connectors, Obsidian and Notion write-back.
- Bluetooth streaming from Omi-style pendants.

Want one sooner? [Open an issue](https://github.com/Nirmaypanchal/rapport/issues) or see
[developers.md](developers.md#adding-a-source-connector); a connector is one Python function.
