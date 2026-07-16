# Werewolf Rhythm Demo

A comedic four-lane rhythm game where muscular, goblin-like werewolves descend
toward a moonlit village. Hit the correct lanes, survive HOLD enemies, build
your score, and trigger a giant red warehouse AGV sweep every 50 points.

**Version:** 0.1.0-demo

## Download the Windows Demo

[Download the latest Windows demo](REPLACE_WITH_GITHUB_LATEST_RELEASE_LINK)

1. Download `WerewolfRhythm-Demo-Windows-v0.1.0.zip` from GitHub Releases.
2. Extract the **entire** archive (keep all files together).
3. Run `WerewolfRhythmDemo.exe`.
4. No installation or Python runtime is required.
5. The game works fully offline.

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
| Enter | Start |
| P | Pause / resume |
| Esc | Return to menu / quit |
| M | Mute |
| Enter or R | Restart from Results |
| C | Credits (from menu) |

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

Optional Windows rebuild:

```powershell
.\build_windows.ps1
```

Output: `dist\WerewolfRhythmDemo\WerewolfRhythmDemo.exe`

## Downloadable Windows build

The GitHub Release ZIP contains the full onedir package. Extract everything, then
run `WerewolfRhythmDemo.exe`. Do not move the EXE alone without its companion files.

## Privacy

Only local settings/high score are stored under:

`%LOCALAPPDATA%\WerewolfRhythmDemo\settings.json`

See [PRIVACY.md](PRIVACY.md).

## Art provenance

All werewolf enemies and the village background in this demo are generated
project artwork. Original prototype photographs and private audio are not included.
See [ART_PROVENANCE.md](ART_PROVENANCE.md).

## Known limitations

- Windows 10/11 64-bit demo only
- Keyboard controls only (no claimed controller support)
- Unsigned executable may show a Windows SmartScreen reputation warning
- No automatic updater
- No online leaderboard
- One escape currently ends the run (Game Over)
- Screenshots in `docs/images/` may still be placeholders

## Author

Ruixin Chen

## Portfolio notice

This repository is provided for personal gameplay, portfolio review, and
technical demonstration. See [PORTFOLIO_NOTICE.md](PORTFOLIO_NOTICE.md).
Third-party music remains under CC BY 4.0.
