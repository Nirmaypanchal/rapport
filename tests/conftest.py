import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture
def library(tmp_path, monkeypatch):
    """A scratch library in a temp folder. Never touches the user's real library."""
    from rapport.config import Library

    monkeypatch.setenv("RAPPORT_LIBRARY", str(tmp_path / "lib"))
    lib = Library(tmp_path / "lib")
    lib.update_settings({"open_browser": False, "summary_provider": "off", "min_file_age_sec": 0})
    return lib


@pytest.fixture
def db(library):
    from rapport.db import Database

    return Database(library.db_path)
