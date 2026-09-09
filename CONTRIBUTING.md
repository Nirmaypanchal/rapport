# Contributing to Rapport

Thanks for helping. Rapport is a local-first voice library for macOS: every recording you make,
transcribed, speaker-tagged and summarized on your own Mac. Contributions of every size are welcome,
from a typo to a new device connector.

## Ways to help

- **Report a device or app that doesn't import.** Open a "Device / integration request" issue with the
  recorder model, how it mounts (USB drive, app export, cloud folder) and a sample file name.
- **Fix a bug.** Search issues first; if it's new, open one with steps to reproduce and the last lines of
  the Activity log (Settings → Activity).
- **Add a source connector.** See [docs/developers.md](docs/developers.md#adding-a-source-connector).
- **Improve the docs.** Everything under `docs/` is fair game.

## Development setup

Requirements: macOS 14+ on Apple silicon, [uv](https://docs.astral.sh/uv/), ffmpeg, Node 20+.

```bash
brew install uv ffmpeg node
git clone https://github.com/Nirmaypanchal/rapport && cd rapport
./run.sh                         # Python API + worker on http://127.0.0.1:8765, builds the UI once
cd frontend && npm run dev       # hot-reloading UI on :3000 (talks to :8765)
```

Use a scratch library while developing so you never touch your real recordings:

```bash
RAPPORT_LIBRARY=/tmp/rapport-dev ./run.sh
```

The desktop app (Tauri 2) lives in `desktop/`; see [docs/developers.md](docs/developers.md#desktop-app).

## Pull requests

- Keep PRs focused. One connector, one fix, one doc page.
- Run `cd frontend && npx tsc --noEmit && npm run build` before pushing UI changes.
- Python code is typed and formatted plainly; no framework beyond FastAPI. Prefer the standard library.
- Never add a network call that sends user audio or text anywhere. Connectors may *fetch* the user's own
  data with the user's own key, and that is the only outbound traffic allowed.
- Describe what you tested and on which device.

## Code of conduct

Be kind. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
