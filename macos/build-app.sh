#!/bin/bash
# Build "yt down.app" and yt-down-mac.dmg. Run on macOS from the repository root:
#   macos/build-app.sh 1.0.1 dist
# The app bundles the sources and a universal uv; at launch it opens Terminal running
# start-mac.command, which prepares Python + dependencies outside the bundle and updates yt-dlp.
set -euo pipefail

VERSION="${1:?version}"
OUT="${2:-dist}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$OUT/yt down.app"
RES="$APP/Contents/Resources/app"

rm -rf "$APP" "$OUT/yt-down-mac.dmg"
mkdir -p "$APP/Contents/MacOS" "$RES/bin"

# Sources and launcher.
rsync -a --exclude __pycache__ --exclude '*.pyc' "$ROOT/src" "$RES/"
cp "$ROOT/pyproject.toml" "$ROOT/uv.lock" "$ROOT/README.md" "$ROOT/start-mac.command" "$RES/"
chmod +x "$RES/start-mac.command"

# Universal uv (Apple Silicon + Intel).
TMP="$(mktemp -d)"
for arch in aarch64 x86_64; do
  curl -fsSL "https://github.com/astral-sh/uv/releases/latest/download/uv-$arch-apple-darwin.tar.gz" \
    | tar -xz -C "$TMP"
  mv "$TMP/uv-$arch-apple-darwin/uv" "$TMP/uv-$arch"
done
lipo -create "$TMP/uv-aarch64" "$TMP/uv-x86_64" -output "$RES/bin/uv"
chmod +x "$RES/bin/uv"
rm -rf "$TMP"

cp "$ROOT/macos/launcher.sh" "$APP/Contents/MacOS/yt-down"
chmod +x "$APP/Contents/MacOS/yt-down"

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>yt down</string>
  <key>CFBundleDisplayName</key><string>yt down</string>
  <key>CFBundleIdentifier</key><string>app.ytdown.launcher</string>
  <key>CFBundleVersion</key><string>$VERSION</string>
  <key>CFBundleShortVersionString</key><string>$VERSION</string>
  <key>CFBundleExecutable</key><string>yt-down</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
</dict>
</plist>
PLIST

# Ad-hoc signature: required for the bundled binary on Apple Silicon. Not notarized.
codesign --force --deep --sign - "$APP"

STAGE="$(mktemp -d)"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
hdiutil create -quiet -volname "yt down" -srcfolder "$STAGE" -format UDZO "$OUT/yt-down-mac.dmg"
rm -rf "$STAGE"
echo "Built: $APP and $OUT/yt-down-mac.dmg"
