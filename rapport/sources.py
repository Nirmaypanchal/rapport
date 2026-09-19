"""Where a recording came from, as a *place* rather than as a mechanism.

Two vocabularies met in the middle of this app and did not match. The ``recordings.source`` column names the
mechanism Rapport used to get a file — ``folder``, ``usb``, ``microphone``, ``file``, ``voicememos``, ``granola``
— which is what import dedup and the connectors need, and must not change. The Sources page names *places*:
``mic``, ``files``, ``icloud``, ``dropbox``, ``googledrive`` and a generic ``folder`` for everything else. A user
choosing "a summary template for my iCloud recorder" is choosing a place, so anything offered next to that choice
has to speak the second vocabulary (`sprint/decisions.md`, 2026-09-14).

This module is the one translation between them. ``source_key`` maps a recording to the place it came from; three
watched folders that all arrive as ``folder`` come out as the services that sync them, because the watched path is
already stored on the row. Nothing here writes, and nothing here changes what the column holds.
"""
from __future__ import annotations

from pathlib import Path

# Mechanisms whose place is simply spelled differently on the Sources page. Everything not named here — `dji`,
# `usb`, `voicememos`, `granola`, `omi`, `notion` — is already the same word on both sides.
PLACE_NAMES = {"microphone": "mic", "file": "files"}


def _present(cands: list[tuple[str, str, Path]]) -> list[dict]:
    """The candidates that exist on this Mac, first one wins per key."""
    seen: set[str] = set()
    out = []
    for key, label, p in cands:
        if p.is_dir() and key not in seen:
            seen.add(key)
            out.append({"key": key, "label": label, "path": str(p)})
    return out


def cloud_roots(home: Path | None = None) -> list[dict]:
    """The cloud-synced folders present on this Mac: the places a watched folder can belong to.

    A folder under one of these belongs to that service, however deep — the same rule `sources-view.tsx` uses
    client-side to decide which tile a watched folder is listed under. OneDrive is in this list and has no tile of
    its own yet, so its folders are still *managed* under the generic "watched folder" tile while their recordings
    are *filed* under `onedrive`; naming the place a recording came from is right either way.
    """
    home = home or Path.home()
    cands = [
        ("icloud", "iCloud Drive", home / "Library/Mobile Documents/com~apple~CloudDocs"),
        ("dropbox", "Dropbox", home / "Library/CloudStorage/Dropbox"),
        ("dropbox", "Dropbox", home / "Dropbox"),
        ("onedrive", "OneDrive", home / "Library/CloudStorage/OneDrive-Personal"),
    ]
    for g in sorted((home / "Library/CloudStorage").glob("GoogleDrive-*")):
        cands.insert(3, ("googledrive", "Google Drive", g / "My Drive"))
    return _present(cands)


def fs_roots(home: Path | None = None) -> list[dict]:
    """What `GET /api/fs/roots` answers: the cloud folders above, then two ordinary places worth one click.

    Downloads and Desktop are shortcuts for the folder browser, not services — a recording watched out of
    Downloads is still filed under the generic `folder` place, because there is no Downloads source to set
    anything for.
    """
    home = home or Path.home()
    return cloud_roots(home) + _present([
        ("downloads", "Downloads", home / "Downloads"),
        ("desktop", "Desktop", home / "Desktop"),
    ])


def source_key(source: str | None, source_volume: str | None = None, roots: list[dict] | None = None) -> str:
    """The place a recording came from, in the vocabulary the Sources page and the per-source settings use.

    ``source_volume`` is the watched folder's own path for a ``folder`` import (`importer.py` stores it), which is
    what resolves the three-way tie between iCloud, Dropbox and Google Drive. Pass ``roots`` when resolving more
    than one recording, so the filesystem is asked once rather than per row; leave it out and `cloud_roots()`
    answers. A folder under nothing in particular, or a row with no volume stored, stays the generic ``folder``.

    Rows written before the ``source`` column existed are NULL and are DJI mic files.
    """
    key = (source or "dji").strip() or "dji"
    if key == "folder":
        return _folder_place(source_volume, roots)
    return PLACE_NAMES.get(key, key)


def _folder_place(source_volume: str | None, roots: list[dict] | None = None) -> str:
    if not source_volume:
        return "folder"
    try:
        p = Path(source_volume).expanduser()
    except (OSError, ValueError, RuntimeError):
        return "folder"
    for r in (cloud_roots() if roots is None else roots):
        # `is_relative_to` rather than a string prefix: "~/Dropbox Archive" is not inside "~/Dropbox".
        try:
            if p.is_relative_to(r["path"]):
                return r["key"]
        except (OSError, ValueError):
            continue
    return "folder"


def resolve_by_source(by_source: dict | None, roots: list[dict] | None = None) -> dict[str, str]:
    """A ``summary_template_by_source`` map with its keys read as places.

    `settings.json` is a file a user can edit and one an older build wrote, so a key may still be a mechanism
    (``microphone``) rather than a place (``mic``). Resolving on read costs nothing — a place resolves to itself —
    and means a map written before this vocabulary existed keeps working instead of quietly doing nothing.
    """
    return {source_key(k, roots=roots): v for k, v in (by_source or {}).items() if isinstance(k, str) and k.strip()}
