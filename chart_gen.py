"""
Procedural chart generation for Werewolf Rhythm.

Per-song BPM / seed / personality. Density is restrained and readable.
A HOLD with multiple visual frames is ONE gameplay note.
"""

from __future__ import annotations

import random
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple

AUDIO_OFFSET_MS = 0
PRE_ROLL_SECONDS = 1.5
FINAL_NOTE_LEAD_SECONDS = 2.5
FINISH_DELAY_SECONDS = 0.65
COLS = 4
TRAVEL_TIME = 3.8
RECOVERY_COOLDOWN_BEATS = 8
MAX_CHART_GENERATION_ITERATIONS = 100000

SONG_CATALOG: List[dict] = [
    {
        "id": "monkeys",
        "menu_number": 1,
        "title": "Monkeys Spinning Monkeys",
        "composer": "Kevin MacLeod",
        "file": "assets/audio/monkeys-spinning-monkeys.mp3",
        "bpm": 144,
        "fallback_duration": 125.0,
        "seed": 14401,
        "approx_label": "2:05",
        "source": "https://incompetech.com/music/royalty-free/index.html?Search=Search&isrc=USUAN1400011",
        "personality": "monkeys",
    },
    {
        "id": "duck",
        "menu_number": 2,
        "title": "Fluffing a Duck",
        "composer": "Kevin MacLeod",
        "file": "assets/audio/fluffing-a-duck.mp3",
        "bpm": 122,
        "fallback_duration": 67.0,
        "seed": 12202,
        "approx_label": "1:07",
        "source": "https://incompetech.com/music/royalty-free/index.html?Search=Search&isrc=USUAN1100768",
        "personality": "duck",
    },
    {
        "id": "snitch",
        "menu_number": 3,
        "title": "Sneaky Snitch",
        "composer": "Kevin MacLeod",
        "file": "assets/audio/sneaky-snitch.mp3",
        "bpm": 87,
        "fallback_duration": 137.0,
        "seed": 8703,
        "approx_label": "2:17",
        "source": "https://incompetech.com/music/royalty-free/index.html?Search=Search&isrc=USUAN1100772",
        "personality": "snitch",
    },
]

# Density / spacing (beats). Max gaps are soft rests — not hard-fill targets.
DIFFICULTY_PARAMS = {
    "Easy": {
        "group_spacing": (2.0, 3.0),
        "min_spacing": 1.25,
        "max_gap": 4.0,
        "hold_chance": 0.065,
        "hold_beats_choices": (2, 3),
        "chord_chance": 0.08,
        "simultaneous_max": 2,
        "active_short_cap": 3,
        "active_hold_cap": 1,
        "active_total_cap": 4,
        "npm_warn": 55,
    },
    "Normal": {
        "group_spacing": (1.25, 2.0),
        "min_spacing": 0.75,
        "max_gap": 3.0,
        "hold_chance": 0.10,
        "hold_beats_choices": (2, 3, 4),
        "chord_chance": 0.18,
        "simultaneous_max": 2,
        "active_short_cap": 5,
        "active_hold_cap": 1,
        "active_total_cap": 6,
        "npm_warn": 80,
    },
    "Hard": {
        "group_spacing": (0.75, 1.5),
        "min_spacing": 0.5,
        "max_gap": 2.5,
        "hold_chance": 0.125,
        "hold_beats_choices": (2, 3, 4),
        "chord_chance": 0.28,
        "simultaneous_max": 2,
        "active_short_cap": 7,
        "active_hold_cap": 1,
        "active_total_cap": 8,
        "npm_warn": 110,
    },
}


def get_song(song_id: str) -> dict:
    for song in SONG_CATALOG:
        if song["id"] == song_id:
            return song
    raise KeyError(song_id)


def seconds_per_beat(bpm: float) -> float:
    return 60.0 / float(bpm)


def beat_to_time(beat: float, bpm: float) -> float:
    return beat * seconds_per_beat(bpm)


