#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-run}"
APP_NAME="FragarachLite"
BUNDLE_NAME="Fragarach Lite"
BUNDLE_ID="com.raymorgan.fragarach-lite.app"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_BUNDLE="$ROOT_DIR/dist/$BUNDLE_NAME.app"
CONTENTS="$APP_BUNDLE/Contents"
MACOS="$CONTENTS/MacOS"
RESOURCES="$CONTENTS/Resources"
INFO="$CONTENTS/Info.plist"
ICON="$ROOT_DIR/assets/macos/FragarachLite.icns"

cd "$ROOT_DIR"
swift build -c release --product "$APP_NAME"
BUILD_BINARY="$(swift build -c release --show-bin-path)/$APP_NAME"
rm -rf "$APP_BUNDLE"
mkdir -p "$MACOS" "$RESOURCES"
cp "$BUILD_BINARY" "$MACOS/$APP_NAME"
cp "$ICON" "$RESOURCES/FragarachLite.icns"
chmod +x "$MACOS/$APP_NAME"
/usr/libexec/PlistBuddy -c 'Clear dict' "$INFO" 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Add :CFBundleExecutable string $APP_NAME" "$INFO"
/usr/libexec/PlistBuddy -c "Add :CFBundleIdentifier string $BUNDLE_ID" "$INFO"
/usr/libexec/PlistBuddy -c "Add :CFBundleName string $BUNDLE_NAME" "$INFO"
/usr/libexec/PlistBuddy -c 'Add :CFBundleIconFile string FragarachLite.icns' "$INFO"
/usr/libexec/PlistBuddy -c 'Add :CFBundleShortVersionString string 2.0' "$INFO"
/usr/libexec/PlistBuddy -c 'Add :CFBundleVersion string 16' "$INFO"
/usr/libexec/PlistBuddy -c 'Add :CFBundlePackageType string APPL' "$INFO"
/usr/libexec/PlistBuddy -c 'Add :LSMinimumSystemVersion string 14.0' "$INFO"
/usr/libexec/PlistBuddy -c 'Add :NSPrincipalClass string NSApplication' "$INFO"
/usr/bin/codesign --force --deep --sign - "$APP_BUNDLE"

case "$MODE" in
  --build-only|build) ;;
  run) pkill -x "$APP_NAME" 2>/dev/null || true; /usr/bin/open -n "$APP_BUNDLE" ;;
  --verify|verify) pkill -x "$APP_NAME" 2>/dev/null || true; /usr/bin/open -n "$APP_BUNDLE"; sleep 5; pgrep -x "$APP_NAME" >/dev/null ;;
  *) echo "usage: $0 [run|--build-only|--verify]" >&2; exit 2 ;;
esac
