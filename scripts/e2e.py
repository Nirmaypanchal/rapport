#!/usr/bin/env python3
"""End-to-end test on macOS: start the real backend on a scratch library, import a synthetic recording
(spoken by the system voices), wait for the real pipeline, and check transcript, speakers and search.

    scripts/e2e.py                      # uses .venv/bin/python (uv sync first)
    scripts/e2e.py --core PATH          # test a frozen sidecar (desktop/sidecar/dist/rapport-core/rapport-core
                                        #   or /Applications/Rapport.app/Contents/Resources/core/rapport-core)
Env: RAPPORT_E2E_MODEL (default mlx-community/whisper-base-mlx), RAPPORT_E2E_TIMEOUT seconds (default 900).
Exit code 0 on success. Prints a Markdown summary you can paste into sprint/log/.
"""
from __future__ import annotations

import argparse, json, os, secrets, shutil, socket, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LINES = [
    ("Samantha", "Good morning everyone. Today we are planning the marathon in October and the move to Lisbon."),
    ("Daniel", "Thanks. I will book the flights on Friday and send the itinerary to the whole team."),
    ("Samantha", "Perfect. Let us also remember to order the pastel notebooks for the workshop."),
]
EXPECT = ["marathon", "lisbon", "friday", "notebooks"]


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def make_fixture(dst: Path) -> Path:
    parts = []
    for i, (voice, text) in enumerate(LINES):
        aiff = dst / f"part{i}.aiff"
        subprocess.run(["say", "-v", voice, "-o", str(aiff), text], check=True)
        parts.append(aiff)
    lst = dst / "parts.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    out = dst / "TX01_MIC001_20260909_090000_e2e.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-ar", "16000", "-ac", "1", str(out)], check=True)
    return out


def api(base: str, token: str, path: str, body=None, method=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method or ("POST" if data else "GET"))
    req.add_header("Authorization", f"Bearer {token}")
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or b"null")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--core", help="frozen sidecar executable to test instead of the source tree")
    ap.add_argument("--keep", action="store_true", help="keep the scratch library")
    a = ap.parse_args()
    model = os.environ.get("RAPPORT_E2E_MODEL", "mlx-community/whisper-base-mlx")
    timeout = float(os.environ.get("RAPPORT_E2E_TIMEOUT", "900"))
    tmp = Path(tempfile.mkdtemp(prefix="rapport-e2e-"))
    lib = tmp / "library"; lib.mkdir()
    port, token = free_port(), secrets.token_hex(16)
    (lib / "settings.json").write_text(json.dumps({
        "open_browser": False, "port": port, "whisper_model": model, "diarizer": "builtin",
        "summary_provider": "off", "auto_summarize": False, "auto_import": False, "auto_import_voice_memos": False,
        "min_file_age_sec": 0,
    }))
    env = {**os.environ, "RAPPORT_LIBRARY": str(lib), "RAPPORT_TOKEN": token, "PYTHONUNBUFFERED": "1"}
    if a.core:
        cmd = [a.core]
    else:
        py = ROOT / ".venv" / "bin" / "python"
        cmd = [str(py if py.exists() else sys.executable), "-m", "rapport.sidecar"]
    log = open(tmp / "backend.log", "wb")
    t0 = time.time()
    proc = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=log)
    base = None
    try:
        # sidecar prints "READY <port>"; fall back to polling the port for the plain server
        while time.time() - t0 < 120 and proc.poll() is None:
            line = proc.stdout.readline().decode(errors="replace").strip()
            if line.startswith("READY"):
                port = int(line.split()[1]); base = f"http://127.0.0.1:{port}"; break
        if base is None:
            base = f"http://127.0.0.1:{port}"
        for _ in range(60):
            try:
                if api(base, token, "/api/health")["ok"]:
                    break
            except Exception:
                time.sleep(1)
        else:
            raise SystemExit("backend never became healthy; see " + str(tmp / "backend.log"))
        fixture = make_fixture(tmp)
        ids = api(base, token, "/api/import/path", {"path": str(fixture)})
        imported = ids.get("imported") if isinstance(ids, dict) else ids
        assert imported, f"import returned no recording: {ids}"
        rid = imported[0]
        t1 = time.time()
        rec = None
        while time.time() - t1 < timeout:
            rec = api(base, token, f"/api/recordings/{rid}")
            if rec["status"] in ("done", "error"):
                break
            time.sleep(3)
        assert rec and rec["status"] == "done", f"pipeline ended with {rec and rec['status']}: {rec and rec.get('error')}"
        text = " ".join(s["text"] for s in rec["segments"]).lower()
        missing = [w for w in EXPECT if w not in text]
        assert not missing, f"transcript missing {missing}: {text[:300]}"
        assert rec["segments"] and rec["segments"][0].get("words"), "no word timestamps"
        speakers = rec.get("speakers") or []
        assert len(speakers) >= 1, "no speakers detected"
        hits = api(base, token, "/api/search?q=marathon")
        assert any(h["recording_id"] == rid for h in hits), "search did not find the recording"
        secs = time.time() - t1
        print(f"\n## e2e OK\n- model: {model}\n- pipeline: {secs:.0f}s\n- speakers: {len(speakers)} (2 expected)\n- transcript: {text[:160]}…\n- library: {lib}")
        return 0
    except (AssertionError, SystemExit) as e:
        print(f"\n## e2e FAILED\n- {e}\n- log: {tmp / 'backend.log'}")
        a.keep = True
        return 1
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            proc.kill()
        log.close()
        if not a.keep:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
