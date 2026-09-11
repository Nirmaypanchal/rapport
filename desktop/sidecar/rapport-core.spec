# PyInstaller spec for the Rapport backend sidecar (one-dir bundle).
# Build with: desktop/sidecar/build.sh
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata

ROOT = Path(SPECPATH).resolve().parents[1]
BIN = ROOT / "desktop" / "sidecar" / "bin"

datas, binaries, hiddenimports = [], [], []
# Packages that load data files / extension modules dynamically.
for pkg in ["mlx", "mlx_whisper", "mlx_lm", "pyannote.audio", "pyannote.core", "pyannote.pipeline", "pyannote.database", "pyannote.metrics",
            "silero_vad", "torchaudio", "torchcodec", "lightning_fabric", "pytorch_lightning", "torchmetrics", "asteroid_filterbanks",
            "speechbrain", "transformers", "tokenizers", "huggingface_hub", "safetensors", "sklearn", "scipy", "numpy", "soundfile",
            "tiktoken", "tiktoken_ext", "regex", "einops", "omegaconf", "hydra", "rich", "typer", "pyannoteai"]:
    try:
        d, b, h = collect_all(pkg)
        datas += d; binaries += b; hiddenimports += h
    except Exception as e:  # optional packages
        print("skip", pkg, e)
for pkg in ["torch"]:
    hiddenimports += collect_submodules(pkg)
for pkg in ["rapport", "torch", "torchaudio", "transformers", "tokenizers", "huggingface_hub", "safetensors", "mlx", "mlx_lm", "mlx_whisper", "pyannote.audio", "lightning", "pytorch_lightning", "numpy", "scipy", "scikit-learn", "silero_vad", "fastapi", "uvicorn", "starlette", "pydantic", "tqdm", "filelock", "packaging", "pyyaml", "requests", "regex", "tiktoken", "sentencepiece", "protobuf"]:
    try:
        datas += copy_metadata(pkg)
    except Exception:
        pass
hiddenimports += ["uvicorn.logging", "uvicorn.loops", "uvicorn.loops.auto", "uvicorn.protocols", "uvicorn.protocols.http", "uvicorn.protocols.http.auto",
                  "uvicorn.protocols.websockets", "uvicorn.protocols.websockets.auto", "uvicorn.lifespan", "uvicorn.lifespan.on", "multipart", "python_multipart",
                  "rapport.sidecar", "rapport.mcp", "sklearn.cluster", "sklearn.utils._typedefs", "sklearn.neighbors._partition_nodes", "scipy.special._cdflib"]

# Static ffmpeg/ffprobe travel in bin/ next to the executable.
binaries += [(str(BIN / "ffmpeg"), "bin"), (str(BIN / "ffprobe"), "bin")]

# Summary templates are read from disk at runtime, so the Markdown files have to travel with the bundle.
datas += [(str(ROOT / "rapport" / "templates"), "rapport/templates")]

a = Analysis(
    [str(ROOT / "desktop" / "sidecar" / "entry.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    excludes=["tkinter", "matplotlib.tests", "IPython", "jupyter", "notebook", "PyQt5", "PySide2", "PySide6", "wx"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="rapport-core", debug=False, strip=False, upx=False, console=True,
          target_arch="arm64", codesign_identity=None, entitlements_file=None)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="rapport-core")