def time_to_beat(t: float, bpm: float) -> float:
    return t / seconds_per_beat(bpm)


def active_caps(difficulty: str) -> Tuple[int, int, int]:
    p = DIFFICULTY_PARAMS[difficulty]
    return p["active_short_cap"], p["active_hold_cap"], p["active_total_cap"]


def _patterns_for(personality: str, rng: random.Random, difficulty: str) -> List[List[Tuple[float, List[int], bool, float]]]:
    """Pattern blocks: (beat_offset, lanes, is_hold, hold_beats). Sparse by design."""
    hold_beats = float(rng.choice(DIFFICULTY_PARAMS[difficulty]["hold_beats_choices"]))

    if personality == "monkeys":
        return [
            # alternating singles
            [(0.0, [0], False, 0.0), (2.0, [1], False, 0.0), (4.0, [2], False, 0.0)],
            [(0.0, [3], False, 0.0), (2.0, [2], False, 0.0), (4.0, [1], False, 0.0)],
            # left-right exchange
            [(0.0, [0], False, 0.0), (2.0, [3], False, 0.0), (4.0, [1], False, 0.0)],
            [(0.0, [1], False, 0.0), (2.5, [2], False, 0.0)],
            # occasional sweep (spaced)
            [(0.0, [0], False, 0.0), (1.5, [1], False, 0.0), (3.0, [2], False, 0.0), (4.5, [3], False, 0.0)],
            # rest-friendly pair
            [(0.0, [0, 2], False, 0.0)] if difficulty != "Easy" else [(0.0, [1], False, 0.0)],
            # sparse HOLD
            [(0.0, [rng.randint(0, 3)], True, hold_beats)],
            [(0.0, [2], False, 0.0), (3.0, [0], False, 0.0)],
        ]
    if personality == "duck":
        return [
            [(0.0, [0], False, 0.0), (2.5, [1], False, 0.0)],
            [(0.0, [2], False, 0.0), (3.0, [3], False, 0.0)],
            [(0.0, [1], False, 0.0), (2.0, [2], False, 0.0), (4.0, [1], False, 0.0)],
            # small staircase
            [(0.0, [0], False, 0.0), (2.0, [1], False, 0.0), (4.0, [2], False, 0.0)],
            [(0.0, [3], False, 0.0), (2.5, [2], False, 0.0)],
            # short pair
            [(0.0, [0], False, 0.0), (1.5, [3], False, 0.0)],
            # rare HOLD
            [(0.0, [rng.choice([1, 2])], True, min(hold_beats, 3.0))],
            [(0.0, [1], False, 0.0)],
        ]
    # snitch — slower, deliberate, off-beat feel on half-grid
    return [
        [(0.0, [0], False, 0.0), (2.5, [2], False, 0.0)],
        [(0.5, [1], False, 0.0), (3.0, [3], False, 0.0)],
        [(0.0, [3], False, 0.0), (3.5, [0], False, 0.0)],
        [(1.0, [2], False, 0.0), (3.5, [1], False, 0.0)],
        [(0.0, [1], False, 0.0)],
        [(0.5, [0], False, 0.0), (2.5, [3], False, 0.0), (5.0, [2], False, 0.0)],
        # longer HOLD occasionally
        [(0.0, [rng.randint(0, 3)], True, max(hold_beats, 3.0))],
        [(0.0, [2], False, 0.0), (4.0, [1], False, 0.0)],
    ]


def _lane_ok(
    col: int,
    hit: float,
    hold_dur: float,
    col_busy: List[float],
    hold_spans: List[Tuple[float, float, int]],
) -> bool:
    if hit < col_busy[col] - 1e-6:
        return False
    end = hit + max(hold_dur, 0.0)
    if hold_dur > 0:
        # Never overlap any existing HOLD
        for hs, he, _hc in hold_spans:
            if not (end <= hs + 1e-4 or hit >= he - 1e-4):
                return False
    else:
        # No short note in a lane during that lane's HOLD
        for hs, he, hc in hold_spans:
            if hc == col and hs - 1e-4 <= hit <= he + 1e-4:
                return False
    return True


