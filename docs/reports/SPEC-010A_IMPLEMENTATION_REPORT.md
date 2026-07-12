# SPEC-010A Implementation Report

**Date:** `2026-07-12`

**Result:** `IMPLEMENTED`

**Push:** `FORBIDDEN`

## Branding Source

The supplied master was normalized from `fragarach_2 icon.png` to the specified `docs/icon/fragarach_2_icon.png` path without changing its bytes. Its SHA-256 remains:

```text
409126aab33aba1464aa2f7de2af919cb0822af2dddda94cc62557e2e59e6604
```

The master is 1254 × 1254 RGB PNG artwork without an alpha channel. Generated files retain the source image content and do not introduce artwork edits.

## Integration

`script/generate_app_icon.sh` validates the master, generates the ten macOS 1×/2× PNG renditions from 16px through 1024px, populates `assets/macos/Assets.xcassets/AppIcon.appiconset`, and compiles `assets/macos/FragarachII.icns` through `iconutil`.

The existing SwiftPM bundle script now:

1. regenerates icon assets from the master;
2. embeds `FragarachII.icns` under `Contents/Resources`;
3. declares `CFBundleIconFile=FragarachII.icns`;
4. ad-hoc signs the completed resource-bearing application bundle;
5. launches through the existing `/usr/bin/open -n` path.

The master remains outside the generated asset catalogue and is documented in `docs/icon/README.md`.

No application source behavior, schema, migration, or authority logic changed.
