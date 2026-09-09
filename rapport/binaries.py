"""Locate ffmpeg/ffprobe: bundled next to the frozen app, or from PATH in development."""
from __future__ import annotations

import os
import shutil
import sys
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=None)
def find(name: str) -> str:
    env_dir = os.environ.get("RAPPORT_BIN_DIR")
    candidates: list[Path] = []
    if env_dir:
        candidates.append(Path(env_dir) / name)
    if getattr(sys, "frozen", False):  # PyInstaller one-dir bundle
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        candidates += [base / "bin" / name, Path(sys.executable).parent / "bin" / name, Path(sys.executable).parent / name]
    candidates.append(Path(__file__).resolve().parent.parent / "desktop" / "sidecar" / "bin" / name)
    for c in candidates:
        if c.is_file() and os.access(c, os.X_OK):
            return str(c)
    found = shutil.which(name)
    if found:
        return found
    raise FileNotFoundError(f"{name} not found. Install it with `brew install ffmpeg` or set RAPPORT_BIN_DIR.")


def ffmpeg() -> str:
    return find("ffmpeg")


def ffprobe() -> str:
    return find("ffprobe")
