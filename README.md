# Werewolf Rhythm Demo

A comedic four-lane rhythm game where muscular, goblin-like werewolves descend
toward a moonlit village. Hit the correct lanes, survive HOLD enemies, build
your score, and trigger a giant red warehouse AGV sweep every 50 points.

**Version:** 0.1.0-demo

## Download the Windows Demo

[Download the latest Windows demo](https://github.com/MarcyChen-ruixin/werewolf-rhythm-demo/releases/latest)

1. Download `WerewolfRhythm-Demo-Windows-v0.1.0.zip` from GitHub Releases.
2. Extract the **entire** archive (keep all files together).
3. Run `WerewolfRhythmDemo.exe`.
4. No installation or Python runtime is required.
5. The game works fully offline.

## Download for macOS

Choose the build that matches your Mac:

| Mac type | How to tell | Download (GitHub Releases) |
| --- | --- | --- |
| Apple Silicon | Apple menu → About This Mac → Chip (M1/M2/M3/M4…) | `WerewolfRhythm-Demo-macOS-AppleSilicon-v0.1.0.zip` |
| Intel | Apple menu → About This Mac → Processor (Intel) | `WerewolfRhythm-Demo-macOS-Intel-v0.1.0.zip` |

Placeholder release links (replace with the published asset URLs after upload):

- Apple Silicon Mac download: see GitHub Releases → `WerewolfRhythm-Demo-macOS-AppleSilicon-v0.1.0.zip`
- Intel Mac download: see GitHub Releases → `WerewolfRhythm-Demo-macOS-Intel-v0.1.0.zip`

### Installation (macOS)

1. Download the correct ZIP for your Mac.
2. Extract the ZIP.
3. Drag `Werewolf Rhythm Demo.app` into Applications if desired.
4. Open the application.
5. Keep all content inside the `.app` bundle intact.

The current GitHub Demo is **ad-hoc signed and not notarized**.

After attempting to open the app, macOS may show an unidentified-developer
warning. Confirm the file came from the official GitHub repository. Then open
**System Settings → Privacy & Security** and use **Open Anyway** only when you
trust the downloaded file.

Do not disable macOS security protections / Gatekeeper globally.

macOS builds:

- Work offline
- Require no Python installation
- Use keyboard controls only
- Include no analytics, account system, or network services

See [docs/MACOS_SIGNING.md](docs/MACOS_SIGNING.md) and
[docs/MACOS_TEST_REPORT.md](docs/MACOS_TEST_REPORT.md).

## Gameplay preview

Screenshot placeholders (replace with public sanitized captures):

| Screen | Path |
| --- | --- |
| Menu | `docs/images/menu.png` |
| Gameplay | `docs/images/gameplay.png` |
| HOLD note | `docs/images/hold-note.png` |
| AGV sweep | `docs/images/agv-sweep.png` |
| Results | `docs/images/results.png` |

## Features

- Three selectable comedic music tracks (Kevin MacLeod, CC BY 4.0)
- Easy / Normal / Hard difficulties with song-specific BPM charts
- Four-lane rhythm gameplay
- Short-note werewolf enemies and multi-frame HOLD enemies
- Score, Combo, Accuracy, Defeated, Escaped, and AGV Cleared
- Recurring red AGV reward every **50** score points (large, slow sweep)
- Pause, mute, credits, Results restart with countdown
- Silent-mode fallback if audio cannot load
- Offline play — no account, no analytics

## Controls

| Key | Action |
| --- | --- |
| DFJK | Four rhythm lanes (Tab switches to ASKL) |
| 1 / 2 / 3 | Select song |
| F1 / F2 / F3 | Select difficulty |
| Enter / Return | Start |
| P | Pause / resume |
| Esc | Return to menu / quit |
| M | Mute |
| Enter / Return or R | Restart from Results |
| C | Credits (from menu) |

On macOS, both the main Return key and the keypad Enter key are supported where
practical. Rhythm lanes do not require Command, Control, or Option. Command-Q
and the window close button quit cleanly; the game does not intercept system
shortcuts for lane input.

## Songs and credits

Music by **Kevin MacLeod** (incompetech.com), licensed under **CC BY 4.0**
(not public domain):

1. Monkeys Spinning Monkeys  
2. Fluffing a Duck  
3. Sneaky Snitch  

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and the in-game Credits screen (press **C** on the menu).

## AGV reward

Every **50** score points, a large red warehouse AGV slowly sweeps left to right
and clears up to one eligible enemy per lane. AGV clears increase Defeated /
AGV Cleared and **do not** add score. Milestones queue one at a time (50, 100, 150, …).

## Installation from source

```powershell
python -m pip install -r requirements.txt
python rhythm_game.py
```

On macOS:

```bash
python3 -m pip install -r requirements-macos.txt
python3 rhythm_game.py
```

Optional Windows rebuild:

```powershell
.\build_windows.ps1
```

Output: `dist\WerewolfRhythmDemo\WerewolfRhythmDemo.exe`

Optional macOS rebuild (must run on a Mac or GitHub-hosted macOS runner):

```bash
chmod +x build_macos.sh
./build_macos.sh
```

Output: `dist/Werewolf Rhythm Demo.app` plus architecture-specific ZIP under
`dist/release/`.

## Downloadable builds

### Windows

The GitHub Release ZIP contains the full onedir package. Extract everything, then
run `WerewolfRhythmDemo.exe`. Do not move the EXE alone without its companion files.

### macOS

Download the Apple Silicon or Intel ZIP, extract it, then open
`Werewolf Rhythm Demo.app`. Separate native builds are provided (not Universal).

## Privacy

Only local settings/high score are stored:

- Windows: `%LOCALAPPDATA%\WerewolfRhythmDemo\settings.json`
- macOS: `~/Library/Application Support/Werewolf Rhythm Demo/settings.json`

See [PRIVACY.md](PRIVACY.md).

## Art provenance

All werewolf enemies and the village background in this demo are generated
project artwork. Original prototype photographs and private audio are not included.
See [ART_PROVENANCE.md](ART_PROVENANCE.md).

## Known limitations

- Windows 10/11 64-bit and macOS (Apple Silicon + Intel) demos
- Keyboard controls only (no claimed controller support)
- Unsigned Windows executable may show a SmartScreen reputation warning
- macOS builds are ad-hoc signed and not notarized (manual Privacy & Security approval may be required)
- No automatic updater
- No online leaderboard
- One escape currently ends the run (Game Over)
- Screenshots in `docs/images/` may still be placeholders
- Full interactive macOS GUI verification still requires physical Mac hardware

## Author

Ruixin Chen

## Portfolio notice

This repository is provided for personal gameplay, portfolio review, and
technical demonstration. See [PORTFOLIO_NOTICE.md](PORTFOLIO_NOTICE.md).
Third-party music remains under CC BY 4.0.