def _estimate_active_at(
    events: List[dict],
    t: float,
) -> Tuple[int, int, int]:
    """Count notes that would be on-screen at time t (spawned, not past end)."""
    short_n = 0
    hold_n = 0
    for e in events:
        spawn = e["hit_time"] - TRAVEL_TIME
        end = e["hit_time"] + e["hold_duration"] + 0.15
        if spawn <= t <= end:
            if e["is_long"]:
                hold_n += 1
            else:
                short_n += 1
    return short_n, hold_n, short_n + hold_n


def fallback_chart(song: dict, difficulty: str, duration_sec: float) -> List[dict]:
    """Minimal safe chart — used when generation fails or exceeds iteration limits."""
    bpm = float(song["bpm"])
    spb = seconds_per_beat(bpm)
    end_time = max(PRE_ROLL_SECONDS + 3.0, float(duration_sec) - FINAL_NOTE_LEAD_SECONDS)
    spacing = DIFFICULTY_PARAMS.get(difficulty, DIFFICULTY_PARAMS["Easy"])["min_spacing"]
    events: List[dict] = []
    t = PRE_ROLL_SECONDS + 0.5
    col = 0
    guard = 0
    while t <= end_time and guard < 5000:
        guard += 1
        events.append(
            {
                "hit_time": t,
                "energy": 0.6,
                "is_long": False,
                "hold_duration": 0.0,
                "col": col,
                "priority": 3,
                "is_recovery": False,
            }
        )
        col = (col + 1) % COLS
        t += spb * max(1.0, spacing)
    return events


