#!/usr/bin/env bash
# Backend tests that need no ML models or Apple silicon. Works on Linux (cloud agents, CI) and macOS.
# Uses a throwaway virtualenv with only the light dependencies so it never tries to install mlx/torch.
set -euo pipefail
cd "$(dirname "$0")/.."
command -v uv >/dev/null 2>&1 || { curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null; export PATH="$HOME/.local/bin:$PATH"; }
VENV="${RAPPORT_LIGHT_VENV:-.venv-light}"
[ -d "$VENV" ] || uv venv -q "$VENV" --python 3.12
uv pip install -q --python "$VENV/bin/python" fastapi "uvicorn[standard]" numpy soundfile python-multipart httpx pytest
exec "$VENV/bin/python" -m pytest -q tests "$@"
