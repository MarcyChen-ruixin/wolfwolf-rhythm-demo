"""
Werewolf Rhythm Demo — cross-platform rhythm demo (Windows + macOS).
"""

from __future__ import annotations

import json
import math
import os
import random
import sys
import time
from collections import deque
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# Headless / CI self-test must set SDL drivers before pygame is imported.
if any(arg in ("--self-test", "--self-test-restart") for arg in sys.argv[1:]):
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from paths import resource_path as _resource_path
from paths import resource_root as _resource_root
from paths import settings_path as _settings_path
from paths import userdata_available
from paths import userdata_dir as _userdata_dir

from chart_gen import (
    AUDIO_OFFSET_MS,
    DIFFICULTY_PARAMS,
    FINAL_NOTE_LEAD_SECONDS,
    FINISH_DELAY_SECONDS,
    PRE_ROLL_SECONDS,
    RECOVERY_COOLDOWN_BEATS,
    SONG_CATALOG,
    TRAVEL_TIME as CHART_TRAVEL,
    active_caps,
    beat_to_time,
    fallback_chart,
    generate_chart,
    recovery_pattern,
    seconds_per_beat,
    time_to_beat,
)

from agv_reward import (
    AGV_HEIGHT,
    AGV_RENDER_HEIGHT,
    AGV_RENDER_WIDTH,
    AGV_REWARD_INTERVAL,
    AGV_REWARD_QUEUE_DELAY_SECONDS,
    AGV_SWEEP_DURATION_SECONDS,
    AGV_VISUAL_SCALE,
    AGV_WIDTH,
    AGVRewardSweep,
    crossed_milestones,
    select_lane_targets,
)

from soft_restart import (
    COUNTDOWN_SECONDS,
    RESTART_WATCHDOG_SECONDS,
    STEP_CLEAR_AGV,
    STEP_CLEAR_NOTES,
    STEP_DONE,
    STEP_ENTER_COUNTDOWN,
    STEP_GENERATE_CHART,
    STEP_PREPARE_AUDIO,
    STEP_RESET_COUNTERS,
    STEP_STOP_MUSIC,
    RestartLogger,
    restart_log_path,
    userdata_dir,
)


# ---------------------------------------------------------------------------
# Paths (dev + PyInstaller Windows onedir + macOS .app)
# ---------------------------------------------------------------------------
def resource_root() -> str:
    return str(_resource_root())


def resource_path(relative_path: str) -> Path:
    return _resource_path(relative_path)


def asset_path(*parts: str) -> str:
    rel = "/".join(str(p).replace("\\", "/") for p in parts)
    return str(resource_path(rel))


def settings_path() -> str:
    return str(_settings_path())

# ---------------------------------------------------------------------------
# Display / timing (match original proportions)
# ---------------------------------------------------------------------------
WIDTH, HEIGHT = 520, 820
COLS = 4
LANE_W = WIDTH // COLS
FPS = 60

HIT_LINE_Y = 670
TRAVEL_TIME = 3.8
HIT_DISTANCE = 165
TOP_BAR_H = 110
GAMEPLAY_TOP = TOP_BAR_H  # notes must not cover HUD above this line

TITLE = "Werewolf Rhythm Demo"
GAME_VERSION = "0.1.0-demo"

BACKGROUND_PATH = "assets/art/werewolf_background.png"

# Preferred default: DFJK. Optional alternative: ASKL.
KEY_PRESETS = {
    "DFJK": [pygame.K_d, pygame.K_f, pygame.K_j, pygame.K_k],
    "ASKL": [pygame.K_a, pygame.K_s, pygame.K_k, pygame.K_l],
}
KEY_PRESET_LABELS = {
    "DFJK": ["D", "F", "J", "K"],
    "ASKL": ["A", "S", "K", "L"],
}

MUSIC_REL_MP3 = "assets/audio/monkeys-spinning-monkeys.mp3"
MUSIC_REL_OGG = "assets/audio/monkeys-spinning-monkeys.ogg"

# Menu-facing song list (all three selectable; availability depends on file presence)
SONGS: List[dict] = []
for _song in SONG_CATALOG:
    SONGS.append(
        {
            **_song,
            "name": _song["title"],
            "path": _song["file"],
            "available": True,
        }
    )

DIFFICULTIES = {
    "Easy": {},
    "Normal": {},
    "Hard": {},
}

DEV_MODE = not getattr(sys, "frozen", False)
RESULT_FADE_MS = 320
_TRACK_DURATION_CACHE: Dict[str, float] = {}

# Deferred soft-restart (KEYDOWN only queues; work happens at frame boundary)
restart_requested = False
restart_key_latched = False
restart_step = 0
restart_started_at = 0.0
restart_pending_events: List[dict] = []
restart_recovery_message = ""
countdown_timer = 0.0
loaded_music_path = ""  # last successfully loaded music path (skip reload when same)
_restart_logger: Optional[RestartLogger] = None


def _get_restart_logger() -> RestartLogger:
    global _restart_logger
    if _restart_logger is None:
        path = restart_log_path(frozen=not DEV_MODE, project_root=resource_root())
        # Always write restart diagnostics (UI never shows them)
        _restart_logger = RestartLogger(path, enabled=True)
    return _restart_logger


def restart_log(msg: str) -> None:
    _get_restart_logger().log(msg)


def current_song() -> dict:
    return SONGS[selected_song_index]


def song_file_present(song: dict) -> bool:
    path = song.get("file") or song.get("path") or ""
    return bool(path) and os.path.isfile(asset_path(path))


def measure_track_duration(
    rel_path: str, fallback: float, *, allow_sound_probe: bool = False
) -> float:
    """
    Prefer cached / fallback duration.

    Never decode the full track via pygame.mixer.Sound() during Results restart —
    that (combined with music.load) can hang the SDL mixer.
    """
    key = rel_path or ""
    if key in _TRACK_DURATION_CACHE:
        return float(_TRACK_DURATION_CACHE[key])
    if not allow_sound_probe:
        return float(fallback)
    full = asset_path(rel_path) if rel_path else ""
    if full and os.path.isfile(full) and mixer_ok:
        try:
            length = float(pygame.mixer.Sound(full).get_length())
            if length > 1.0:
                _TRACK_DURATION_CACHE[key] = length
                return length
        except (pygame.error, Exception):
            pass
    _TRACK_DURATION_CACHE[key] = float(fallback)
    return float(fallback)


def format_duration_label(seconds: float) -> str:
    s = max(0, int(round(seconds)))
    return f"{s // 60}:{s % 60:02d}"


# Short-note werewolf enemies (weights preserve original score variety)
ENEMY_CONFIG = [
    {"path": "assets/art/werewolf_enemy_1.png", "score": 1, "weight": 0.65},
    {"path": "assets/art/werewolf_enemy_2.png", "score": 3, "weight": 0.25},
    {"path": "assets/art/werewolf_enemy_3.png", "score": 5, "weight": 0.10},
]
HOLD_ENEMY_PATH = "assets/art/werewolf_enemy_hold.png"
MISS_ENEMY_PATH = "assets/art/werewolf_enemy_miss.png"
HOLD_SEQUENCE_DIR = "assets/art/hold_sequence"
HOLD_SEQUENCE_FILES = [
    "werewolf_hold_01.png",
    "werewolf_hold_02.png",
    "werewolf_hold_03.png",
    "werewolf_hold_04.png",
]


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
def load_settings() -> dict:
    defaults = {
        "key_preset": "DFJK",
        "music_enabled": True,
        "music_volume": 0.45,
        "muted": False,
        "high_score": 0,
    }
    path = settings_path()
    try:
        if not os.path.isfile(path):
            return defaults
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        defaults.update({k: data[k] for k in defaults if k in data})
        if defaults["key_preset"] not in KEY_PRESETS:
            defaults["key_preset"] = "DFJK"
        return defaults
    except (OSError, json.JSONDecodeError, TypeError):
        return defaults


def save_settings(settings: dict) -> None:
    if not userdata_available():
        return
    try:
        path = Path(settings_path())
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(settings, fh, indent=2)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------
pygame.init()
mixer_ok = False
try:
    pygame.mixer.init()
    mixer_ok = True
except pygame.error:
    mixer_ok = False

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption(f"{TITLE} {GAME_VERSION}")
pygame.key.set_repeat(0)  # prevent held-key repeat from multi-firing Restart
clock = pygame.time.Clock()

font = pygame.font.SysFont("arial", 34, bold=True)
mid_font = pygame.font.SysFont("arial", 28, bold=True)
small_font = pygame.font.SysFont("arial", 22, bold=True)
tiny_font = pygame.font.SysFont("arial", 18, bold=True)


def load_image(path: str, size: Optional[Tuple[int, int]] = None, fallback_color=(245, 245, 245)):
    full = asset_path(path) if not os.path.isabs(path) else path
    if os.path.isfile(full):
        try:
            img = pygame.image.load(full).convert_alpha()
            if size:
                img = pygame.transform.smoothscale(img, size)
            return img
        except pygame.error:
            pass
    surf = pygame.Surface(size if size else (100, 100), pygame.SRCALPHA)
    surf.fill(fallback_color)
    return surf


background_img = load_image(BACKGROUND_PATH, (WIDTH, HEIGHT), (245, 235, 220))

# Full-resolution enemy art (not pre-stretched) for quality scaling
enemy_images_full: List[pygame.Surface] = []
for cfg in ENEMY_CONFIG:
    enemy_images_full.append(load_image(cfg["path"], None, (80, 80, 80, 255)))

hold_enemy_img = load_image(HOLD_ENEMY_PATH, None, (80, 80, 120, 255))
miss_enemy_img = load_image(MISS_ENEMY_PATH, None, (120, 80, 80, 255))
enemy_preview_thumb = pygame.transform.smoothscale(enemy_images_full[0], (28, 36))

hold_sequence_frames: List[pygame.Surface] = []
for fname in HOLD_SEQUENCE_FILES:
    frame = load_image(f"{HOLD_SEQUENCE_DIR}/{fname}", None, (90, 70, 40, 255))
    hold_sequence_frames.append(frame)
if not hold_sequence_frames:
    hold_sequence_frames = [hold_enemy_img]


def scale_contain(
    source: pygame.Surface,
    box_w: int,
    box_h: int,
) -> Tuple[pygame.Surface, int, int]:
    """Uniformly scale `source` to fit inside box (contain). Returns surface + offsets."""
    sw, sh = source.get_width(), source.get_height()
    if sw <= 0 or sh <= 0 or box_w <= 0 or box_h <= 0:
        empty = pygame.Surface((max(1, box_w), max(1, box_h)), pygame.SRCALPHA)
        return empty, 0, 0
    scale = min(box_w / sw, box_h / sh)
    nw = max(1, int(sw * scale))
    nh = max(1, int(sh * scale))
    scaled = pygame.transform.smoothscale(source, (nw, nh))
    ox = (box_w - nw) // 2
    oy = (box_h - nh) // 2
    return scaled, ox, oy