def generate_chart(
    song: dict,
    difficulty: str,
    duration_sec: Optional[float] = None,
    seed: Optional[int] = None,
) -> List[dict]:
    if difficulty not in DIFFICULTY_PARAMS:
        raise ValueError(difficulty)

    bpm = float(song["bpm"])
    spb = seconds_per_beat(bpm)
    duration = float(duration_sec if duration_sec is not None else song["fallback_duration"])
    params = DIFFICULTY_PARAMS[difficulty]
    chart_seed = int(seed if seed is not None else song["seed"])
    chart_seed += {"Easy": 0, "Normal": 100, "Hard": 200}[difficulty]
    rng = random.Random(chart_seed)

    end_time = max(PRE_ROLL_SECONDS + 3.0, duration - FINAL_NOTE_LEAD_SECONDS)
    patterns = _patterns_for(song["personality"], rng, difficulty)

    hold_chance = params["hold_chance"]
    chord_chance = params["chord_chance"]
    if song["personality"] == "duck":
        hold_chance *= 0.55
        chord_chance *= 0.7
    elif song["personality"] == "snitch":
        chord_chance *= 0.45
        hold_chance *= 1.1

    events: List[dict] = []
    col_busy = [0.0] * COLS
    hold_spans: List[Tuple[float, float, int]] = []
    group_beats: List[float] = []
    last_any_hit = -999.0

    short_cap, hold_cap, total_cap = active_caps(difficulty)
    # Spacing must keep on-screen count under caps given TRAVEL_TIME
    travel_safe_beats = (TRAVEL_TIME / max(1, total_cap)) / spb * 0.92
    min_sp = max(params["min_spacing"], travel_safe_beats)
    # Prefer slightly roomier pacing than the absolute floor
    spacing_lo, spacing_hi = params["group_spacing"]
    spacing_lo = max(spacing_lo, min_sp)
    spacing_hi = max(spacing_hi, spacing_lo + 0.25)

    cursor_beat = time_to_beat(PRE_ROLL_SECONDS + 0.4, bpm)
    cursor_beat = round(cursor_beat * 2) / 2.0
    safety = 0

    while beat_to_time(cursor_beat, bpm) < end_time and safety < MAX_CHART_GENERATION_ITERATIONS:
        safety += 1
        prev_cursor = cursor_beat

        if song["personality"] == "duck" and rng.random() < 0.22:
            cursor_beat += rng.uniform(1.0, 2.0)
        elif song["personality"] == "snitch" and rng.random() < 0.18:
            cursor_beat += rng.uniform(1.0, 2.5)
        elif song["personality"] == "monkeys" and rng.random() < 0.12:
            cursor_beat += rng.uniform(0.75, 1.5)

        block = rng.choice(patterns)
        if any(p[2] for p in block) and rng.random() > hold_chance * 3.5:
            block = [(0.0, [rng.randint(0, 3)], False, 0.0)]
        # Easy: flatten multi-note blocks often
        if difficulty == "Easy" and len(block) > 1 and rng.random() < 0.55:
            block = [block[0]]

        lane_shift = rng.randint(0, COLS - 1) if rng.random() < 0.3 else 0
        block_base = cursor_beat
        last_beat = block_base
        placed_any = False

        for beat_off, lanes, is_hold, hold_beats in block:
            abs_beat = block_base + beat_off
            # Enforce min spacing vs previous group
            if group_beats and (abs_beat - group_beats[-1]) < min_sp - 1e-6:
                abs_beat = group_beats[-1] + min_sp
            hit = beat_to_time(abs_beat, bpm)
            if hit > end_time:
                break
            if hit - last_any_hit < spb * min_sp - 1e-4 and last_any_hit > 0:
                abs_beat = time_to_beat(last_any_hit, bpm) + min_sp
                hit = beat_to_time(abs_beat, bpm)
                if hit > end_time:
                    break

            hold_dur = beat_to_time(hold_beats, bpm) if is_hold else 0.0
            if is_hold and hit + hold_dur > end_time:
                is_hold = False
                hold_dur = 0.0

            # Only one HOLD may be on-screen (spawn→end)
            if is_hold:
                hold_blocked = False
                for hs, he, _hc in hold_spans:
                    # visible window for existing hold
                    vis0 = hs - TRAVEL_TIME
                    vis1 = he + 0.2
                    new0 = hit - TRAVEL_TIME
                    new1 = hit + hold_dur + 0.2
                    if not (new1 <= vis0 or new0 >= vis1):
                        hold_blocked = True
                        break
                if hold_blocked:
                    is_hold = False
                    hold_dur = 0.0

            peek_t = hit
            s_n, h_n, t_n = _estimate_active_at(events, peek_t)
            # Also check mid-travel samples
            for extra in (hit - TRAVEL_TIME * 0.5, hit - 1.0, hit + 0.5):
                if extra > 0:
                    s2, h2, t2 = _estimate_active_at(events, extra)
                    s_n, h_n, t_n = max(s_n, s2), max(h_n, h2), max(t_n, t2)

            if is_hold and h_n >= hold_cap:
                is_hold = False
                hold_dur = 0.0
            if t_n >= total_cap or s_n >= short_cap:
                cursor_beat = abs_beat + min_sp
                break

            chosen: List[int] = []
            want_lanes = list(lanes)
            if len(want_lanes) > 1 and rng.random() > chord_chance:
                want_lanes = [want_lanes[0]]
            if difficulty == "Easy" and len(want_lanes) > 1:
                want_lanes = [want_lanes[0]]
            if len(want_lanes) >= 3 and (difficulty != "Hard" or rng.random() < 0.95):
                want_lanes = want_lanes[:1]

            for raw in want_lanes:
                col = (int(raw) + lane_shift) % COLS
                if col in chosen:
                    continue
                trial_hold = hold_dur if (is_hold and not chosen) else 0.0
                if not _lane_ok(col, hit, trial_hold, col_busy, hold_spans):
                    free = [
                        c
                        for c in range(COLS)
                        if c not in chosen and _lane_ok(c, hit, 0.0, col_busy, hold_spans)
                    ]
                    if not free:
                        continue
                    col = rng.choice(free)
                if len(chosen) >= params["simultaneous_max"]:
                    break
                if s_n + len(chosen) + 1 > short_cap:
                    break
                if t_n + len(chosen) + 1 > total_cap:
                    break
                chosen.append(col)

            if not chosen:
                continue

            hold_col = chosen[0] if is_hold else None
            for col in chosen:
                this_hold = is_hold and col == hold_col
                hd = hold_dur if this_hold else 0.0
                if not this_hold:
                    blocked = False
                    for hs, he, hc in hold_spans:
                        if hc == col and hs - 1e-4 <= hit <= he + 1e-4:
                            blocked = True
                            break
                    if blocked:
                        continue
                events.append(
                    {
                        "hit_time": hit,
                        "energy": rng.uniform(0.4, 0.95),
                        "is_long": this_hold,
                        "hold_duration": hd,
                        "col": col,
                        "priority": 2 if this_hold else 3,
                        "is_recovery": False,
                    }
                )
                gap = spb * max(0.75, min_sp * 0.5)
                col_busy[col] = hit + hd + gap
                if this_hold:
                    hold_spans.append((hit, hit + hd, col))
                placed_any = True
                last_any_hit = hit

            if placed_any:
                group_beats.append(abs_beat)
                last_beat = abs_beat

        spacing = rng.uniform(spacing_lo, spacing_hi)
        next_beat = max(last_beat + spacing, block_base + spacing)
        if next_beat <= cursor_beat:
            next_beat = cursor_beat + min_sp
        cursor_beat = next_beat
        # Guaranteed forward progress every outer iteration
        if cursor_beat <= prev_cursor + 1e-9:
            cursor_beat = prev_cursor + min_sp

    if safety >= MAX_CHART_GENERATION_ITERATIONS:
        raise RuntimeError(
            f"chart generation iteration limit at beat={cursor_beat:.3f} "
            f"time={beat_to_time(cursor_beat, bpm):.3f}"
        )

    events.sort(key=lambda e: (e["hit_time"], e["col"]))
    events = _dedupe(events)
    events = _soft_gap_fill(events, song, difficulty, end_time, bpm, chart_seed + 9, min_sp)
    events = _dedupe(events)
    events = _enforce_active_caps(events, difficulty)
    events.sort(key=lambda e: (e["hit_time"], e["col"]))
    return events


