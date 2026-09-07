"""Entry point for the frozen backend used by the desktop shell.

    rapport-core --port 0 --library ~/Rapport --token SECRET

Prints one line `READY <port>` on stdout once the API answers, so the shell knows
when to open its window. The token, when given, is required on every request.
"""
from __future__ import annotations

import argparse
import logging
import os
import socket
import sys
import threading
from pathlib import Path


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=0, help="0 = pick a free port")
    ap.add_argument("--library", default=os.environ.get("DJI_MIC_LIBRARY") or str(Path.home() / "DJI Mic Library"))
    ap.add_argument("--token", default=os.environ.get("RAPPORT_TOKEN") or "")
    ap.add_argument("--ui", default=os.environ.get("RAPPORT_UI_DIR") or "", help="folder with the built web UI (frontend/out)")
    ap.add_argument("--log", default="info")
    args = ap.parse_args()
    if args.ui:
        os.environ["RAPPORT_UI_DIR"] = str(Path(args.ui).expanduser())

    logging.basicConfig(level=getattr(logging, args.log.upper(), logging.INFO), format="%(asctime)s %(levelname)s %(name)s: %(message)s", stream=sys.stderr)
    for noisy in ("httpx", "urllib3", "pyannote", "lightning", "pytorch_lightning", "torio", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # Any library that shells out to ffmpeg (Whisper, torchaudio) must find the bundled one.
    from .binaries import ffmpeg as _ffmpeg

    try:
        os.environ["PATH"] = str(Path(_ffmpeg()).parent) + os.pathsep + os.environ.get("PATH", "")
    except FileNotFoundError:
        pass

    import uvicorn

    from .config import Library
    from .db import Database
    from .importer import Importer
    from .workerproc import WorkerSupervisor
    from .recorder import Recorder
    from .server import create_app

    library = Library(Path(args.library).expanduser())
    db = Database(library.db_path)
    importer = Importer(library, db)
    worker = WorkerSupervisor(library, db)
    recorder = Recorder(library.cache_dir / "_recording")
    importer.on_transcripts_imported = lambda ids: [worker.summarize_later(r) for r in ids if library.settings.auto_summarize and not db.get_recording(r).get("summary")]
    app = create_app(library, db, importer, worker, recorder, token=args.token or None)

    port = args.port or free_port()
    importer.start()
    worker.start()
    db.log("Sidecar started")

    def announce() -> None:
        import time
        import urllib.request

        for _ in range(200):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1)
                print(f"READY {port}", flush=True)
                return
            except Exception:
                time.sleep(0.1)
        print("FAILED", flush=True)

    threading.Thread(target=announce, daemon=True).start()

    # If the shell that launched us disappears (quit, crash, kill), exit too: never leave an orphan server behind.
    parent = os.getppid()

    def watch_parent() -> None:
        import time

        while True:
            time.sleep(1.5)
            if os.getppid() != parent:
                db.log("Shell exited; sidecar stopping")
                recorder.stop()
                os._exit(0)

    if parent > 1:
        threading.Thread(target=watch_parent, daemon=True).start()
    try:
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
    finally:
        recorder.stop()
        importer.stop()
        worker.stop()


if __name__ == "__main__":
    main()
