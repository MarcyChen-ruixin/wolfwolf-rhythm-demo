"""Validate all song × difficulty chart combinations."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from chart_gen import (  # noqa: E402
    SONG_CATALOG,
    generate_chart,
    validate_chart_data,
)


def measure_duration(song: dict) -> float:
    audio = ROOT / song["file"]
    if audio.is_file():
        try:
            import pygame

            pygame.mixer.init()
            length = float(pygame.mixer.Sound(str(audio)).get_length())
            pygame.mixer.quit()
            return length
        except Exception as exc:
            print(f"  (duration fallback for {song['id']}: {exc})")
    return float(song["fallback_duration"])


def main() -> int:
    all_ok = True
    for song in SONG_CATALOG:
        duration = measure_duration(song)
        print(f"\n### {song['title']}  BPM={song['bpm']}  duration={duration:.3f}s")
        for diff in ("Easy", "Normal", "Hard"):
            events = generate_chart(song, diff, duration_sec=duration)
            report = validate_chart_data(events, song, diff, duration)
            status = "PASS" if report["ok"] else "FAIL"
            warn = f"  WARN {report['warnings']}" if report["warnings"] else ""
            print(
                f"  [{status}] {diff}: notes={report['total_notes']} "
                f"short={report['short_notes']} hold={report['hold_notes']} "
                f"groups={report['note_groups']} max_active={report['max_simultaneous_active']} "
                f"min_sp={report['min_spacing_beats']} max_gap={report['max_gap_beats']} "
                f"npm={report['notes_per_minute']}{warn}"
            )
            if report["failures"]:
                print(f"       failures: {report['failures']}")
                all_ok = False

    print("\n" + ("ALL CHARTS PASSED" if all_ok else "VALIDATION FAILED"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
