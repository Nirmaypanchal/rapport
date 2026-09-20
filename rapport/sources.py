"""Where a recording came from, as a *place* rather than as a mechanism.

Two vocabularies met in the middle of this app and did not match. The ``recordings.source`` column names the
mechanism Rapport used to get a file — ``folder``, ``usb``, ``microphone``, ``file``, ``voicememos``, ``granola``
— which is what import dedup and the connectors need, and must not change. The Sources page names *places*:
``mic``, ``files``, ``icloud``, ``dropbox``, ``googledrive``, ``onedrive``, ``zoom``, and a generic ``folder`` for
everything else. A user choosing "a summary template for my iCloud recorder" is choosing a place, so anything
offered next to that choice has to speak the second vocabulary (`sprint/decisions.md`, 2026-09-14).

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


def place_roots(home: Path | None = None) -> list[dict]:
    """The folders on this Mac that are a place of their own: the ones a watched folder can belong to.

    Two kinds of thing are here, and they earn their place the same way — a tile on the Sources page names them, so
    a recording that arrives from one is worth filing under it rather than under a generic "watched folder". The
    cloud services sync a folder (iCloud Drive, Dropbox, Google Drive, OneDrive); an app writes one (Zoom saves its
    local recordings to ``~/Documents/Zoom``). A folder under any of these belongs to it however deep, which is the
    same rule `sources-view.tsx` uses client-side to decide which tile a watched folder is listed under.

    Order is resolution order, but the entries do not overlap: Zoom's folder is only Zoom's when the path really is
    ``~/Documents/Zoom``. With Desktop & Documents syncing to iCloud, a path browsed in through the iCloud tile
    (`…/CloudDocs/Documents/Zoom`) resolves to iCloud instead, which is what the user picked and what the Sources
    page already lists it under.
    """
    home = home or Path.home()
    cands = [
        ("icloud", "iCloud Drive", home / "Library/Mobile Documents/com~apple~CloudDocs"),
        ("dropbox", "Dropbox", home / "Library/CloudStorage/Dropbox"),
        ("dropbox", "Dropbox", home / "Dropbox"),
        ("onedrive", "OneDrive", home / "Library/CloudStorage/OneDrive-Personal"),
        ("zoom", "Zoom", home / "Documents/Zoom"),
    ]
    for g in sorted((home / "Library/CloudStorage").glob("GoogleDrive-*")):
        cands.insert(3, ("googledrive", "Google Drive", g / "My Drive"))
    return _present(cands)


def fs_roots(home: Path | None = None) -> list[dict]:
    """What `GET /api/fs/roots` answers: the places above, then two ordinary folders worth one click.

    Downloads and Desktop are shortcuts for the folder browser, not places — a recording watched out of
    Downloads is still filed under the generic `folder` place, because there is no Downloads source to set
    anything for. That is the whole difference between the two lists: a tile, and a template you could set for it.
    """
    home = home or Path.home()
    return place_roots(home) + _present([
        ("downloads", "Downloads", home / "Downloads"),
        ("desktop", "Desktop", home / "Desktop"),
    ])


def source_key(source: str | None, source_volume: str | None = None, roots: list[dict] | None = None) -> str:
    """The place a recording came from, in the vocabulary the Sources page and the per-source settings use.

    ``source_volume`` is the watched folder's own path for a ``folder`` import (`importer.py` stores it), which is
    what resolves the three-way tie between iCloud, Dropbox and Google Drive. Pass ``roots`` when resolving more
    than one recording, so the filesystem is asked once rather than per row; leave it out and `place_roots()`
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
    for r in (place_roots() if roots is None else roots):
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
