#!/bin/zsh
# Freeze the Python backend into desktop/sidecar/dist/rapport-core/ (one-dir bundle with ffmpeg inside).
set -e
cd "$(dirname "$0")/../.."
# Static ffmpeg/ffprobe for Apple silicon (not committed; ~63 MB each). Source: https://ffmpeg.martin-riedl.de
mkdir -p desktop/sidecar/bin
for tool in ffmpeg ffprobe; do
  if [ ! -x "desktop/sidecar/bin/$tool" ]; then
    echo "Downloading static $tool…"
    curl -sL --fail -o "/tmp/$tool.zip" "https://ffmpeg.martin-riedl.de/redirect/latest/macos/arm64/release/$tool.zip"
    unzip -o -q "/tmp/$tool.zip" -d desktop/sidecar/bin && rm "/tmp/$tool.zip"
    chmod +x "desktop/sidecar/bin/$tool"
  fi
done
desktop/sidecar/bin/ffmpeg -version | head -1
rm -rf desktop/sidecar/build desktop/sidecar/dist
.venv/bin/pyinstaller --noconfirm --clean --distpath desktop/sidecar/dist --workpath desktop/sidecar/build desktop/sidecar/rapport-core.spec
du -sh desktop/sidecar/dist/rapport-core
echo "built desktop/sidecar/dist/rapport-core/rapport-core"
