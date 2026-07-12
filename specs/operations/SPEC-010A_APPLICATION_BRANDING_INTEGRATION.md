# SPEC-010A — Application Branding Integration

**Document ID:** `SPEC-010A_APPLICATION_BRANDING_INTEGRATION`

**Repository:** `/Users/raymorgan/VSC/Fragarach_2`

**Status:** Implementation

**Authority:** Candidate Authority

**Doctrine:** Operations is King

**Push:** Forbidden

## Objective

Replace the temporary Fragarach II application icon with the approved operational icon.

## Source

Use `docs/icon/fragarach_2_icon.png` as immutable master artwork.

## Requirements

- Generate every required macOS AppIcon size from the master.
- Populate a valid Xcode asset catalogue.
- Generate and embed the `.icns` required by the SwiftPM application bundle.
- Preserve source transparency where present and never modify the master artwork.
- Remove temporary icon references.
- Rebuild, sign, register, launch, and verify the icon-bearing bundle.
- Change no application behaviour, schema, or migration.
- Do not push.

## Acceptance

- Application builds and launches successfully.
- The built `.app` declares and contains the approved icon.
- Finder, Dock, Launch Services, and the running application resolve the icon-bearing bundle.
- Existing Python and native suites remain green.
- Create one local checkpoint and do not push.