def _dedupe(events: List[dict]) -> List[dict]:
    seen = set()
    out = []
    for e in sorted(events, key=lambda x: (x["hit_time"], x["col"], not x["is_long"])):
        key = (round(e["hit_time"], 4), e["col"])
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out


def _enforce_active_caps(events: List[dict], difficulty: str) -> List[dict]:
    """Drop lowest-priority notes that would breach on-screen caps."""
    short_cap, hold_cap, total_cap = active_caps(difficulty)
    # Process in time order; prefer keeping earlier notes
    ordered = sorted(events, key=lambda x: (x["hit_time"], x.get("priority", 3), x["col"]))
    kept: List[dict] = []
    for e in ordered:
        trial = kept + [e]
        t0 = e["hit_time"] - TRAVEL_TIME
        t1 = e["hit_time"] + e["hold_duration"] + 0.2
        ok = True
        t = max(0.0, t0)
        while t <= t1 + 1e-6:
            s, h, tot = _estimate_active_at(trial, t)
            if tot > total_cap or s > short_cap or h > hold_cap:
                ok = False
                break
            t += 0.08
        if ok:
            kept.append(e)
    return kept


def _soft_gap_fill(
    events: List[dict],
    song: dict,
    difficulty: str,
    end_time: float,
    bpm: float,
    seed: int,
    min_sp: float,
) -> List[dict]:
    """Only fill gaps larger than max_gap — single short notes, never chords/HOLDs."""
    rng = random.Random(seed)
    params = DIFFICULTY_PARAMS[difficulty]
    max_gap = params["max_gap"]
    if not events:
        t = PRE_ROLL_SECONDS + 0.5
        col = 0
        guard = 0
        while t <= end_time and guard < 5000:
            guard += 1
            events.append(
                {
                    "hit_time": t,
                    "energy": 0.6,
                    "is_long": False,
                    "hold_duration": 0.0,
                    "col": col,
                    "priority": 3,
                    "is_recovery": False,
                }
            )
            col = (col + 1) % COLS
            t += beat_to_time(max(min_sp, rng.uniform(*params["group_spacing"])), bpm)
        return events

    filled = list(events)
    groups = sorted({round(time_to_beat(e["hit_time"], bpm), 4) for e in filled})
    i = 0
    guard = 0
    while i < len(groups) - 1 and guard < MAX_CHART_GENERATION_ITERATIONS:
        guard += 1
        a, b = groups[i], groups[i + 1]
        if b - a > max_gap + 1e-6:
            insert_beat = a + max(min_sp, max_gap * 0.9)
            if insert_beat >= b - 0.1:
                i += 1
                continue
            hit = beat_to_time(insert_beat, bpm)
            if hit >= end_time:
                break
            prev_len = len(groups)
            filled.append(
                {
                    "hit_time": hit,
                    "energy": 0.55,
                    "is_long": False,
                    "hold_duration": 0.0,
                    "col": rng.randint(0, COLS - 1),
                    "priority": 4,
                    "is_recovery": False,
                }
            )
            groups = sorted({round(time_to_beat(e["hit_time"], bpm), 4) for e in filled})
            # Must advance if insert did not change the group list (rounding / no progress)
            if len(groups) <= prev_len:
                i += 1
            continue
        i += 1

    last = max(e["hit_time"] for e in filled)
    if end_time - last > beat_to_time(max_gap, bpm):
        filled.append(
            {
                "hit_time": end_time,
                "energy": 0.5,
                "is_long": False,
                "hold_duration": 0.0,
                "col": rng.randint(0, COLS - 1),
                "priority": 3,
                "is_recovery": False,
            }
        )
    return filled


