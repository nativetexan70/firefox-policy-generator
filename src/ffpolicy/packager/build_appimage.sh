#!/usr/bin/env bash
set -euo pipefail

APP=ffpolicy
VERSION="${1:-0.1.0}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
DIST="$ROOT/dist"
APPDIR="$DIST/$APP.AppDir"

cd "$ROOT"

# 1. Clean
rm -rf build "$DIST"
mkdir -p "$DIST"

# 2. Freeze the app with PyInstaller (onedir keeps AppImage layout clean)
pyinstaller --noconfirm --clean src/ffpolicy/packager/ffpolicy.spec

# 3. Assemble AppDir
mkdir -p "$APPDIR/usr/bin"
cp -r "dist/$APP/"* "$APPDIR/usr/bin/"
cp src/ffpolicy/packager/$APP.desktop "$APPDIR/$APP.desktop"
cp src/ffpolicy/resources/icons/$APP.png "$APPDIR/$APP.png"

# 4. AppRun shim
cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"
exec "$HERE/usr/bin/ffpolicy" "$@"
EOF
chmod +x "$APPDIR/AppRun"

# 5. Build the AppImage. appimagetool is itself an AppImage that needs FUSE
# to run directly; --appimage-extract-and-run avoids that requirement, which
# CI runners (and some desktop distros) don't have set up by default.
ARCH=x86_64 appimagetool --appimage-extract-and-run "$APPDIR" "$DIST/$APP-$VERSION-x86_64.AppImage"

echo "Built $DIST/$APP-$VERSION-x86_64.AppImage"
