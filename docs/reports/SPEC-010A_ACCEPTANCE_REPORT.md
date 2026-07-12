# SPEC-010A Acceptance Report

**Date:** `2026-07-12`

**Acceptance:** `PASS`

**Push:** `FORBIDDEN`

## Icon Verification

- Master checksum remained unchanged before and after generation.
- Asset catalogue contains all required 16, 32, 64, 128, 256, 512, and 1024 pixel representations with correct macOS idiom/scale declarations.
- `iconutil` produced a valid macOS `.icns` resource.
- The bundled `.icns` is byte-identical to the generated canonical resource.
- `Info.plist` resolves `CFBundleIconFile` to `FragarachII.icns`.
- Visual inspection of the generated 1024px representation matches the approved master artwork.
- The complete bundle passes strict deep code-signature verification with its sealed icon resource.
- Launch Services registered the rebuilt application bundle.
- The running `FragarachII` application process was verified after rebuild.

Finder and Dock consume the registered bundle icon through `CFBundleIconFile`; Launchpad uses the same Launch Services registration when applicable.

## Regression

```text
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Result: **114 tests passed**.

```text
swift run OperationsCoreChecks
```

Result: **13 native checks passed**.

```text
./script/build_and_run.sh --verify
codesign --verify --deep --strict "dist/Fragarach II.app"
```

Result: **build, bundle launch, running-process verification, and strict signature verification passed**.

SPEC-010A is accepted locally. No push was performed.
