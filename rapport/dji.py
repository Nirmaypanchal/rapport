"""Detect mounted DJI Mic transmitters and parse their file names.

The DJI Mic Mini 2S transmitters mount as FAT32 USB drives named "NO NAME" whose
`diskutil` media name is "Mic Tx". Recordings live in folders like

    TX_MIC001_20260907_184337/TX02_MIC001_20260907_140758_orig.wav

We identify a mic volume by (a) the media name containing "Mic" and "Tx" or
(b) the presence of TX_MIC*/ folders or TX*_MIC*.wav files, so the detection
also works for other DJI mics with slightly different layouts.
"""
from __future__ import annotations

import plistlib
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

AUDIO_EXT = {".wav", ".mp3", ".m4a", ".flac", ".aac", ".aif", ".aiff"}
DJI_DIR_RE = re.compile(r"^TX_?MIC\d+_\d{8}_\d{6}$", re.I)
DJI_FILE_RE = re.compile(
    r"^(?P<tx>TX\d*)_?(?:MIC)?(?P<idx>\d+)_(?P<date>\d{8})_(?P<time>\d{6})(?P<suffix>.*)$",
    re.I,
)


@dataclass
class ParsedName:
    transmitter: str | None
    file_index: str | None
    recorded_at: datetime | None
    suffix: str


def parse_name(name: str) -> ParsedName:
    stem = Path(name).stem
    m = DJI_FILE_RE.match(stem)
    if not m:
        return ParsedName(None, None, None, "")
    try:
        dt = datetime.strptime(m.group("date") + m.group("time"), "%Y%m%d%H%M%S")
    except ValueError:
        dt = None
    return ParsedName(m.group("tx").upper(), m.group("idx"), dt, m.group("suffix").strip("_"))


@dataclass
class MicVolume:
    mount: Path
    volume_name: str
    media_name: str
    files: list[Path]


def _diskutil_info(mount: Path) -> dict:
    try:
        out = subprocess.run(
            ["diskutil", "info", "-plist", str(mount)], capture_output=True, timeout=10, check=False
        ).stdout
        return plistlib.loads(out) if out else {}
    except Exception:
        return {}


def _looks_like_dji(mount: Path) -> bool:
    try:
        for child in mount.iterdir():
            if child.name.startswith("."):
                continue
            if child.is_dir() and DJI_DIR_RE.match(child.name):
                return True
            if child.is_file() and DJI_FILE_RE.match(child.stem) and child.suffix.lower() in AUDIO_EXT:
                return True
    except (PermissionError, OSError):
        pass
    return False


def audio_files(mount: Path) -> list[Path]:
    found: list[Path] = []
    try:
        for p in mount.rglob("*"):
            if any(part.startswith(".") for part in p.relative_to(mount).parts):
                continue
            if p.is_file() and p.suffix.lower() in AUDIO_EXT:
                found.append(p)
    except (PermissionError, OSError):
        pass
    return sorted(found)


def find_mic_volumes(extra_names: list[str] | None = None) -> list[MicVolume]:
    extra = {n.strip().lower() for n in (extra_names or []) if n.strip()}
    vols: list[MicVolume] = []
    root = Path("/Volumes")
    if not root.exists():
        return vols
    for mount in sorted(root.iterdir()):
        if mount.is_symlink() or not mount.is_dir():
            continue
        info = _diskutil_info(mount)
        media = str(info.get("MediaName", "") or "")
        removable = bool(info.get("RemovableMedia") or info.get("Removable") or info.get("Ejectable"))
        is_dji_media = "mic" in media.lower() and "tx" in media.lower()
        if not (is_dji_media or mount.name.lower() in extra or (removable and _looks_like_dji(mount))):
            continue
        vols.append(MicVolume(mount=mount, volume_name=mount.name, media_name=media, files=audio_files(mount)))
    return vols


def list_removable_volumes() -> list[dict]:
    """Every mounted removable/external volume, with an audio file count and whether it looks like a DJI mic."""
    root = Path("/Volumes")
    out: list[dict] = []
    if not root.exists():
        return out
    for mount in sorted(root.iterdir()):
        if mount.is_symlink() or not mount.is_dir():
            continue
        info = _diskutil_info(mount)
        removable = bool(info.get("RemovableMedia") or info.get("Removable") or info.get("Ejectable"))
        if not removable:
            continue
        media = str(info.get("MediaName", "") or "")
        is_dji = ("mic" in media.lower() and "tx" in media.lower()) or _looks_like_dji(mount)
        out.append({"mount": str(mount), "name": mount.name, "media": media, "is_dji": is_dji, "files": len(audio_files(mount))})
    return out
