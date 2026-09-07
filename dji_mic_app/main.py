from __future__ import annotations

import logging
import threading
import webbrowser

import uvicorn

from .config import DEFAULT_LIBRARY, Library
from .db import Database
from .importer import Importer
from .pipeline import Worker
from .recorder import Recorder
from .server import create_app


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    for noisy in ("httpx", "urllib3", "pyannote", "lightning", "pytorch_lightning", "speechbrain", "torio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    library = Library(DEFAULT_LIBRARY)
    db = Database(library.db_path)
    importer = Importer(library, db)
    worker = Worker(library, db)
    recorder = Recorder(library.cache_dir / "_recording")
    importer.on_transcripts_imported = lambda ids: [worker.summarize_later(r) for r in ids if library.settings.auto_summarize and not db.get_recording(r).get("summary")]
    app = create_app(library, db, importer, worker, recorder)

    importer.start()
    worker.start()
    db.log("App started")

    url = f"http://127.0.0.1:{library.settings.port}"
    print(f"\n  DJI Mic Library  ->  {url}\n  library folder   ->  {library.root}\n")
    if library.settings.open_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        uvicorn.run(app, host="127.0.0.1", port=library.settings.port, log_level="warning")
    finally:
        importer.stop()
        worker.stop()


if __name__ == "__main__":
    main()
