"""The processing worker runs in its own OS process so heavy ML work never stalls the API and UI.

The API process starts `WorkerSupervisor`; it spawns a child that runs `worker_main`, which owns the models
and drains two queues from the shared SQLite database: recordings with status 'queued', and recordings whose
summary_status is 'queued'. State for /api/status is published to <library>/cache/_worker.json.
"""
from __future__ import annotations

import json
import multiprocessing as mp
import os
import threading
import time
from pathlib import Path


STATE_FILE = "cache/_worker.json"


def worker_main(library_root: str) -> None:
    import logging
    import signal
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s worker %(name)s: %(message)s", stream=sys.stderr)
    for noisy in ("httpx", "urllib3", "pyannote", "lightning", "pytorch_lightning", "torio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    from .binaries import ffmpeg
    from .config import Library
    from .db import Database
    from .pipeline import Worker

    try:
        os.environ["PATH"] = str(Path(ffmpeg()).parent) + os.pathsep + os.environ.get("PATH", "")
    except FileNotFoundError:
        pass

    library = Library(Path(library_root))
    db = Database(library.db_path)
    worker = Worker(library, db)
    state_path = library.root / STATE_FILE
    parent = os.getppid()
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())

    def publish() -> None:
        try:
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(json.dumps({"pid": os.getpid(), "ts": time.time(), **worker.status()}))
        except OSError:
            pass

    # Anything left "processing" by a crashed worker goes back to the queue.
    for r in db.list_recordings():
        if r["status"] == "processing":
            db.update_recording(r["id"], status="queued", stage=None)
        if r.get("summary_status") == "running":
            db.update_recording(r["id"], summary_status="queued")

    publisher = threading.Thread(target=lambda: [publish() or time.sleep(1.0) for _ in iter(lambda: not stop.is_set(), False)], daemon=True)
    publisher.start()
    while not stop.is_set():
        if os.getppid() != parent:  # the API process is gone; so are we
            break
        library.reload_settings()
        rec = db.next_queued()
        if rec is not None:
            worker.process(rec)
            continue
        srec = db.next_summary_queued()
        if srec is not None:
            worker.summarize_now(srec["id"])
            continue
        time.sleep(1.0)
    publish()


class WorkerSupervisor:
    """API-side handle: starts/restarts the worker process and reads its published state."""

    def __init__(self, library, db):
        self.library = library
        self.db = db
        self._proc: mp.Process | None = None
        self._stop = threading.Event()

    def start(self) -> None:
        self._spawn()
        threading.Thread(target=self._watch, name="worker-supervisor", daemon=True).start()

    def _spawn(self) -> None:
        ctx = mp.get_context("spawn")
        self._proc = ctx.Process(target=worker_main, args=(str(self.library.root),), name="rapport-worker", daemon=True)
        self._proc.start()

    def _watch(self) -> None:
        while not self._stop.is_set():
            time.sleep(2.0)
            if self._proc is not None and not self._proc.is_alive() and not self._stop.is_set():
                self.db.log("Worker process exited unexpectedly; restarting", "warn")
                self._spawn()

    def stop(self) -> None:
        self._stop.set()
        if self._proc is not None and self._proc.is_alive():
            self._proc.terminate()
            self._proc.join(timeout=5)

    def wake(self) -> None:  # the worker polls; nothing to do
        pass

    def summarize_later(self, rid: int) -> bool:
        from .summarize import resolve_provider

        s = self.library.settings
        if resolve_provider(s.summary_provider, s.summary_model or None) is None:
            return False
        self.db.update_recording(rid, summary_status="queued", summary_error=None)
        return True

    class _Models:
        def reset_pyannote(self) -> None:
            pass

    models = _Models()

    def status(self) -> dict:
        p = self.library.root / STATE_FILE
        try:
            st = json.loads(p.read_text())
            if time.time() - st.get("ts", 0) < 10:
                return {"current": st.get("current"), "models": st.get("models", {}), "alive": True}
        except Exception:
            pass
        return {"current": None, "models": {}, "alive": bool(self._proc and self._proc.is_alive())}
