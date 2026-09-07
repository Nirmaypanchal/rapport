#!/bin/zsh
# Build Rapport.app. Tauri copies resources by dereferencing symlinks, which breaks the frozen Python
# (libmlx.dylib must stay a symlink into mlx/lib next to mlx.metallib), so the core is copied here with cp -R.
set -e
cd "$(dirname "$0")"
export PATH="$HOME/.cargo/bin:$PATH"
[ -x ../sidecar/dist/rapport-core/rapport-core ] || { echo "build the sidecar first: desktop/sidecar/build.sh"; exit 1; }
[ -f ../../frontend/out/index.html ] || (cd ../../frontend && npm run build)
npx tauri build --bundles app "$@"
APP="src-tauri/target/release/bundle/macos/Rapport.app"
rm -rf "$APP/Contents/Resources/core"
cp -R ../sidecar/dist/rapport-core "$APP/Contents/Resources/core"
rm -rf "$APP/Contents/Resources/ui" && cp -R ../../frontend/out "$APP/Contents/Resources/ui"
echo "symlinks preserved: $(find "$APP/Contents/Resources/core" -type l | wc -l | tr -d ' ')"
du -sh "$APP"
echo "built $APP"
