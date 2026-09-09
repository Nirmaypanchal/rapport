#!/usr/bin/env bash
# Set the product version everywhere it appears. Usage: scripts/bump_version.sh 0.2.0
set -euo pipefail
cd "$(dirname "$0")/.."
V="${1:?version like 0.2.0}"
[[ "$V" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "bad version: $V"; exit 1; }
sed -i.bak -E "s/^version = \"[0-9.]+\"/version = \"$V\"/" pyproject.toml desktop/app/src-tauri/Cargo.toml
sed -i.bak -E "s/\"version\": \"[0-9.]+\"/\"version\": \"$V\"/" desktop/app/src-tauri/tauri.conf.json frontend/package.json desktop/app/package.json
rm -f pyproject.toml.bak desktop/app/src-tauri/Cargo.toml.bak desktop/app/src-tauri/tauri.conf.json.bak frontend/package.json.bak desktop/app/package.json.bak
grep -n "\"version\"\|^version" pyproject.toml desktop/app/src-tauri/Cargo.toml desktop/app/src-tauri/tauri.conf.json frontend/package.json desktop/app/package.json
