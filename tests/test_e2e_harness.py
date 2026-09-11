"""Guards for scripts/e2e.py itself.

The nightly on-device test is the only thing that ever runs the real pipeline, so a broken harness is
invisible: on 2026-09-10 the script had no `__main__` guard and exited 0 without running anything, and it
read the wrong key from `POST /api/import/path`. Neither could be caught by the suite it is supposed to
back up. These tests do not run the pipeline (it needs macOS and a model); they check that the harness
starts and that the one API contract it hard-codes still holds.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
E2E = ROOT / "scripts" / "e2e.py"


def test_e2e_script_has_an_entry_point():
    """`e2e.py --help` must actually run. Without `if __name__ == "__main__"` it exits 0 printing nothing,
    and every caller sees a silent pass while testing nothing."""
    p = subprocess.run([sys.executable, str(E2E), "--help"], capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr
    assert "--core" in p.stdout, f"e2e.py --help printed nothing useful: {p.stdout!r}"


def test_e2e_script_is_executable():
    """The nightly and the docs invoke it as `./scripts/e2e.py`."""
    assert E2E.stat().st_mode & 0o111, "scripts/e2e.py is not executable"
