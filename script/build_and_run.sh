#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-run}"
APP_NAME="FragarachII"
BUNDLE_NAME="Fragarach II"
BUNDLE_ID="com.raymorgan.fragarach-ii.operations"
MIN_SYSTEM_VERSION="14.0"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="$ROOT_DIR/dist"
APP_BUNDLE="$DIST_DIR/$BUNDLE_NAME.app"
APP_CONTENTS="$APP_BUNDLE/Contents"
APP_MACOS="$APP_CONTENTS/MacOS"
APP_BINARY="$APP_MACOS/$APP_NAME"
INFO_PLIST="$APP_CONTENTS/Info.plist"
SOURCE_REVISION="$(git -C "$ROOT_DIR" rev-parse --short=12 HEAD)"
BUILD_ID="$SOURCE_REVISION"
if [[ -n "$(git -C "$ROOT_DIR" status --porcelain)" ]]; then
  BUILD_ID="${SOURCE_REVISION}-local-$(date -u +%Y%m%d%H%M%S)"
fi
ICON_SOURCE="$ROOT_DIR/assets/macos/FragarachII.icns"

pkill -x "$APP_NAME" >/dev/null 2>&1 || true
cd "$ROOT_DIR"
./script/generate_app_icon.sh
swift build -c release
BUILD_BINARY="$(swift build -c release --show-bin-path)/$APP_NAME"
rm -rf "$APP_BUNDLE"
mkdir -p "$APP_MACOS"
mkdir -p "$APP_CONTENTS/Resources"
cp "$BUILD_BINARY" "$APP_BINARY"
cp "$ICON_SOURCE" "$APP_CONTENTS/Resources/FragarachII.icns"
chmod +x "$APP_BINARY"

/usr/libexec/PlistBuddy -c 'Clear dict' "$INFO_PLIST" 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Add :CFBundleExecutable string $APP_NAME" "$INFO_PLIST"
/usr/libexec/PlistBuddy -c "Add :CFBundleIdentifier string $BUNDLE_ID" "$INFO_PLIST"
/usr/libexec/PlistBuddy -c "Add :CFBundleName string $BUNDLE_NAME" "$INFO_PLIST"
/usr/libexec/PlistBuddy -c 'Add :CFBundleIconFile string FragarachII.icns' "$INFO_PLIST"
/usr/libexec/PlistBuddy -c 'Add :CFBundlePackageType string APPL' "$INFO_PLIST"
/usr/libexec/PlistBuddy -c "Add :CFBundleVersion string $BUILD_ID" "$INFO_PLIST"
/usr/libexec/PlistBuddy -c "Add :LSMinimumSystemVersion string $MIN_SYSTEM_VERSION" "$INFO_PLIST"
/usr/libexec/PlistBuddy -c 'Add :NSPrincipalClass string NSApplication' "$INFO_PLIST"
/usr/bin/codesign --force --deep --sign - "$APP_BUNDLE"

open_app() {
  local args=()
  if [[ -n "${FRAGARACH_LAUNCH_MODE:-}" ]]; then
    args+=(--mode "$FRAGARACH_LAUNCH_MODE")
    if [[ -n "${FRAGARACH_LAUNCH_SYMBOL:-}" ]]; then
      args+=(--symbol "$FRAGARACH_LAUNCH_SYMBOL")
    fi
  fi
  if [[ "${FRAGARACH_SCHEDULER_DISABLED:-0}" == "1" ]]; then
    args+=(--disable-scheduler)
  fi
  if [[ ${#args[@]} -gt 0 ]]; then /usr/bin/open -n "$APP_BUNDLE" --args "${args[@]}"; else /usr/bin/open -n "$APP_BUNDLE"; fi
}
case "$MODE" in
  run) open_app ;;
  --debug|debug) lldb -- "$APP_BINARY" ;;
  --logs|logs) open_app; /usr/bin/log stream --info --style compact --predicate "process == '$APP_NAME'" ;;
  --telemetry|telemetry) open_app; /usr/bin/log stream --info --style compact --predicate "subsystem == '$BUNDLE_ID'" ;;
  --verify|verify) open_app; sleep 8; pgrep -x "$APP_NAME" >/dev/null; echo "Fragarach II signed bundle launched and remained alive" ;;
  *) echo "usage: $0 [run|--debug|--logs|--telemetry|--verify]" >&2; exit 2 ;;
esac