def recovery_pattern(at_beat: float, bpm: float, seed: int = 0) -> List[dict]:
    """One short note or a two-note alternating pair. Never HOLD / sweep / chord."""
    rng = random.Random(seed + int(at_beat * 10))
    beat = round(at_beat * 2) / 2.0
    hit = beat_to_time(beat, bpm)
    col = rng.randint(0, COLS - 1)
    events = [
        {
            "hit_time": hit,
            "energy": 0.55,
            "is_long": False,
            "hold_duration": 0.0,
            "col": col,
            "priority": 4,
            "is_recovery": True,
        }
    ]
    if rng.random() < 0.45:
        events.append(
            {
                "hit_time": beat_to_time(beat + 1.0, bpm),
                "energy": 0.55,
                "is_long": False,
                "hold_duration": 0.0,
                "col": (col + 1) % COLS,
                "priority": 4,
                "is_recovery": True,
            }
        )
    return events


def validate_chart_data(
    events: List[dict],
    song: dict,
    difficulty: str,
    duration_sec: float,
) -> Dict:
    bpm = float(song["bpm"])
    params = DIFFICULTY_PARAMS[difficulty]
    short_n = sum(1 for e in events if not e["is_long"])
    hold_n = sum(1 for e in events if e["is_long"])
    times = [e["hit_time"] for e in events]
    first_t = min(times) if times else None
    last_t = max(times) if times else None

    group_beats = sorted({round(time_to_beat(t, bpm), 4) for t in times})
    min_spacing = None
    max_gap = 0.0
    backward = 0
    for i in range(1, len(group_beats)):
        gap = group_beats[i] - group_beats[i - 1]
        if gap < -1e-6:
            backward += 1
        max_gap = max(max_gap, gap)
        if min_spacing is None or gap < min_spacing:
            min_spacing = gap

    # Max simultaneous at any sample (active on screen)
    max_short = max_hold = max_total = 0
    if times:
        sample_end = max(times) + 1.0
        t = 0.0
        while t <= sample_end:
            s, h, tot = _estimate_active_at(events, t)
            max_short = max(max_short, s)
            max_hold = max(max_hold, h)
            max_total = max(max_total, tot)
            t += 0.1

    # HOLD overlaps + same-lane conflicts
    hold_overlap = 0
    same_lane_conflict = 0
    holds = [(e["hit_time"], e["hit_time"] + e["hold_duration"], e["col"]) for e in events if e["is_long"]]
    for i, (a0, a1, ac) in enumerate(holds):
        for j, (b0, b1, bc) in enumerate(holds):
            if j <= i:
                continue
            if not (a1 <= b0 + 1e-4 or b1 <= a0 + 1e-4):
                hold_overlap += 1
    for e in events:
        if e["is_long"]:
            continue
        for h0, h1, hc in holds:
            if e["col"] == hc and h0 - 1e-4 <= e["hit_time"] <= h1 + 1e-4:
                same_lane_conflict += 1

    recovery_n = sum(1 for e in events if e.get("is_recovery"))
    recovery_beats = [time_to_beat(e["hit_time"], bpm) for e in events if e.get("is_recovery")]
    recovery_dense = 0
    for i, b in enumerate(sorted(recovery_beats)):
        window = sum(1 for x in recovery_beats if abs(x - b) <= 16)
        # count patterns roughly: pair counts as 2 events
        recovery_dense = max(recovery_dense, window)

    chart_dur = (last_t - first_t) if first_t is not None and last_t is not None else 0.0
    npm = (len(events) / chart_dur * 60.0) if chart_dur > 1 else 0.0

    short_cap, hold_cap, total_cap = active_caps(difficulty)
    failures = []
    warnings = []
    if not events:
        failures.append("no_notes")
    if max_total > total_cap:
        failures.append(f"active_cap {max_total}>{total_cap}")
    if max_hold > hold_cap:
        failures.append(f"hold_cap {max_hold}>{hold_cap}")
    if hold_overlap:
        failures.append(f"hold_overlaps={hold_overlap}")
    if same_lane_conflict:
        failures.append(f"same_lane_hold_conflicts={same_lane_conflict}")
    if backward:
        failures.append(f"backward={backward}")
    if recovery_n > 12:
        failures.append(f"excessive_recovery={recovery_n}")
    if recovery_dense > 4:  # >2 patterns (~2 notes each) in 16 beats
        failures.append(f"recovery_burst={recovery_dense}")
    if min_spacing is not None and min_spacing + 1e-3 < params["min_spacing"] * 0.85:
        warnings.append(f"min_spacing_low={min_spacing:.3f}")
    if npm > params["npm_warn"]:
        warnings.append(f"npm={npm:.1f}>{params['npm_warn']}")

    return {
        "song": song["title"],
        "song_id": song["id"],
        "bpm": bpm,
        "duration": duration_sec,
        "difficulty": difficulty,
        "short_notes": short_n,
        "hold_notes": hold_n,
        "total_notes": len(events),
        "note_groups": len(group_beats),
        "max_simultaneous_active": max_total,
        "max_visible_short": max_short,
        "max_visible_hold": max_hold,
        "min_spacing_beats": min_spacing,
        "max_gap_beats": max_gap,
        "overlapping_holds": hold_overlap,
        "same_lane_hold_conflicts": same_lane_conflict,
        "recovery_notes": recovery_n,
        "notes_per_minute": round(npm, 1),
        "first_note_time": first_t,
        "last_note_time": last_t,
        "ok": len(failures) == 0,
        "failures": failures,
        "warnings": warnings,
    }
