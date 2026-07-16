# macOS Test Report — Werewolf Rhythm Demo v0.1.0-demo

This document separates **CI-verifiable** results from checks that require
**physical Mac hardware**.

Do not mark interactive Mac gameplay as fully verified until the app has been
opened and played on real Apple Silicon and Intel machines.

## CI results (GitHub Actions)

| Check | Status |
| --- | --- |
| Native compilation (arm64 / x86_64) | CI (see workflow run) |
| `.app` bundle structure | CI |
| Architecture (`file` / `lipo`) | CI |
| Module imports | CI |
| Asset presence + load | CI |
| Chart generation (Easy/Normal/Hard) | CI |
| Restart-state logic (100 cycles) | CI |
| Packaged `--self-test` | CI |
| Ad-hoc signature structure | CI |
| Forbidden-asset scan | CI |

Update the Status column with the workflow run URL after the first successful
`build-macos.yml` execution.

## Manual physical Mac checks

| Check | Apple Silicon | Intel |
| --- | --- | --- |
| Real music playback (all 3 tracks) | MANUAL MAC TEST REQUIRED | MANUAL MAC TEST REQUIRED |
| Mute / pause / resume audio | MANUAL MAC TEST REQUIRED | MANUAL MAC TEST REQUIRED |
| Keyboard timing latency (DFJK) | MANUAL MAC TEST REQUIRED | MANUAL MAC TEST REQUIRED |
| Retina display layout (HUD/menu/Results/AGV/Credits) | MANUAL MAC TEST REQUIRED | MANUAL MAC TEST REQUIRED |
| Fullscreen switching | MANUAL MAC TEST REQUIRED | MANUAL MAC TEST REQUIRED |
| Window focus loss (pause + HOLD clear) | MANUAL MAC TEST REQUIRED | MANUAL MAC TEST REQUIRED |
| Gatekeeper first-launch / Open Anyway flow | MANUAL MAC TEST REQUIRED | MANUAL MAC TEST REQUIRED |
| Repeated interactive restart from Results | MANUAL MAC TEST REQUIRED | MANUAL MAC TEST REQUIRED |
| AGV animation appearance | MANUAL MAC TEST REQUIRED | MANUAL MAC TEST REQUIRED |
| HOLD key behavior | MANUAL MAC TEST REQUIRED | MANUAL MAC TEST REQUIRED |
| Command-Q / window close quit | MANUAL MAC TEST REQUIRED | MANUAL MAC TEST REQUIRED |

## Signing note

Current builds are **ad-hoc signed and not notarized**. See
[MACOS_SIGNING.md](MACOS_SIGNING.md).

## Expected release artifacts

- `WerewolfRhythm-Demo-macOS-AppleSilicon-v0.1.0.zip`
- `WerewolfRhythm-Demo-macOS-AppleSilicon-v0.1.0.sha256`
- `WerewolfRhythm-Demo-macOS-Intel-v0.1.0.zip`
- `WerewolfRhythm-Demo-macOS-Intel-v0.1.0.sha256`
