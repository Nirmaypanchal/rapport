"""The one translation between the two words for "source": the mechanism on the row, and the place a user picks.

Nothing here needs a Mac: `cloud_roots` is built from a home directory these tests create, and `source_key`
takes the resolved roots so the filesystem can stay out of it entirely.
"""
from pathlib import Path

import pytest

from rapport.sources import cloud_roots, fs_roots, resolve_by_source, source_key

ICLOUD = "Library/Mobile Documents/com~apple~CloudDocs"


@pytest.fixture
def home(tmp_path):
    """A home directory with iCloud Drive, Dropbox, Google Drive and Downloads on it."""
    for rel in (ICLOUD, "Library/CloudStorage/Dropbox", "Library/CloudStorage/GoogleDrive-me@x.com/My Drive", "Downloads"):
        (tmp_path / rel).mkdir(parents=True)
    return tmp_path


def test_a_mechanism_is_renamed_to_the_place_the_sources_page_names(home):
    # The two spellings that differ, and the many that do not.
    assert source_key("microphone") == "mic"
    assert source_key("file") == "files"
    for same in ("dji", "usb", "voicememos", "granola", "omi", "notion"):
        assert source_key(same) == same


def test_a_recording_with_no_source_is_filed_as_dji():
    # `source` arrived after the first releases, so rows written before it are NULL and are DJI mic files.
    assert source_key(None) == "dji" and source_key("") == "dji" and source_key(" granola ") == "granola"


def test_a_watched_folder_is_the_service_that_syncs_it(home):
    roots = cloud_roots(home)
    assert source_key("folder", str(home / ICLOUD / "Recorder"), roots) == "icloud"
    assert source_key("folder", str(home / ICLOUD), roots) == "icloud", "the root itself, not only a folder inside it"
    assert source_key("folder", str(home / "Library/CloudStorage/Dropbox/Audio/2026"), roots) == "dropbox"
    assert source_key("folder", str(home / "Library/CloudStorage/GoogleDrive-me@x.com/My Drive/Meet"), roots) == "googledrive"


def test_a_folder_that_is_nobodys_stays_a_folder(home):
    roots = cloud_roots(home)
    assert source_key("folder", str(home / "Downloads"), roots) == "folder", "a browse shortcut is not a service"
    assert source_key("folder", str(home / "Recordings"), roots) == "folder"
    assert source_key("folder", None, roots) == "folder", "a row with no volume stored has nothing to resolve"
    # "~/Dropbox Archive" is not inside "~/Dropbox"; a string prefix would say it was.
    (home / "Dropbox").mkdir()
    assert source_key("folder", str(home / "Dropbox Archive"), cloud_roots(home)) == "folder"


def test_only_a_watched_folder_is_resolved_against_the_roots(home):
    # A one-off "import this folder" is filed as an imported file wherever the folder happens to sit.
    assert source_key("file", str(home / ICLOUD / "Voice"), cloud_roots(home)) == "files"


def test_cloud_roots_skips_what_is_not_on_this_mac(home):
    assert [r["key"] for r in cloud_roots(home)] == ["icloud", "dropbox", "googledrive"], "no OneDrive here"
    assert [r["key"] for r in fs_roots(home)] == ["icloud", "dropbox", "googledrive", "downloads"]
    assert cloud_roots(Path(home / "nothing-here")) == []


def test_one_dropbox_even_when_both_places_exist(home):
    (home / "Dropbox").mkdir()
    keys = [r["key"] for r in cloud_roots(home)]
    assert keys.count("dropbox") == 1
    assert dict((r["key"], r["path"]) for r in cloud_roots(home))["dropbox"] == str(home / "Library/CloudStorage/Dropbox")


def test_a_settings_map_written_in_the_old_words_still_matches(home):
    # A place resolves to itself, so reading the map costs nothing; a mechanism from an older build is translated
    # rather than quietly matching nothing.
    assert resolve_by_source({"microphone": "journal", "icloud": "meeting", "granola": "sales-call"}) == {
        "mic": "journal", "icloud": "meeting", "granola": "sales-call",
    }
    assert resolve_by_source(None) == {} and resolve_by_source({"  ": "meeting"}) == {}