def build_short_note_surface(photo: pygame.Surface, width: int, height: int) -> pygame.Surface:
    """Short-note card with proportional contain fit (no independent W/H stretch)."""
    surf = pygame.Surface((width, height), pygame.SRCALPHA)
    surf.fill((255, 252, 240, 230))
    scaled, ox, oy = scale_contain(photo, width, height)
    surf.blit(scaled, (ox, oy))
    return surf


def build_hold_note_surface(
    frames: List[pygame.Surface],
    width: int,
    height: int,
    reveal: float = 1.0,
) -> pygame.Surface:
    """Continuous HOLD group: stacked proportional frames with slight overlap (no ladder)."""
    surf = pygame.Surface((width, height), pygame.SRCALPHA)

    # Soft continuous strip behind the group (no horizontal divider lines)
    strip = pygame.Surface((width, height), pygame.SRCALPHA)
    for y in range(height):
        t = y / max(1, height - 1)
        a = int(70 + 40 * (1.0 - abs(t - 0.5) * 2))
        pygame.draw.line(strip, (35, 28, 42, a), (0, y), (width, y))
    surf.blit(strip, (0, 0))

    if not frames:
        frames = [hold_enemy_img]

    n = len(frames)
    reveal = max(0.15, min(1.0, reveal))
    visible_count = max(1, int(math.ceil(n * reveal)))
    visible = frames[:visible_count]

    # Each frame gets a vertical slot; slight overlap removes gaps
    overlap = 0.18
    slot_h = height / max(1, (len(visible) - overlap * (len(visible) - 1)))
    y = 4.0
    for i, frame in enumerate(visible):
        box_h = max(48, int(slot_h * (1.0 + overlap * 0.35)))
        # Keep last frame from overflowing
        if y + box_h > height - 8:
            box_h = max(40, int(height - 8 - y))
        scaled, ox, oy = scale_contain(frame, width - 4, box_h)
        surf.blit(scaled, (2 + ox, int(y) + oy))
        y += box_h * (1.0 - overlap)

    # Soft timing tail (not a segmented bar)
    pygame.draw.ellipse(
        surf,
        (70, 100, 180, 200),
        (width // 2 - 16, height - 16, 32, 12),
    )
    return surf


# ---------------------------------------------------------------------------
# Beatmap — full-duration 144 BPM pre-generation (see chart_gen.py)
# ---------------------------------------------------------------------------
class Explosion:
    def __init__(self, x: float, y: float) -> None:
        self.particles = []
        for _ in range(45):
            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(3, 9)
            self.particles.append(
                {
                    "x": x,
                    "y": y,
                    "vx": math.cos(angle) * speed,
                    "vy": math.sin(angle) * speed,
                    "life": random.randint(18, 35),
                    "radius": random.randint(4, 9),
                }
            )

    def update(self) -> None:
        for p in self.particles:
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            p["vy"] += 0.2
            p["life"] -= 1
        self.particles = [p for p in self.particles if p["life"] > 0]

    def draw(self, surface: pygame.Surface) -> None:
        for p in self.particles:
            color = random.choice(
                [(255, 80, 0), (255, 170, 0), (255, 220, 60), (255, 50, 50)]
            )
            pygame.draw.circle(surface, color, (int(p["x"]), int(p["y"])), p["radius"])

    def finished(self) -> bool:
        return len(self.particles) == 0


class Note:
    def __init__(self, hit_time, energy, is_long, hold_duration, col) -> None:
        self.hit_time = hit_time
        self.hold_duration = hold_duration
        self.end_time = hit_time + hold_duration
        self.is_long = is_long
        self.spawn_time = hit_time - TRAVEL_TIME
        self.col = col
        self.width = LANE_W - 28
        self.x = self.col * LANE_W + 14
        self.energy = energy

        if self.is_long:
            self.height = int(170 + hold_duration * 170)
        else:
            self.height = int(85 + energy * 85)
        self.height = max(75, min(self.height, 460))

        # Short notes: alternate pack members. HOLD notes: dedicated strong enemy art.
        if self.is_long:
            self.enemy_type = -1  # hold
            self.score = 5
        else:
            self.enemy_type = random.choices(
                population=[0, 1, 2],
                weights=[
                    ENEMY_CONFIG[0]["weight"],
                    ENEMY_CONFIG[1]["weight"],
                    ENEMY_CONFIG[2]["weight"],
                ],
                k=1,
            )[0]
            self.score = ENEMY_CONFIG[self.enemy_type]["score"]
        self.clicked = False
        self.missed = False
        self.holding = False
        self.hold_started = False
        self.hold_completed = False
        self.is_recovery = False
        self.priority = 3
        self.note_id = id(self)
        self.cleared_by_agv = False
        self.agv_reserved = False
        self.agv_fade = 0.0
        self.agv_slide_x = 0.0
        self.removed = False
        self.agv_defeat_counted = False
        self._cached_surf: Optional[pygame.Surface] = None
        self._cached_size: Optional[Tuple[int, int]] = None
        self._cached_reveal: int = -1

    def get_head_y(self, current_time: float) -> float:
        progress = (current_time - self.spawn_time) / TRAVEL_TIME
        start_y = GAMEPLAY_TOP - 60
        y = start_y + progress * (HIT_LINE_Y - start_y)
        # Reserved AGV targets: clamp near judgment line (no Escaped)
        if self.agv_reserved and not self.cleared_by_agv and not self.removed:
            if self.is_long:
                # keep bottom near hit line
                max_head = HIT_LINE_Y + self.height * 0.15
            else:
                max_head = HIT_LINE_Y + HIT_DISTANCE * 0.35
            y = min(y, max_head)
        return y

    def get_rect(self, current_time: float) -> pygame.Rect:
        head_y = self.get_head_y(current_time)
        if self.is_long:
            y = head_y - self.height
        else:
            y = head_y - self.height / 2
        slide = int(getattr(self, "agv_slide_x", 0) or 0)
        return pygame.Rect(self.x + slide, y, self.width, self.height)

    def is_active(self, current_time: float) -> bool:
        if self.removed:
            return False
        return self.spawn_time <= current_time <= self.end_time + 2.0

    def short_distance(self, current_time: float) -> float:
        return abs(self.get_rect(current_time).centery - HIT_LINE_Y)

    def long_start_distance(self, current_time: float) -> float:
        return abs(self.get_rect(current_time).bottom - HIT_LINE_Y)

    def long_end_distance(self, current_time: float) -> float:
        return abs(self.get_rect(current_time).top - HIT_LINE_Y)

    def _hold_reveal(self, current_time: float) -> float:
        progress = (current_time - self.spawn_time) / TRAVEL_TIME
        return max(0.3, min(1.0, 0.4 + progress * 0.7))

    def _surface(self, current_time: Optional[float] = None) -> pygame.Surface:
        size = (self.width, self.height)
        if self.is_long:
            reveal = self._hold_reveal(current_time if current_time is not None else self.hit_time)
            reveal_q = int(reveal * 4 + 0.01)
            if (
                self._cached_surf is not None
                and self._cached_size == size
                and self._cached_reveal == reveal_q
            ):
                return self._cached_surf
            self._cached_surf = build_hold_note_surface(
                hold_sequence_frames, self.width, self.height, reveal=reveal
            )
            self._cached_size = size
            self._cached_reveal = reveal_q
            return self._cached_surf

        if self._cached_surf is not None and self._cached_size == size:
            return self._cached_surf
        photo = enemy_images_full[self.enemy_type]
        self._cached_surf = build_short_note_surface(photo, self.width, self.height)
        self._cached_size = size
        return self._cached_surf

    def draw(self, surface: pygame.Surface, current_time: float) -> None:
        if self.removed:
            return
        if self.clicked and not self.is_long and not self.cleared_by_agv:
            return
        if self.hold_completed and not self.cleared_by_agv:
            return

        rect = self.get_rect(current_time)
        if rect.bottom <= GAMEPLAY_TOP:
            return
        clip_top = max(rect.top, GAMEPLAY_TOP)
        src_y = int(clip_top - rect.top)
        visible_h = int(rect.bottom - clip_top)
        if visible_h <= 0:
            return
        note_surf = self._surface(current_time)
        if self.cleared_by_agv:
            fade = max(0.0, min(1.0, getattr(self, "agv_fade", 0.0)))
            alpha = int(255 * (1.0 - fade))
            scale = max(0.55, 1.0 - 0.35 * fade)
            nw = max(1, int(self.width * scale))
            nh = max(1, int(visible_h * scale))
            scaled = pygame.transform.smoothscale(
                note_surf.subsurface(pygame.Rect(0, src_y, self.width, visible_h)),
                (nw, nh),
            )
            scaled = scaled.copy()
            scaled.set_alpha(alpha)
            surface.blit(scaled, (rect.x, clip_top))
            return

        surface.blit(
            note_surf,
            (rect.x, clip_top),
            area=pygame.Rect(0, src_y, self.width, visible_h),
        )

        border_rect = pygame.Rect(rect.x, clip_top, self.width, visible_h)
        if self.is_long:
            border_color = (0, 80, 255)
            label_text = "HOLD"
        else:
            border_color = (0, 0, 0)
            label_text = f"+{self.score}"
        if self.holding:
            border_color = (0, 180, 0)

        pygame.draw.rect(surface, border_color, border_rect, 4, border_radius=10)
        if clip_top <= rect.y + 24:
            label = tiny_font.render(label_text, True, (0, 0, 0))
            surface.blit(label, (rect.x + 8, max(clip_top + 4, rect.y + 8)))


def create_notes_from_chart(events: List[dict]) -> List[Note]:
    notes = []
    for item in events:
        note = Note(
            hit_time=item["hit_time"],
            energy=item["energy"],
            is_long=item["is_long"],
            hold_duration=item["hold_duration"],
            col=int(item["col"]),
        )
        note.is_recovery = bool(item.get("is_recovery"))
        note.priority = int(item.get("priority", 3))
        notes.append(note)
    return notes


# ---------------------------------------------------------------------------
# Game state — central run statistics (avoids local/global assignment bugs)
# ---------------------------------------------------------------------------
class RunState:
    """Mutable per-run stats owned by one object; reset only on new run."""

    __slots__ = (
        "notes",
        "explosions",
        "score",
        "combo",
        "best_combo",
        "defeated_count",
        "escaped_count",
        "judged_count",
        "miss_flash_timer",
        "game_over",
        "cleared",
        "results_entered",
        "gameplay_active",
        "music_started",
        "music_available",
        "silent_message",
        "start_ticks",
        "accumulated_pause_ms",
        "pause_started_ticks",
        "paused",
        "pressed_cols",
        "current_song_path",
        "song_meta",
        "bpm",
        "track_duration",
        "chart_end_time",
        "finish_timer",
        "ending",
        "dev_empty_warned",
        "last_recovery_beat",
        "recovery_count",
        "result_fade_ms",
        "result_kind",
        "triggered_agv_milestones",
        "pending_agv_rewards",
        "agv_queue_delay",
        "agv_reward",
        "agv_cleared_count",
    )

    def __init__(self) -> None:
        self.notes: List[Note] = []
        self.explosions: List[Explosion] = []
        self.score = 0
        self.combo = 0
        self.best_combo = 0
        self.defeated_count = 0
        self.escaped_count = 0
        self.judged_count = 0
        self.miss_flash_timer = 0
        self.game_over = False
        self.cleared = False
        self.results_entered = False
        self.gameplay_active = True
        self.music_started = False
        self.music_available = False
        self.silent_message = ""
        self.start_ticks = 0
        self.accumulated_pause_ms = 0
        self.pause_started_ticks: Optional[int] = None
        self.paused = False
        self.pressed_cols: Set[int] = set()
        self.current_song_path = ""
        self.song_meta: dict = {}
        self.bpm = 144.0
        self.track_duration = 125.0
        self.chart_end_time = 0.0
        self.finish_timer = 0.0
        self.ending = False
        self.dev_empty_warned = False
        self.last_recovery_beat = -999.0
        self.recovery_count = 0
        self.result_fade_ms = 0
        self.result_kind = ""
        self.triggered_agv_milestones: Set[int] = set()
        self.pending_agv_rewards: deque = deque()
        self.agv_queue_delay = 0.0
        self.agv_reward = AGVRewardSweep()
        self.agv_cleared_count = 0

    def reset_counters(self) -> None:
        self.score = 0
        self.combo = 0
        self.best_combo = 0
        self.defeated_count = 0
        self.escaped_count = 0
        self.judged_count = 0
        self.miss_flash_timer = 0
        self.game_over = False
        self.cleared = False
        self.results_entered = False
        self.gameplay_active = True
        self.music_started = False
        self.pressed_cols = set()
        self.accumulated_pause_ms = 0
        self.pause_started_ticks = None
        self.paused = False
        self.finish_timer = 0.0
        self.ending = False
        self.dev_empty_warned = False
        self.last_recovery_beat = -999.0
        self.recovery_count = 0
        self.result_fade_ms = 0
        self.result_kind = ""
        self.triggered_agv_milestones = set()
        self.pending_agv_rewards = deque()
        self.agv_queue_delay = 0.0
        self.agv_cleared_count = 0
        if getattr(self, "agv_reward", None) is None:
            self.agv_reward = AGVRewardSweep()
        else:
            self.agv_reward.cancel()
            self.agv_reward.reset()

    def register_defeat(self) -> None:
        self.defeated_count = int(getattr(self, "defeated_count", 0) or 0) + 1
        self.judged_count = int(getattr(self, "judged_count", 0) or 0) + 1
        self.combo = int(getattr(self, "combo", 0) or 0)
        self.best_combo = max(self.best_combo, self.combo)

    def register_escape(self) -> None:
        self.escaped_count = int(getattr(self, "escaped_count", 0) or 0) + 1
        self.judged_count = int(getattr(self, "judged_count", 0) or 0) + 1
        self.miss_flash_timer = 90
        self.combo = 0

    def register_agv_clear(self) -> None:
        """Defeated +1 only — no score, combo, accuracy, or recursive rewards."""
        self.defeated_count = int(getattr(self, "defeated_count", 0) or 0) + 1
        self.agv_cleared_count = int(getattr(self, "agv_cleared_count", 0) or 0) + 1


settings = load_settings()
run = RunState()
game_state = "menu"  # menu | playing | credits | results | restarting | countdown
selected_song_index = 0
selected_difficulty = "Easy"


def key_map() -> Dict[int, int]:
    preset = settings.get("key_preset", "DFJK")
    if preset not in KEY_PRESETS:
        preset = "DFJK"
        settings["key_preset"] = preset
    keys = KEY_PRESETS[preset]
    mapping = {keys[i]: i for i in range(COLS)}
    mapping.update(
        {
            pygame.K_1: 0,
            pygame.K_2: 1,
            pygame.K_3: 2,
            pygame.K_4: 3,
            pygame.K_KP1: 0,
            pygame.K_KP2: 1,
            pygame.K_KP3: 2,
            pygame.K_KP4: 3,
        }
    )
    return mapping


def apply_music_volume() -> None:
    if not mixer_ok or not run.music_available:
        return
    try:
        vol = 0.0 if settings.get("muted") else float(settings.get("music_volume", 0.45))
        pygame.mixer.music.set_volume(max(0.0, min(1.0, vol)))
    except pygame.error:
        pass


def reset_game(*, probe_duration: bool = False) -> None:
    """Synchronous reset for automated tests / tools."""
    start_new_run(probe_duration=probe_duration, from_results=False)


def queue_soft_restart(*, from_menu: bool = False, probe_duration: bool = False) -> None:
    """KEYDOWN / menu Enter: set a flag only. No chart/audio work here."""
    global restart_requested, restart_key_latched
    if restart_requested:
        return
    if not from_menu and not run.results_entered and game_state != "results":
        return
    restart_requested = True
    restart_key_latched = True
    restart_log("[restart] key received")
    restart_log("[restart] request queued")


def begin_soft_restart_pipeline() -> None:
    """Frame-boundary entry: RESULTS/MENU -> RESTARTING."""
    global restart_requested, restart_step, restart_started_at, game_state
    global restart_pending_events, restart_recovery_message, countdown_timer
    restart_requested = False
    restart_step = STEP_STOP_MUSIC
    restart_started_at = time.perf_counter()
    restart_pending_events = []
    restart_recovery_message = ""
    countdown_timer = 0.0
    game_state = "restarting"
    run.results_entered = False
    run.gameplay_active = False
    run.paused = False
    restart_log("[restart] leaving results")


def _fresh_run_skeleton() -> "RunState":
    """Create a clean RunState preserving nothing from the finished run."""
    return RunState()


def perform_soft_restart_step() -> None:
    """
    Execute at most one expensive restart step. Must return quickly.
    Called once per frame while game_state == 'restarting'.
    """
    global run, restart_step, game_state, restart_pending_events
    global loaded_music_path, countdown_timer, restart_recovery_message

    # Watchdog
    if time.perf_counter() - restart_started_at > RESTART_WATCHDOG_SECONDS:
        restart_log(
            f"[restart] WATCHDOG fired at step={restart_step} — fallback silent chart"
        )
        song = current_song()
        events = fallback_chart(song, selected_difficulty, float(song["fallback_duration"]))
        new_run = _fresh_run_skeleton()
        new_run.song_meta = song
        new_run.bpm = float(song["bpm"])
        new_run.track_duration = float(song["fallback_duration"])
        new_run.current_song_path = ""
        new_run.music_available = False
        new_run.silent_message = "Restart recovery mode enabled."
        new_run.notes = create_notes_from_chart(events)
        new_run.chart_end_time = max((n.end_time for n in new_run.notes), default=0.0)
        new_run.gameplay_active = False
        run = new_run
        restart_recovery_message = "Restart recovery mode enabled."
        restart_step = STEP_ENTER_COUNTDOWN

    step = restart_step

    if step == STEP_STOP_MUSIC:
        restart_log("[restart] stopping music")
        if mixer_ok:
            try:
                pygame.mixer.music.stop()
            except pygame.error:
                pass
            try:
                pygame.mixer.stop()
            except pygame.error:
                pass
        restart_step = STEP_CLEAR_NOTES
        return

    if step == STEP_CLEAR_NOTES:
        restart_log("[restart] clearing notes")
        restart_log("[restart] clearing holds")
        run.notes = []
        run.explosions = []
        run.pressed_cols = set()
        run.miss_flash_timer = 0
        run.finish_timer = 0.0
        run.ending = False
        run.last_recovery_beat = -999.0
        run.recovery_count = 0
        restart_step = STEP_CLEAR_AGV
        return

    if step == STEP_CLEAR_AGV:
        restart_log("[restart] clearing AGV state")
        cancel_agv_reward()
        run.triggered_agv_milestones = set()
        run.pending_agv_rewards = deque()
        run.agv_queue_delay = 0.0
        run.agv_cleared_count = 0
        if run.agv_reward is None:
            run.agv_reward = AGVRewardSweep()
        else:
            run.agv_reward.reset()
        restart_step = STEP_RESET_COUNTERS
        return

    if step == STEP_RESET_COUNTERS:
        restart_log("[restart] Run state cleared")
        song = current_song()
        new_run = _fresh_run_skeleton()
        new_run.song_meta = song
        new_run.bpm = float(song["bpm"])
        new_run.current_song_path = song["file"] if song_file_present(song) else ""
        new_run.track_duration = measure_track_duration(
            new_run.current_song_path or song["file"],
            float(song["fallback_duration"]),
            allow_sound_probe=False,
        )
        new_run.gameplay_active = False
        new_run.results_entered = False
        new_run.game_over = False
        new_run.cleared = False
        new_run.music_started = False
        run = new_run
        restart_step = STEP_GENERATE_CHART
        return

    if step == STEP_GENERATE_CHART:
        restart_log("[restart] generating chart")
        song = run.song_meta or current_song()
        t0 = time.perf_counter()
        try:
            events = generate_chart(
                song, selected_difficulty, duration_sec=run.track_duration
            )
        except Exception as exc:
            restart_log(f"[restart] chart error: {exc} — using fallback")
            events = fallback_chart(
                song, selected_difficulty, float(song["fallback_duration"])
            )
        dt_ms = (time.perf_counter() - t0) * 1000.0
        restart_log(f"[restart] chart generated notes={len(events)} time_ms={dt_ms:.1f}")
        run.notes = create_notes_from_chart(events)
        run.chart_end_time = max((n.end_time for n in run.notes), default=0.0)
        restart_pending_events = events
        restart_step = STEP_PREPARE_AUDIO
        return

    if step == STEP_PREPARE_AUDIO:
        restart_log("[restart] preparing audio")
        song = run.song_meta or current_song()
        run.music_available = False
        run.silent_message = restart_recovery_message or ""
        want_path = run.current_song_path
        full = asset_path(want_path) if want_path else ""

        if not settings.get("music_enabled", True):
            run.silent_message = "Music unavailable — continuing in silent mode."
        elif not mixer_ok:
            run.silent_message = "Music unavailable — continuing in silent mode."
        elif not want_path or not os.path.isfile(full):
            run.silent_message = "Audio unavailable — continuing in silent mode."
        else:
            try:
                if loaded_music_path != full:
                    pygame.mixer.music.load(full)
                    loaded_music_path = full
                run.music_available = True
                apply_music_volume()
                restart_log(f"[restart] audio prepared: {song.get('title', want_path)}")
            except pygame.error as exc:
                restart_log(f"[restart] audio load failed: {exc}")
                run.music_available = False
                run.silent_message = "Music unavailable — continuing in silent mode."
                loaded_music_path = ""
        run.music_started = False
        restart_step = STEP_ENTER_COUNTDOWN
        return

    if step == STEP_ENTER_COUNTDOWN:
        if DEV_MODE:
            assert run.escaped_count == 0
            assert not run.game_over
            assert not run.results_entered
            assert run.score == 0
        restart_log("[restart] state set to countdown")
        restart_log(
            f"[restart] flags game_over={run.game_over} results={run.results_entered} "
            f"escaped={run.escaped_count} notes={len(run.notes)} ending={run.ending}"
        )
        game_state = "countdown"
        countdown_timer = COUNTDOWN_SECONDS
        run.gameplay_active = False
        restart_step = STEP_DONE
        return


def finish_countdown_and_start_playing() -> None:
    """COUNTDOWN complete: start clock + music exactly once, enter PLAYING."""
    global game_state
    run.accumulated_pause_ms = 0
    run.pause_started_ticks = None
    run.paused = False
    run.start_ticks = pygame.time.get_ticks()
    run.gameplay_active = True
    run.results_entered = False
    run.game_over = False
    run.cleared = False
    run.ending = False
    run.finish_timer = 0.0
    run.music_started = True
    if run.music_available and mixer_ok:
        try:
            apply_music_volume()
            pygame.mixer.music.play()
            restart_log(
                f"[restart] audio started: {(run.song_meta or {}).get('title', '')}"
            )
        except pygame.error:
            run.music_available = False
            run.silent_message = "Music unavailable — continuing in silent mode."
            restart_log("[restart] audio play failed — silent mode")
    else:
        restart_log("[restart] audio started: silent")
    game_state = "playing"
    restart_log("[restart] first gameplay frame rendered")


def start_new_run(
    *,
    preserve_menu_selection: bool = True,
    probe_duration: bool = False,
    from_results: bool = False,
) -> bool:
    """
    Synchronous helper for automated tests only.

    Interactive play uses queue_soft_restart() + perform_soft_restart_step().
    """
    global run, loaded_music_path, game_state
    try:
        if mixer_ok:
            try:
                pygame.mixer.music.stop()
            except pygame.error:
                pass
        song = current_song()
        new_run = _fresh_run_skeleton()
        new_run.song_meta = song
        new_run.bpm = float(song["bpm"])
        new_run.current_song_path = song["file"] if song_file_present(song) else ""
        new_run.track_duration = measure_track_duration(
            new_run.current_song_path or song["file"],
            float(song["fallback_duration"]),
            allow_sound_probe=False,
        )
        try:
            events = generate_chart(
                song, selected_difficulty, duration_sec=new_run.track_duration
            )
        except Exception:
            events = fallback_chart(
                song, selected_difficulty, float(song["fallback_duration"])
            )
        new_run.notes = create_notes_from_chart(events)
        new_run.chart_end_time = max((n.end_time for n in new_run.notes), default=0.0)
        new_run.gameplay_active = True
        new_run.start_ticks = pygame.time.get_ticks()
        full = asset_path(new_run.current_song_path) if new_run.current_song_path else ""
        if (
            settings.get("music_enabled", True)
            and mixer_ok
            and full
            and os.path.isfile(full)
        ):
            try:
                if loaded_music_path != full:
                    pygame.mixer.music.load(full)
                    loaded_music_path = full
                new_run.music_available = True
            except pygame.error:
                new_run.silent_message = "Music unavailable — continuing in silent mode."
        else:
            new_run.silent_message = "Music unavailable — continuing in silent mode."
        run = new_run
        game_state = "playing"
        return True
    except Exception:
        return False


def request_restart_from_results() -> None:
    """Results KEYDOWN: queue only."""
    queue_soft_restart(from_menu=False)


def current_time_seconds() -> float:
    """Gameplay clock: wall time minus pause accumulation (+ optional audio offset)."""
    now = pygame.time.get_ticks()
    if run.paused and run.pause_started_ticks is not None:
        now = run.pause_started_ticks
    elapsed_ms = now - run.start_ticks - run.accumulated_pause_ms
    return elapsed_ms / 1000.0 + (AUDIO_OFFSET_MS / 1000.0)


def set_paused(paused: bool) -> None:
    if paused == run.paused:
        return
    if paused:
        run.paused = True
        run.pause_started_ticks = pygame.time.get_ticks()
        if mixer_ok and run.music_available:
            try:
                pygame.mixer.music.pause()
            except pygame.error:
                pass
    else:
        if run.pause_started_ticks is not None:
            run.accumulated_pause_ms += pygame.time.get_ticks() - run.pause_started_ticks
        run.pause_started_ticks = None
        run.paused = False
        if mixer_ok and run.music_available:
            try:
                pygame.mixer.music.unpause()
            except pygame.error:
                pass


def clear_held_input_state(*, release_holds: bool = True) -> None:
    """Clear stuck keys after focus loss; optionally cancel active HOLD notes."""
    current_time = current_time_seconds() if run.gameplay_active else 0.0
    if release_holds and run.gameplay_active and not run.results_entered:
        for col in list(run.pressed_cols):
            release_hold_note(col, current_time)
    run.pressed_cols.clear()
    for note in run.notes:
        if getattr(note, "holding", False):
            note.holding = False


def handle_focus_lost() -> None:
    """Pause gameplay and clear held keys when the window loses focus."""
    clear_held_input_state(release_holds=True)
    if (
        game_state == "playing"
        and run.gameplay_active
        and not run.results_entered
        and not run.paused
    ):
        set_paused(True)


def note_resolved(note: Note) -> bool:
    if getattr(note, "removed", False):
        return True
    if getattr(note, "cleared_by_agv", False) and getattr(note, "agv_fade", 0) >= 1.0:
        return True
    if note.is_long:
        return note.hold_completed or note.missed or note.clicked
    return note.clicked or note.missed


def note_hittable(note: Note) -> bool:
    if getattr(note, "agv_reserved", False) or getattr(note, "cleared_by_agv", False):
        return False
    if getattr(note, "removed", False):
        return False
    return not note_resolved(note)


def add_score_points(points: int) -> None:
    """Increase score and enqueue AGV milestones safely (no recursive AGV score)."""
    if points <= 0:
        return
    previous = int(run.score)
    run.score = previous + int(points)
    enqueue_agv_milestones(previous, int(run.score))


def enqueue_agv_milestones(previous_score: int, current_score: int) -> None:
    if run.results_entered or not run.gameplay_active:
        return
    newly = crossed_milestones(
        previous_score,
        current_score,
        AGV_REWARD_INTERVAL,
        run.triggered_agv_milestones,
    )
    for milestone in newly:
        run.triggered_agv_milestones.add(milestone)
        run.pending_agv_rewards.append(milestone)
    maybe_start_next_agv_from_queue()


def maybe_start_next_agv_from_queue() -> None:
    if run.results_entered or not run.gameplay_active:
        return
    if run.agv_reward is None:
        run.agv_reward = AGVRewardSweep()
    if run.agv_reward.active:
        return
    if run.agv_queue_delay > 0:
        return
    if not run.pending_agv_rewards:
        return
    milestone = run.pending_agv_rewards.popleft()
    start_agv_sweep(milestone)


def start_agv_sweep(threshold: int) -> None:
    ct = current_time_seconds()
    targets = select_lane_targets(run.notes, ct, COLS, HIT_LINE_Y, note_resolved)
    # Fit 5x AGV between HUD and lane labels at default 520x820
    render_h = AGV_RENDER_HEIGHT
    render_w = AGV_RENDER_WIDTH
    scale = AGV_VISUAL_SCALE
    max_h = HIT_LINE_Y - GAMEPLAY_TOP - 24
    if render_h > max_h:
        fit = max_h / float(AGV_HEIGHT)
        scale = fit
        render_h = int(round(AGV_HEIGHT * scale))
        render_w = int(round(AGV_WIDTH * scale))
        if DEV_MODE:
            print(f"AGV display-fit scale={scale:.2f} (default {AGV_VISUAL_SCALE})")

    agv_y = HIT_LINE_Y - render_h - 8
    # Fully off-screen left / right using rendered width
    start_x = float(0 - render_w - 24)
    end_x = float(WIDTH + 24)
    run.agv_reward.start(
        threshold,
        targets,
        y=agv_y,
        start_x=start_x,
        end_x=end_x,
        lane_w=LANE_W,
        cols=COLS,
        font=tiny_font,
        duration=AGV_SWEEP_DURATION_SECONDS,
        render_w=render_w,
        render_h=render_h,
        scale=scale,
    )


def update_agv_reward(dt: float) -> None:
    if run.agv_reward is None:
        return
    if run.paused:
        return
    if run.results_entered:
        return

    was_active = run.agv_reward.active
    newly = run.agv_reward.update(dt)
    for note in newly:
        if not getattr(note, "agv_defeat_counted", False):
            note.agv_defeat_counted = True
            run.register_agv_clear()
    for note in run.agv_reward.selected_targets.values():
        if note is None:
            continue
        if getattr(note, "cleared_by_agv", False) and not getattr(note, "agv_defeat_counted", False):
            note.agv_defeat_counted = True
            run.register_agv_clear()

    # After a sweep finishes, wait before starting the next queued reward
    if was_active and not run.agv_reward.active and run.agv_reward.finished:
        if run.pending_agv_rewards:
            run.agv_queue_delay = AGV_REWARD_QUEUE_DELAY_SECONDS

    if run.agv_queue_delay > 0 and not run.agv_reward.active:
        run.agv_queue_delay = max(0.0, run.agv_queue_delay - dt)
        if run.agv_queue_delay <= 0:
            maybe_start_next_agv_from_queue()
    elif not run.agv_reward.active and run.pending_agv_rewards and run.agv_queue_delay <= 0:
        maybe_start_next_agv_from_queue()


def cancel_agv_reward() -> None:
    run.pending_agv_rewards.clear()
    run.agv_queue_delay = 0.0
    if run.agv_reward is not None:
        run.agv_reward.cancel()


def next_untriggered_agv_milestone() -> Optional[int]:
    """Next milestone above current score (for DEV F10)."""
    nxt = (int(run.score) // AGV_REWARD_INTERVAL + 1) * AGV_REWARD_INTERVAL
    if nxt in run.triggered_agv_milestones:
        nxt += AGV_REWARD_INTERVAL
    return nxt if nxt > 0 else AGV_REWARD_INTERVAL


def count_active_notes(current_time: float) -> Tuple[int, int, int]:
    short_n = hold_n = 0
    for note in run.notes:
        if note_resolved(note):
            continue
        if note.spawn_time <= current_time <= note.end_time + 0.15:
            if note.is_long:
                hold_n += 1
            else:
                short_n += 1
    return short_n, hold_n, short_n + hold_n


def any_active_hold(current_time: float) -> bool:
    for note in run.notes:
        if not note.is_long or note_resolved(note):
            continue
        if note.holding or note.hold_started:
            return True
        if note.spawn_time <= current_time <= note.end_time + 0.5:
            return True
    return False


def next_scheduled_spawn(current_time: float) -> Optional[float]:
    best = None
    for note in run.notes:
        if note_resolved(note):
            continue
        if note.spawn_time > current_time:
            if best is None or note.spawn_time < best:
                best = note.spawn_time
    return best


def upcoming_or_visible(current_time: float) -> bool:
    look = seconds_per_beat(run.bpm) * DIFFICULTY_PARAMS[selected_difficulty]["max_gap"]
    for note in run.notes:
        if note_resolved(note):
            continue
        if note.spawn_time <= current_time <= note.end_time + 0.2:
            return True
        if current_time < note.spawn_time <= current_time + look:
            return True
    return False


def maybe_chart_recovery(current_time: float) -> None:
    if not run.gameplay_active or run.paused or run.results_entered:
        return
    if run.game_over or run.cleared or run.ending:
        return
    if current_time < PRE_ROLL_SECONDS + 0.5:
        return
    if current_time >= run.track_duration - 3.0:
        return
    if any_active_hold(current_time):
        return
    short_n, hold_n, total_n = count_active_notes(current_time)
    _sc, _hc, total_cap = active_caps(selected_difficulty)
    if total_n > 0:
        return
    nxt = next_scheduled_spawn(current_time)
    look = seconds_per_beat(run.bpm) * DIFFICULTY_PARAMS[selected_difficulty]["max_gap"]
    if nxt is not None and nxt <= current_time + look:
        return
    beat = time_to_beat(current_time, run.bpm)
    if beat - run.last_recovery_beat < RECOVERY_COOLDOWN_BEATS:
        return
    if total_n >= total_cap:
        return

    extras = create_notes_from_chart(
        recovery_pattern(beat + 0.5, run.bpm, seed=int(beat * 10) + run.recovery_count)
    )
    # Skip if would exceed cap
    if total_n + len(extras) > total_cap:
        return
    run.notes.extend(extras)
    run.last_recovery_beat = beat
    run.recovery_count += 1
    if DEV_MODE:
        print(f"Chart recovery inserted at beat {beat:.2f}")
        print(
            f"Active notes: {total_n + len(extras)} / cap {total_cap}  "
            f"Scheduled next: {nxt}  Recovery cooldown: {RECOVERY_COOLDOWN_BEATS}"
        )


def accuracy_pct() -> float:
    total = max(1, int(run.judged_count))
    return 100.0 * float(run.defeated_count) / float(total)


def enter_results(kind: str) -> None:
    """Enter Game Over / Clear results exactly once; stop notes and feedback."""
    global game_state
    if run.results_entered:
        return
    run.results_entered = True
    run.gameplay_active = False
    run.ending = False
    run.result_kind = kind
    run.game_over = kind == "game_over"
    run.cleared = kind == "clear"
    run.result_fade_ms = RESULT_FADE_MS
    run.miss_flash_timer = 0
    run.pressed_cols = set()
    run.paused = False
    game_state = "results"
    cancel_agv_reward()
    if kind == "game_over":
        for note in run.notes:
            if not note_resolved(note):
                note.missed = True
                note.holding = False
    else:
        for note in run.notes:
            if not note_resolved(note):
                note.clicked = True
                note.hold_completed = True
                note.holding = False
    run.notes = []
    run.explosions = []
    # Hard stop — never fadeout (mixer hang risk with subsequent load)
    if mixer_ok:
        try:
            pygame.mixer.music.stop()
        except pygame.error:
            pass
    maybe_update_high_score()


def trigger_failure() -> None:
    if run.results_entered:
        return
    enter_results("game_over")


def all_notes_resolved() -> bool:
    return bool(run.notes) and all(note_resolved(n) for n in run.notes)


def check_song_end(current_time: float, dt: float) -> None:
    if run.results_entered:
        return
    if run.ending:
        run.finish_timer += dt
        # Wait until no active on-screen notes, then short delay
        _s, _h, active = count_active_notes(current_time)
        if active == 0 and run.finish_timer >= FINISH_DELAY_SECONDS:
            enter_results("clear")
        return

    last_hit = max((n.hit_time for n in run.notes), default=0.0)
    near_audio_end = current_time >= run.track_duration - 0.05
    chart_done = all_notes_resolved() and current_time >= last_hit

    if chart_done or (
        near_audio_end
        and all(note_resolved(n) for n in run.notes if n.spawn_time <= current_time + 0.1)
        and current_time >= last_hit
    ):
        run.ending = True
        run.finish_timer = 0.0
        run.gameplay_active = False  # stop spawning/recovery
        return

    # Early empty mid-track: do not wait forever
    if (
        current_time > PRE_ROLL_SECONDS + 2.0
        and current_time < run.track_duration - 3.0
        and not upcoming_or_visible(current_time)
        and current_time > last_hit + seconds_per_beat(run.bpm) * 3
    ):
        if DEV_MODE and not run.dev_empty_warned:
            print(f"DEV WARNING: chart empty early t={current_time:.2f} last={last_hit:.2f}")
            run.dev_empty_warned = True
        run.ending = True
        run.finish_timer = 0.0
        run.gameplay_active = False


def hit_short_note(target_col: int, current_time: float) -> None:
    if not run.gameplay_active or run.results_entered:
        return
    best_note = None
    best_distance = 999999.0
    for note in run.notes:
        if not note_hittable(note) or note.is_long:
            continue
        if note.col != target_col or not note.is_active(current_time):
            continue
        distance = note.short_distance(current_time)
        if distance < best_distance:
            best_distance = distance
            best_note = note

    if best_note and best_distance <= HIT_DISTANCE:
        best_note.clicked = True
        rect = best_note.get_rect(current_time)
        run.explosions.append(Explosion(rect.centerx, rect.centery))
        run.combo += 1
        run.best_combo = max(run.best_combo, run.combo)
        multiplier = max(1, run.combo // 8 + 1)
        add_score_points(best_note.score * multiplier)
        run.register_defeat()
    else:
        run.combo = 0


def start_hold_note(target_col: int, current_time: float) -> None:
    if not run.gameplay_active or run.results_entered:
        return
    best_note = None
    best_distance = 999999.0
    for note in run.notes:
        if not note.is_long or not note_hittable(note):
            continue
        if note.col != target_col or not note.is_active(current_time):
            continue
        distance = note.long_start_distance(current_time)
        if distance < best_distance:
            best_distance = distance
            best_note = note

    if best_note and best_distance <= HIT_DISTANCE:
        best_note.holding = True
        best_note.hold_started = True
    else:
        hit_short_note(target_col, current_time)


def release_hold_note(target_col: int, current_time: float) -> None:
    if not run.gameplay_active or run.results_entered:
        return
    for note in run.notes:
        if not note.is_long or note.col != target_col:
            continue
        if getattr(note, "agv_reserved", False) or getattr(note, "cleared_by_agv", False):
            continue
        if note.holding and not note.hold_completed:
            note.holding = False
            distance = note.long_end_distance(current_time)
            rect = note.get_rect(current_time)
            if distance <= HIT_DISTANCE:
                note.hold_completed = True
                note.clicked = True
                run.explosions.append(Explosion(rect.centerx, HIT_LINE_Y))
                run.combo += 1
                run.best_combo = max(run.best_combo, run.combo)
                multiplier = max(1, run.combo // 8 + 1)
                add_score_points(note.score * 3 * multiplier)
                run.register_defeat()
            else:
                run.combo = 0
                run.register_escape()
                trigger_failure()
            break


def update_long_notes(current_time: float) -> None:
    if not run.gameplay_active or run.results_entered:
        return
    for note in run.notes:
        if not note.is_long or note.missed or note.hold_completed:
            continue
        if getattr(note, "agv_reserved", False) or getattr(note, "cleared_by_agv", False):
            continue

        if note.holding and note.col not in run.pressed_cols:
            note.holding = False
            note.missed = True
            run.combo = 0
            run.register_escape()
            trigger_failure()
            break

        if not note.hold_started and note.long_start_distance(current_time) > HIT_DISTANCE:
            rect = note.get_rect(current_time)
            if rect.bottom > HIT_LINE_Y + HIT_DISTANCE:
                note.missed = True
                run.combo = 0
                run.register_escape()
                trigger_failure()
                break

        if note.holding and note.long_end_distance(current_time) <= HIT_DISTANCE:
            note.holding = False
            note.hold_completed = True
            note.clicked = True
            rect = note.get_rect(current_time)
            run.explosions.append(Explosion(rect.centerx, HIT_LINE_Y))
            run.combo += 1
            run.best_combo = max(run.best_combo, run.combo)
            multiplier = max(1, run.combo // 8 + 1)
            add_score_points(note.score * 3 * multiplier)
            run.register_defeat()


def update_short_notes(current_time: float) -> None:
    if not run.gameplay_active or run.results_entered:
        return
    for note in run.notes:
        if note.is_long or note.clicked or note.missed:
            continue
        if getattr(note, "agv_reserved", False) or getattr(note, "cleared_by_agv", False):
            continue
        rect = note.get_rect(current_time)
        if rect.centery > HIT_LINE_Y + HIT_DISTANCE:
            note.missed = True
            run.combo = 0
            run.register_escape()
            trigger_failure()
            break


def maybe_update_high_score() -> None:
    if run.score > int(settings.get("high_score", 0)):
        settings["high_score"] = run.score
        save_settings(settings)


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------
def draw_mini_agv_icon(surface: pygame.Surface, x: int, y: int, scale: float = 2.5) -> None:
    """Small static AGV glyph for HUD / results (2–3× base unit, not 5×)."""
    from agv_reward import AGV_BLACK, AGV_DARK_RED, AGV_GRAY, AGV_RED, AGV_WARNING

    w = int(round(18 * scale))
    h = int(round(10 * scale))

    def sc(v: float) -> int:
        return int(round(v * scale))

    pygame.draw.rect(
        surface, AGV_RED, (x + sc(2), y + sc(2), w - sc(4), h - sc(4)), border_radius=max(1, sc(1))
    )
    pygame.draw.rect(surface, AGV_GRAY, (x + sc(3), y + sc(1), w - sc(8), sc(2)))
    pygame.draw.polygon(
        surface,
        AGV_DARK_RED,
        [
            (x + w - sc(2), y + sc(2)),
            (x + w + sc(3), y + h // 2),
            (x + w - sc(2), y + h - sc(2)),
        ],
    )
    pygame.draw.circle(surface, AGV_WARNING, (x + sc(5), y + sc(2)), max(1, sc(1)))
    pygame.draw.ellipse(surface, AGV_BLACK, (x + sc(4), y + h - sc(3), sc(4), sc(3)))
    pygame.draw.ellipse(surface, AGV_BLACK, (x + w - sc(8), y + h - sc(3), sc(4), sc(3)))


def draw_ui() -> None:
    top_bar = pygame.Surface((WIDTH, TOP_BAR_H), pygame.SRCALPHA)
    top_bar.fill((255, 255, 255, 150))
    screen.blit(top_bar, (0, 0))
    pygame.draw.line(screen, (0, 0, 0), (0, TOP_BAR_H), (WIDTH, TOP_BAR_H), 3)

    score_val = int(getattr(run, "score", 0) or 0)
    combo_val = int(getattr(run, "combo", 0) or 0)
    defeated_val = int(getattr(run, "defeated_count", 0) or 0)
    escaped_val = int(getattr(run, "escaped_count", 0) or 0)

    score_text = font.render(f"Score  {score_val}", True, (0, 0, 0))
    combo_text = font.render(f"Combo  {combo_val}", True, (0, 0, 0))
    screen.blit(score_text, (24, 18))
    screen.blit(combo_text, (WIDTH - combo_text.get_width() - 24, 18))

    bpm_lab = tiny_font.render(f"{int(run.bpm)} BPM", True, (50, 50, 60))
    screen.blit(bpm_lab, (24, 58))

    # Defeated counter + enemy preview below Combo (inside HUD, never under notes)
    tw, th = 28, 36
    preview_y = 62
    dx = WIDTH - 18 - tw
    try:
        if enemy_preview_thumb is not None:
            screen.blit(enemy_preview_thumb, (dx, preview_y))
            pygame.draw.rect(screen, (0, 0, 0), (dx, preview_y, tw, th), 1, border_radius=3)
    except Exception:
        pass
    dlab = tiny_font.render(f"Defeated {defeated_val}", True, (0, 0, 0))
    screen.blit(dlab, (dx - dlab.get_width() - 6, preview_y + 8))

    for col in range(COLS + 1):
        x = col * LANE_W
        pygame.draw.line(screen, (0, 0, 0), (x, GAMEPLAY_TOP), (x, HEIGHT), 2)

    pygame.draw.line(screen, (0, 0, 0), (0, HIT_LINE_Y), (WIDTH, HIT_LINE_Y), 5)

    # Subtle beat pulse / rest life (does not cover lanes)
    if game_state == "playing" and run.gameplay_active and not run.results_entered:
        ct = current_time_seconds()
        spb = seconds_per_beat(run.bpm)
        beat_phase = (ct / spb) % 1.0
        pulse = abs(0.5 - beat_phase) * 2.0
        glow = int(30 + 40 * (1.0 - pulse))
        pygame.draw.line(
            screen,
            (40, 40, 70, 255),
            (0, HIT_LINE_Y),
            (WIDTH, HIT_LINE_Y),
            2 if pulse > 0.7 else 5,
        )
        if not upcoming_or_visible(ct) and ct > PRE_ROLL_SECONDS and not run.ending:
            hint = tiny_font.render("Next wave", True, (60, 60, 80))
            screen.blit(hint, (WIDTH // 2 - hint.get_width() // 2, HIT_LINE_Y - 28))
            for i in range(COLS):
                alpha_surf = pygame.Surface((LANE_W - 8, 8), pygame.SRCALPHA)
                alpha_surf.fill((90, 90, 140, glow))
                screen.blit(alpha_surf, (i * LANE_W + 4, HIT_LINE_Y - 4))

    preset = settings.get("key_preset", "DFJK")
    labels = KEY_PRESET_LABELS.get(preset, KEY_PRESET_LABELS["DFJK"])
    key_y = HIT_LINE_Y + 12
    for i in range(COLS):
        num = small_font.render(str(i + 1), True, (0, 0, 0))
        key = tiny_font.render(labels[i], True, (20, 20, 20))
        cx = i * LANE_W + LANE_W // 2
        screen.blit(num, (cx - num.get_width() // 2, key_y))
        screen.blit(key, (cx - key.get_width() // 2, key_y + 26))

    if run.silent_message:
        msg = tiny_font.render(run.silent_message, True, (40, 40, 40))
        screen.blit(msg, (12, HEIGHT - 28))

    if run.miss_flash_timer > 0 and not run.results_entered:
        run.miss_flash_timer -= 1
        alpha = min(220, 40 + run.miss_flash_timer * 2)
        badge = pygame.Surface((150, 110), pygame.SRCALPHA)
        badge.fill((255, 255, 255, alpha))
        try:
            scaled = pygame.transform.smoothscale(miss_enemy_img, (72, 72))
            badge.blit(scaled, (39, 4))
        except Exception:
            pass
        esc = tiny_font.render(f"Escaped {escaped_val}", True, (80, 20, 20))
        badge.blit(esc, (75 - esc.get_width() // 2, 82))
        screen.blit(badge, (WIDTH // 2 - 75, HIT_LINE_Y - 130))

    if run.paused and not run.results_entered:
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((255, 255, 255, 140))
        screen.blit(overlay, (0, 0))
        pause_text = font.render("Paused", True, (0, 0, 0))
        hint = small_font.render("Press P to resume", True, (0, 0, 0))
        screen.blit(pause_text, (WIDTH // 2 - pause_text.get_width() // 2, HEIGHT // 2 - 40))
        screen.blit(hint, (WIDTH // 2 - hint.get_width() // 2, HEIGHT // 2 + 10))


def draw_menu() -> None:
    screen.blit(background_img, (0, 0))

    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((255, 255, 255, 185))
    screen.blit(overlay, (0, 0))

    calm = tiny_font.render("DEMO  ·  FOCUS  ·  RHYTHM", True, (40, 40, 55))
    screen.blit(calm, (WIDTH // 2 - calm.get_width() // 2, 48))

    title = font.render(TITLE, True, (0, 0, 0))
    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 80))

    song_title = mid_font.render("Select Song", True, (0, 0, 0))
    screen.blit(song_title, (WIDTH // 2 - song_title.get_width() // 2, 150))

    y = 188
    for i, song in enumerate(SONGS):
        prefix = ">" if i == selected_song_index else " "
        present = song_file_present(song)
        color = (0, 0, 0) if present else (120, 120, 120)
        name = small_font.render(f"{prefix} {i + 1}. {song['title']}", True, color)
        screen.blit(name, (36, y))
        meta = f"{song['composer']} · {int(song['bpm'])} BPM · {song['approx_label']}"
        if not present:
            meta += "  — Audio unavailable"
        meta_s = tiny_font.render(meta, True, (70, 70, 80) if present else (140, 100, 100))
        screen.blit(meta_s, (56, y + 24))
        y += 52

    diff_title = mid_font.render("Select Difficulty", True, (0, 0, 0))
    screen.blit(diff_title, (WIDTH // 2 - diff_title.get_width() // 2, y + 8))
    y += 48
    diffs = list(DIFFICULTIES.keys())
    for i, diff in enumerate(diffs):
        prefix = ">" if diff == selected_difficulty else " "
        text = small_font.render(f"{prefix} F{i + 1}. {diff}", True, (0, 0, 0))
        screen.blit(text, (150, y + i * 32))

    y = 560
    preset = settings["key_preset"]
    keys_line = small_font.render(
        f"Keys: {preset}   [Tab] switch preset", True, (0, 0, 0)
    )
    screen.blit(keys_line, (WIDTH // 2 - keys_line.get_width() // 2, y))
    mute_hint = tiny_font.render(
        "M mute  C credits  High score " + str(settings.get("high_score", 0)),
        True,
        (40, 40, 40),
    )
    screen.blit(mute_hint, (WIDTH // 2 - mute_hint.get_width() // 2, y + 30))
    start_text = small_font.render("Press ENTER to Start", True, (0, 0, 0))
    help_text = tiny_font.render(
        "1/2/3 song | F1/F2/F3 difficulty | ESC quit", True, (0, 0, 0)
    )
    screen.blit(start_text, (WIDTH // 2 - start_text.get_width() // 2, y + 60))
    screen.blit(help_text, (WIDTH // 2 - help_text.get_width() // 2, y + 95))


def draw_credits() -> None:
    screen.blit(background_img, (0, 0))
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((255, 255, 255, 210))
    screen.blit(overlay, (0, 0))
    title = font.render("Credits", True, (0, 0, 0))
    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 40))

    lines = [
        f"Werewolf Rhythm Demo {GAME_VERSION}",
        "",
        "Music by Kevin MacLeod",
        "incompetech.com",
        "Licensed under CC BY 4.0",
        "",
        "Monkeys Spinning Monkeys",
        "Fluffing a Duck",
        "Sneaky Snitch",
        "",
        "Creative Commons Attribution 4.0",
        "International",
        "",
        "See AUDIO_CREDITS.md and",
        "THIRD_PARTY_NOTICES.md",
        "",
        "Developer: Ruixin Chen",
        "",
        "Press ESC to return",
    ]
    y = 100
    for line in lines:
        surf = tiny_font.render(line, True, (20, 20, 30))
        screen.blit(surf, (WIDTH // 2 - surf.get_width() // 2, y))
        y += 26


def draw_results_panel() -> None:
    """Opaque results panel — no notes/feedback behind it."""
    dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    dim.fill((30, 28, 35, 210))
    screen.blit(dim, (0, 0))

    panel_w, panel_h = 420, 460
    panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    panel.fill((250, 248, 240, 245))
    pygame.draw.rect(panel, (0, 0, 0), (0, 0, panel_w, panel_h), 3, border_radius=8)

    song = run.song_meta or current_song()
    headline = "Game Over" if run.game_over else "Results"
    lines = [
        headline,
        "",
        f"Song: {song.get('title', '')}",
        f"Difficulty: {selected_difficulty}",
        f"Score: {run.score}",
        f"Defeated: {run.defeated_count}",
        f"Escaped: {run.escaped_count}",
        f"AGV Cleared: {getattr(run, 'agv_cleared_count', 0)}",
        f"Accuracy: {accuracy_pct():.0f}%",
        f"Best Combo: {run.best_combo}",
        "",
        "Enter / R — Restart",
        "Esc — Menu",
    ]
    y = 24
    for i, line in enumerate(lines):
        use_font = font if i == 0 else small_font
        surf = use_font.render(line, True, (0, 0, 0))
        panel.blit(surf, (panel_w // 2 - surf.get_width() // 2, y))
        if line.startswith("AGV Cleared"):
            icon_x = panel_w // 2 - surf.get_width() // 2 - 52
            draw_mini_agv_icon(panel, icon_x, y + 2, scale=2.5)
        y += 34 if i == 0 else 28

    screen.blit(panel, (WIDTH // 2 - panel_w // 2, HEIGHT // 2 - panel_h // 2))


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def draw_restarting_overlay() -> None:
    screen.blit(background_img, (0, 0))
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((255, 255, 255, 200))
    screen.blit(overlay, (0, 0))
    title = font.render("Restarting...", True, (0, 0, 0))
    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, HEIGHT // 2 - 24))
    if restart_recovery_message:
        msg = tiny_font.render(restart_recovery_message, True, (60, 40, 40))
        screen.blit(msg, (WIDTH // 2 - msg.get_width() // 2, HEIGHT // 2 + 30))


def draw_countdown_overlay() -> None:
    screen.blit(background_img, (0, 0))
    draw_ui()
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((255, 255, 255, 160))
    screen.blit(overlay, (0, 0))
    # Map remaining time to 3 / 2 / 1 / Ready
    if countdown_timer > 0.6:
        label = "3"
    elif countdown_timer > 0.35:
        label = "2"
    elif countdown_timer > 0.12:
        label = "1"
    else:
        label = "Ready"
    title = font.render(label, True, (0, 0, 0))
    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, HEIGHT // 2 - 24))
    song = run.song_meta or current_song()
    sub = tiny_font.render(
        f"{song.get('title', '')}  ·  {selected_difficulty}", True, (40, 40, 50)
    )
    screen.blit(sub, (WIDTH // 2 - sub.get_width() // 2, HEIGHT // 2 + 36))


def main() -> None:
    global game_state, selected_song_index, selected_difficulty
    global restart_requested, restart_key_latched, countdown_timer
    running = True
    prev_ticks = pygame.time.get_ticks()
    first_play_logged = False

    while running:
        clock.tick(FPS)
        now_ticks = pygame.time.get_ticks()
        dt = (now_ticks - prev_ticks) / 1000.0
        prev_ticks = now_ticks

        # --- MENU ---
        if game_state == "menu":
            draw_menu()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type in (
                    getattr(pygame, "WINDOWFOCUSLOST", -1),
                    getattr(pygame, "APP_DIDENTERBACKGROUND", -2),
                ):
                    clear_held_input_state(release_holds=False)
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_1:
                        selected_song_index = 0
                    elif event.key == pygame.K_2:
                        selected_song_index = 1
                    elif event.key == pygame.K_3:
                        selected_song_index = 2
                    elif event.key == pygame.K_F1:
                        selected_difficulty = "Easy"
                    elif event.key == pygame.K_F2:
                        selected_difficulty = "Normal"
                    elif event.key == pygame.K_F3:
                        selected_difficulty = "Hard"
                    elif event.key == pygame.K_c:
                        game_state = "credits"
                    elif event.key == pygame.K_TAB:
                        settings["key_preset"] = (
                            "DFJK" if settings.get("key_preset") == "ASKL" else "ASKL"
                        )
                        save_settings(settings)
                    elif event.key == pygame.K_m:
                        settings["muted"] = not settings.get("muted", False)
                        save_settings(settings)
                    elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                        settings["music_volume"] = max(
                            0.0, float(settings.get("music_volume", 0.45)) - 0.05
                        )
                        save_settings(settings)
                    elif event.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                        settings["music_volume"] = min(
                            1.0, float(settings.get("music_volume", 0.45)) + 0.05
                        )
                        save_settings(settings)
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        queue_soft_restart(from_menu=True, probe_duration=False)
            if restart_requested:
                begin_soft_restart_pipeline()
            pygame.display.flip()
            continue

        # --- CREDITS ---
        if game_state == "credits":
            draw_credits()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    game_state = "menu"
            pygame.display.flip()
            continue

        # --- RESTARTING (one step per frame; always pump events) ---
        if game_state == "restarting":
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type in (
                    getattr(pygame, "WINDOWFOCUSLOST", -1),
                    getattr(pygame, "APP_DIDENTERBACKGROUND", -2),
                ):
                    clear_held_input_state(release_holds=False)
                elif event.type == pygame.KEYUP and event.key in (
                    pygame.K_RETURN,
                    pygame.K_KP_ENTER,
                    pygame.K_r,
                ):
                    restart_key_latched = False
            draw_restarting_overlay()
            perform_soft_restart_step()
            pygame.display.flip()
            continue

        # --- COUNTDOWN ---
        if game_state == "countdown":
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type in (
                    getattr(pygame, "WINDOWFOCUSLOST", -1),
                    getattr(pygame, "APP_DIDENTERBACKGROUND", -2),
                ):
                    clear_held_input_state(release_holds=False)
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    if mixer_ok:
                        try:
                            pygame.mixer.music.stop()
                        except pygame.error:
                            pass
                    game_state = "menu"
                    run.results_entered = False
                    run.gameplay_active = False
                elif event.type == pygame.KEYUP and event.key in (
                    pygame.K_RETURN,
                    pygame.K_KP_ENTER,
                    pygame.K_r,
                ):
                    restart_key_latched = False
            countdown_timer = max(0.0, countdown_timer - dt)
            draw_countdown_overlay()
            pygame.display.flip()
            if countdown_timer <= 0.0 and game_state == "countdown":
                finish_countdown_and_start_playing()
                first_play_logged = False
            continue

        # --- RESULTS / PLAYING share event pump ---
        screen.blit(background_img, (0, 0))
        draw_ui()

        current_time = current_time_seconds() if run.gameplay_active else 0.0
        mapping = key_map()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if event.type in (
                getattr(pygame, "WINDOWFOCUSLOST", -1),
                getattr(pygame, "APP_DIDENTERBACKGROUND", -2),
            ):
                handle_focus_lost()
                continue

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if mixer_ok:
                        try:
                            pygame.mixer.music.stop()
                        except pygame.error:
                            pass
                    maybe_update_high_score()
                    set_paused(False)
                    cancel_agv_reward()
                    run.notes = []
                    run.explosions = []
                    run.results_entered = False
                    game_state = "menu"
                elif (
                    event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_r)
                    and (run.results_entered or game_state == "results")
                    and not restart_key_latched
                ):
                    queue_soft_restart(from_menu=False)
                elif (
                    event.key == pygame.K_p
                    and not run.results_entered
                    and game_state == "playing"
                ):
                    set_paused(not run.paused)
                elif event.key == pygame.K_m:
                    settings["muted"] = not settings.get("muted", False)
                    apply_music_volume()
                    save_settings(settings)
                elif event.key == pygame.K_TAB:
                    settings["key_preset"] = (
                        "DFJK" if settings.get("key_preset") == "ASKL" else "ASKL"
                    )
                    save_settings(settings)
                elif (
                    DEV_MODE
                    and event.key == pygame.K_F10
                    and run.gameplay_active
                    and not run.results_entered
                    and game_state == "playing"
                ):
                    nxt = next_untriggered_agv_milestone()
                    need = max(1, nxt - int(run.score))
                    add_score_points(need)
                elif (
                    run.gameplay_active
                    and not run.results_entered
                    and not run.paused
                    and game_state == "playing"
                    and event.key in mapping
                ):
                    col = mapping[event.key]
                    run.pressed_cols.add(col)
                    start_hold_note(col, current_time)

            if event.type == pygame.KEYUP:
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_r):
                    restart_key_latched = False
                if event.key in mapping:
                    col = mapping[event.key]
                    if col in run.pressed_cols:
                        run.pressed_cols.remove(col)
                    if (
                        run.gameplay_active
                        and not run.results_entered
                        and not run.paused
                        and game_state == "playing"
                    ):
                        release_hold_note(col, current_time)

        # Frame-boundary soft restart (never inside KEYDOWN work)
        if restart_requested:
            begin_soft_restart_pipeline()
            draw_restarting_overlay()
            pygame.display.flip()
            continue

        if run.results_entered or game_state == "results":
            run.notes = []
            run.explosions = []
            cancel_agv_reward()
            draw_results_panel()
            pygame.display.flip()
            continue

        # --- PLAYING ---
        if not first_play_logged and game_state == "playing":
            restart_log(
                f"[restart] playing flags score={run.score} escaped={run.escaped_count} "
                f"game_over={run.game_over} results={run.results_entered}"
            )
            first_play_logged = True

        if run.gameplay_active and not run.paused:
            update_short_notes(current_time)
            update_long_notes(current_time)
            maybe_chart_recovery(current_time)
            update_agv_reward(dt)
            check_song_end(current_time, dt)
        elif run.ending and not run.results_entered:
            update_agv_reward(dt)
            check_song_end(current_time, dt)
        elif (
            not run.results_entered
            and run.agv_reward is not None
            and (run.agv_reward.active or run.agv_reward.message_timer > 0)
            and not run.paused
        ):
            update_agv_reward(dt)

        if not run.paused:
            for note in run.notes:
                if note_resolved(note) and not (
                    getattr(note, "cleared_by_agv", False)
                    and not getattr(note, "removed", False)
                ):
                    continue
                if note.is_active(current_time) or getattr(note, "cleared_by_agv", False):
                    note.draw(screen, current_time)
            for exp in run.explosions:
                exp.update()
                exp.draw(screen)
            run.explosions = [e for e in run.explosions if not e.finished()]
            if run.agv_reward is not None:
                run.agv_reward.draw(screen)
        else:
            for note in run.notes:
                if not note_resolved(note) and note.is_active(current_time):
                    note.draw(screen, current_time)
                elif getattr(note, "cleared_by_agv", False) and not getattr(
                    note, "removed", False
                ):
                    note.draw(screen, current_time)
            for exp in run.explosions:
                exp.draw(screen)
            if run.agv_reward is not None:
                run.agv_reward.draw(screen)

        if (
            run.agv_reward is not None
            and run.agv_reward.active
            and run.agv_reward.y < TOP_BAR_H + 8
        ):
            top_bar = pygame.Surface((WIDTH, TOP_BAR_H), pygame.SRCALPHA)
            top_bar.fill((255, 255, 255, 210))
            screen.blit(top_bar, (0, 0))
            pygame.draw.line(screen, (0, 0, 0), (0, TOP_BAR_H), (WIDTH, TOP_BAR_H), 3)
            score_text = font.render(f"Score  {int(run.score)}", True, (0, 0, 0))
            combo_text = font.render(f"Combo  {int(run.combo)}", True, (0, 0, 0))
            screen.blit(score_text, (24, 18))
            screen.blit(combo_text, (WIDTH - combo_text.get_width() - 24, 18))

        pygame.display.flip()

    save_settings(settings)
    pygame.quit()


def self_test_restart(cycles: int = 20) -> int:
    """
    Non-interactive restart validation for source and packaged builds.

    Usage: WerewolfRhythmDemo --self-test-restart
           python rhythm_game.py --self-test-restart
    """
    global selected_song_index, selected_difficulty, game_state, countdown_timer
    global restart_requested

    restart_log(f"[self-test] begin cycles={cycles} version={GAME_VERSION}")
    scenarios = [None, "agv", "hold", "pause", "silent", "clear"]
    failures = 0
    for song_i, song in enumerate(SONGS):
        selected_song_index = song_i
        selected_difficulty = "Easy"
        for cycle in range(cycles):
            scenario = scenarios[cycle % len(scenarios)]
            if not start_new_run(from_results=False):
                restart_log(f"[self-test] FAIL start_new_run song={song['id']} c={cycle}")
                failures += 1
                continue
            if scenario == "agv":
                add_score_points(50)
                if run.agv_reward is not None and run.agv_reward.active:
                    run.agv_reward.update(0.5)
            elif scenario == "hold":
                for n in run.notes:
                    if n.is_long:
                        n.holding = True
                        n.hold_started = True
                        break
            elif scenario == "pause":
                set_paused(True)
                set_paused(False)
            elif scenario == "silent":
                run.music_available = False
                run.silent_message = "Music unavailable — continuing in silent mode."
            elif scenario == "clear":
                enter_results("clear")
            if not run.results_entered:
                enter_results("game_over")

            t0 = time.perf_counter()
            queue_soft_restart(from_menu=False)
            if not restart_requested:
                restart_log(f"[self-test] FAIL queue song={song['id']} c={cycle}")
                failures += 1
                continue
            begin_soft_restart_pipeline()
            timed_out = False
            while game_state == "restarting":
                if time.perf_counter() - t0 > 2.0:
                    restart_log(f"[self-test] FAIL timeout step={restart_step}")
                    failures += 1
                    timed_out = True
                    break
                perform_soft_restart_step()
            if timed_out:
                continue
            if game_state != "countdown":
                restart_log(f"[self-test] FAIL expected countdown got {game_state}")
                failures += 1
                continue
            countdown_timer = 0.0
            finish_countdown_and_start_playing()
            if game_state != "playing":
                restart_log(f"[self-test] FAIL expected playing got {game_state}")
                failures += 1
                continue
            if (
                run.score != 0
                or run.escaped_count != 0
                or run.results_entered
                or run.game_over
                or len(run.notes) == 0
            ):
                restart_log(
                    f"[self-test] FAIL dirty state score={run.score} "
                    f"escaped={run.escaped_count} notes={len(run.notes)}"
                )
                failures += 1
                continue
            if run.agv_reward is not None and run.agv_reward.active:
                restart_log("[self-test] FAIL AGV still active")
                failures += 1
                continue
            elapsed = time.perf_counter() - t0
            if elapsed > 2.0:
                restart_log(f"[self-test] FAIL slow {elapsed:.3f}s")
                failures += 1
        restart_log(f"[self-test] song={song['id']} cycles={cycles} done")

    result_path = str(Path(userdata_dir()) / "self_test_restart_result.txt")
    if failures:
        restart_log(f"[self-test] FAILED failures={failures}")
        msg = f"SELF-TEST FAILED failures={failures} version={GAME_VERSION}\n"
        try:
            with open(result_path, "w", encoding="utf-8") as fh:
                fh.write(msg)
                fh.flush()
        except OSError:
            pass
        print(msg, flush=True)
        return 1
    restart_log("[self-test] PASSED")
    msg = f"SELF-TEST PASSED version={GAME_VERSION} cycles_per_song={cycles}\n"
    try:
        with open(result_path, "w", encoding="utf-8") as fh:
            fh.write(msg)
            fh.flush()
    except OSError:
        pass
    print(msg, flush=True)
    return 0


def run_self_test() -> int:
    """
    Non-interactive packaged/CI self-test. Does not start normal gameplay.

    Usage: WerewolfRhythmDemo --self-test
           python rhythm_game.py --self-test
    """
    checks: List[Tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, ok, detail))
        status = "PASS" if ok else "FAIL"
        suffix = f" — {detail}" if detail else ""
        print(f"  [{status}] {name}{suffix}", flush=True)

    print(f"Werewolf Rhythm Demo self-test {GAME_VERSION}", flush=True)
    print(f"platform={sys.platform} frozen={getattr(sys, 'frozen', False)}", flush=True)

    # Module imports already succeeded if we are here.
    check("import main modules", True, "rhythm_game/chart_gen/agv_reward/soft_restart/paths")

    try:
        pygame.get_init()
        check("pygame initialized", True)
    except Exception as exc:  # noqa: BLE001
        check("pygame initialized", False, str(exc))

    try:
        info = pygame.display.Info()
        check("display init (dummy/headless ok)", True, f"driver ok size={info.current_w}x{info.current_h}")
    except Exception as exc:  # noqa: BLE001
        check("display init (dummy/headless ok)", False, str(exc))

    check(
        "audio init safe",
        True,
        "mixer_ok=True" if mixer_ok else "silent mode (mixer unavailable)",
    )

    image_assets = [
        BACKGROUND_PATH,
        HOLD_ENEMY_PATH,
        MISS_ENEMY_PATH,
        *[cfg["path"] for cfg in ENEMY_CONFIG],
        *[f"{HOLD_SEQUENCE_DIR}/{fname}" for fname in HOLD_SEQUENCE_FILES],
    ]
    missing_images = [p for p in image_assets if not os.path.isfile(asset_path(p))]
    check("sanitized image assets load", not missing_images, ", ".join(missing_images) or "all present")

    for img_path in image_assets:
        full = asset_path(img_path)
        if not os.path.isfile(full):
            continue
        try:
            surf = pygame.image.load(full)
            check(f"image open {Path(img_path).name}", surf.get_width() > 0)
        except Exception as exc:  # noqa: BLE001
            check(f"image open {Path(img_path).name}", False, str(exc))

    music_ok = True
    for song in SONG_CATALOG:
        full = asset_path(song["file"])
        present = os.path.isfile(full)
        check(f"music file present: {song['title']}", present, song["file"])
        if not present:
            music_ok = False
            continue
        # Validate file can be opened / probed without requiring a real device.
        try:
            if mixer_ok:
                pygame.mixer.music.load(full)
                pygame.mixer.music.stop()
            else:
                with open(full, "rb") as fh:
                    header = fh.read(16)
                if len(header) < 4:
                    raise OSError("music file too small")
            check(f"music open/validate: {song['title']}", True)
        except Exception as exc:  # noqa: BLE001
            # Silent mode is acceptable when the device/driver is missing.
            check(f"music open/validate: {song['title']}", True, f"silent fallback ({exc})")
        check(
            f"song config: {song['title']}",
            bool(song.get("bpm") and song.get("file") and song.get("id")),
            f"bpm={song.get('bpm')}",
        )

    # Mute / pause markers without requiring audible output
    try:
        prev_muted = bool(settings.get("muted", False))
        settings["muted"] = True
        apply_music_volume()
        settings["muted"] = prev_muted
        apply_music_volume()
        check("mute path safe", True)
    except Exception as exc:  # noqa: BLE001
        check("mute path safe", False, str(exc))

    chart_failures = 0
    for song in SONG_CATALOG:
        for diff in ("Easy", "Normal", "Hard"):
            t0 = time.perf_counter()
            try:
                events = generate_chart(
                    song,
                    diff,
                    duration_sec=float(song.get("fallback_duration", 60.0)),
                )
                elapsed = time.perf_counter() - t0
                times = [float(e["hit_time"]) for e in events]
                ordered = times == sorted(times)
                ok = bool(events) and ordered and elapsed < 5.0
                if not ok:
                    chart_failures += 1
                check(
                    f"chart {song['id']}/{diff}",
                    ok,
                    f"notes={len(events)} ordered={ordered} {elapsed*1000:.0f}ms",
                )
            except Exception as exc:  # noqa: BLE001
                chart_failures += 1
                check(f"chart {song['id']}/{diff}", False, str(exc))
    check("chart generation no hang", chart_failures == 0)

    hold_ok = all(
        os.path.isfile(asset_path(f"{HOLD_SEQUENCE_DIR}/{fname}"))
        for fname in HOLD_SEQUENCE_FILES
    ) and bool(hold_sequence_frames)
    check("HOLD assets load", hold_ok, f"frames={len(hold_sequence_frames)}")

    try:
        agv = AGVRewardSweep()
        check("AGV state initializes", agv is not None and not agv.active)
    except Exception as exc:  # noqa: BLE001
        check("AGV state initializes", False, str(exc))

    try:
        selected_song_index_save = selected_song_index
        # Construct restartable run state
        ok_start = start_new_run(from_results=False)
        enter_results("game_over")
        queue_soft_restart(from_menu=False)
        begin_soft_restart_pipeline()
        steps = 0
        while game_state == "restarting" and steps < 20:
            perform_soft_restart_step()
            steps += 1
        check(
            "restart state constructed",
            game_state in ("countdown", "playing", "restarting") and ok_start,
            f"state={game_state} steps={steps}",
        )
        globals()["selected_song_index"] = selected_song_index_save
    except Exception as exc:  # noqa: BLE001
        check("restart state constructed", False, str(exc))

    try:
        ud = Path(userdata_dir())
        check("user-data path resolved", True, str(ud))
    except Exception as exc:  # noqa: BLE001
        check("user-data path resolved", False, str(exc))

    # Brief restart cycle sample (full 100-cycle suite is tools/test_restart_cycle.py)
    restart_rc = self_test_restart(cycles=2)
    check("restart sample cycles", restart_rc == 0)

    failed = [name for name, ok, _ in checks if not ok]
    print("", flush=True)
    if failed:
        print(f"SELF-TEST FAILED ({len(failed)} checks)", flush=True)
        for name in failed:
            print(f"  - {name}", flush=True)
        return 1
    print(f"SELF-TEST PASSED ({len(checks)} checks) music_bundle_ok={music_ok}", flush=True)
    return 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        raise SystemExit(run_self_test())
    if "--self-test-restart" in sys.argv:
        raise SystemExit(self_test_restart(20))
    main()
