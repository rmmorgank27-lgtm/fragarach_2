#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MASTER="$ROOT_DIR/docs/icon/fragarach_2_icon.png"
ASSET_ROOT="$ROOT_DIR/assets/macos/Assets.xcassets/AppIcon.appiconset"
ICNS="$ROOT_DIR/assets/macos/FragarachII.icns"
TEMP_DIR="$(mktemp -d)"
ICONSET="$TEMP_DIR/FragarachII.iconset"
trap 'rm -rf "$TEMP_DIR"' EXIT

test -f "$MASTER"
WIDTH="$(sips -g pixelWidth "$MASTER" | awk '/pixelWidth/{print $2}')"
HEIGHT="$(sips -g pixelHeight "$MASTER" | awk '/pixelHeight/{print $2}')"
test "$WIDTH" = "$HEIGHT"
test "$WIDTH" -ge 1024

mkdir -p "$ASSET_ROOT" "$ICONSET"
for size in 16 32 128 256 512; do
  double=$((size * 2))
  sips -z "$size" "$size" "$MASTER" --out "$ASSET_ROOT/icon_${size}x${size}.png" >/dev/null
  sips -z "$double" "$double" "$MASTER" --out "$ASSET_ROOT/icon_${size}x${size}@2x.png" >/dev/null
  cp "$ASSET_ROOT/icon_${size}x${size}.png" "$ICONSET/icon_${size}x${size}.png"
  cp "$ASSET_ROOT/icon_${size}x${size}@2x.png" "$ICONSET/icon_${size}x${size}@2x.png"
done

if [[ ! -f "$ASSET_ROOT/Contents.json" ]]; then
  echo "missing AppIcon Contents.json" >&2
  exit 1
fi

rm -f "$ICNS"
iconutil -c icns "$ICONSET" -o "$ICNS"
