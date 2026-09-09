"""Live recording from any Core Audio input (built-in, USB, Bluetooth, Continuity iPhone) via ffmpeg/avfoundation."""
from __future__ import annotations

import re
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .binaries import ffmpeg


def list_inputs() -> list[str]:
    """Names of audio input devices as avfoundation sees them."""
    try:
        out = subprocess.run([ffmpeg(), "-hide_banner", "-f", "avfoundation", "-list_devices", "true", "-i", ""], capture_output=True, text=True, timeout=10).stderr
    except Exception:
        return []
    names: list[str] = []
    in_audio = False
    for line in out.splitlines():
        if "AVFoundation audio devices" in line:
            in_audio = True
            continue
        if "AVFoundation video devices" in line:
            in_audio = False
        m = re.search(r"\[\d+\]\s+(.*)$", line) if in_audio else None
        if m:
            names.append(m.group(1).strip())
    return names


@dataclass
class Session:
    device: str
    path: Path
    started_at: float
    proc: subprocess.Popen


class Recorder:
    def __init__(self, tmp_dir: Path):
        self.tmp_dir = tmp_dir
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.session: Session | None = None
        self.last_error: str | None = None

    def start(self, device: str) -> dict:
        with self.lock:
            if self.session:
                raise RuntimeError("already recording")
            ts = datetime.now()
            path = self.tmp_dir / f"REC_{ts:%Y%m%d_%H%M%S}.wav"
            cmd = [ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-f", "avfoundation", "-i", f":{device}", "-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le", str(path)]
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            time.sleep(0.8)
            if proc.poll() is not None:
                err = (proc.stderr.read() if proc.stderr else "") or "ffmpeg exited"
                self.last_error = err.strip()[:300]
                raise RuntimeError(self.last_error or "could not open the microphone (check Microphone permission for the app that launched this)")
            self.session = Session(device=device, path=path, started_at=time.time(), proc=proc)
            self.last_error = None
            return self.status()

    def stop(self) -> Path | None:
        with self.lock:
            s = self.session
            if not s:
                return None
            try:
                if s.proc.stdin:
                    s.proc.stdin.write("q")
                    s.proc.stdin.flush()
                s.proc.wait(timeout=5)
            except Exception:
                s.proc.send_signal(signal.SIGINT)
                try:
                    s.proc.wait(timeout=5)
                except Exception:
                    s.proc.kill()
            self.session = None
            return s.path if s.path.exists() and s.path.stat().st_size > 1000 else None

    def status(self) -> dict | None:
        s = self.session
        if not s:
            return None
        if s.proc.poll() is not None:  # died underneath us
            self.session = None
            self.last_error = "recording stopped unexpectedly"
            return None
        return {"device": s.device, "started_at": s.started_at, "elapsed": round(time.time() - s.started_at, 1)}
