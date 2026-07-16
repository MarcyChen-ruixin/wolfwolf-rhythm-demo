"""
Recurring score-milestone AGV reward sweep (every 50 points).

Generic warehouse AGV drawn with Pygame primitives only — no external art.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set

import pygame

AGV_REWARD_INTERVAL = 50
AGV_SWEEP_DURATION_SECONDS = 4.0
AGV_REWARD_QUEUE_DELAY_SECONDS = 0.5
AGV_MESSAGE_DURATION_SECONDS = 1.5
AGV_CLEAR_FADE_SEC = 0.22

# Base design size (logical unit). Rendered at AGV_VISUAL_SCALE.
AGV_WIDTH = 72
AGV_HEIGHT = 40
AGV_VISUAL_SCALE = 5.0
AGV_RENDER_WIDTH = int(round(AGV_WIDTH * AGV_VISUAL_SCALE))
AGV_RENDER_HEIGHT = int(round(AGV_HEIGHT * AGV_VISUAL_SCALE))

AGV_RED = (205, 35, 35)
AGV_DARK_RED = (130, 20, 20)
AGV_BLACK = (25, 25, 25)
AGV_GRAY = (160, 160, 160)
AGV_WARNING = (255, 195, 40)
AGV_WHITE = (245, 245, 245)


def lane_center_x(lane: int, lane_w: int) -> float:
    return lane * lane_w + lane_w * 0.5


def crossed_milestones(
    previous_score: int,
    current_score: int,
    interval: int = AGV_REWARD_INTERVAL,
    already: Optional[Set[int]] = None,
) -> List[int]:
    if interval <= 0 or current_score <= previous_score:
        return []
    already = already or set()
    prev_m = max(0, int(previous_score) // interval)
    cur_m = max(0, int(current_score) // interval)
    hit: List[int] = []
    for m in range(prev_m + 1, cur_m + 1):
        threshold = m * interval
        if threshold <= 0:
            continue
        if threshold in already:
            continue
        hit.append(threshold)
    return hit


def select_lane_targets(
    notes: list,
    current_time: float,
    cols: int,
    hit_line_y: float,
    note_resolved_fn,
) -> Dict[int, object]:
    selected: Dict[int, object] = {}
    for lane in range(cols):
        best = None
        best_dist = 1e18
        for note in notes:
            if getattr(note, "col", -1) != lane:
                continue
            if note_resolved_fn(note):
                continue
            if getattr(note, "cleared_by_agv", False):
                continue
            if getattr(note, "agv_reserved", False):
                continue
            if getattr(note, "removed", False):
                continue
            if getattr(note, "is_long", False) and (
                getattr(note, "holding", False) or getattr(note, "hold_started", False)
            ):
                continue
            if not note.is_active(current_time):
                continue
            if note.is_long:
                dist = abs(note.get_rect(current_time).bottom - hit_line_y)
            else:
                dist = abs(note.get_rect(current_time).centery - hit_line_y)
            if dist < best_dist:
                best_dist = dist
                best = note
        if best is not None:
            selected[lane] = best
    return selected


class AGVRewardSweep:
    """Left-to-right warehouse AGV that clears up to one reserved enemy per lane."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.active = False
        self.finished = False
        self.threshold = 0
        self.x = 0.0
        self.y = 0.0
        self.start_x = 0.0
        self.end_x = 0.0
        self.speed = 100.0
        self.width = AGV_RENDER_WIDTH
        self.height = AGV_RENDER_HEIGHT
        self.scale = AGV_VISUAL_SCALE
        self.selected_targets: Dict[int, object] = {}
        self.cleared_lanes: Set[int] = set()
        self.message_timer = 0.0
        self.no_targets_timer = 0.0
        self.lane_w = 130
        self.cols = 4
        self.effects: List[dict] = []
        self._font: Optional[pygame.font.Font] = None
        self._prev_front_x = 0.0

    def shovel_front_x(self) -> float:
        """World X of the front shovel tip (scales with rendered width)."""
        tip = 10.0 * (self.width / float(AGV_WIDTH))
        return self.x + self.width + tip

    def start(
        self,
        threshold: int,
        targets: Dict[int, object],
        *,
        y: float,
        start_x: float,
        end_x: float,
        lane_w: int,
        cols: int,
        font: Optional[pygame.font.Font] = None,
        duration: float = AGV_SWEEP_DURATION_SECONDS,
        render_w: int = AGV_RENDER_WIDTH,
        render_h: int = AGV_RENDER_HEIGHT,
        scale: float = AGV_VISUAL_SCALE,
    ) -> None:
        self.reset()
        self.active = True
        self.finished = False
        self.threshold = int(threshold)
        self.selected_targets = dict(targets)
        self.width = int(render_w)
        self.height = int(render_h)
        self.scale = float(scale)
        self.start_x = float(start_x)
        self.end_x = float(end_x)
        self.x = self.start_x
        self.y = float(y)
        self.lane_w = int(lane_w)
        self.cols = int(cols)
        travel = max(1.0, self.end_x - self.start_x)
        dur = max(0.5, float(duration))
        self.speed = travel / dur
        self.message_timer = AGV_MESSAGE_DURATION_SECONDS
        self.no_targets_timer = 1.0 if not targets else 0.0
        self._font = font
        self._prev_front_x = self.shovel_front_x()
        for note in self.selected_targets.values():
            note.agv_reserved = True

    def clear_lane_target(self, lane_index: int) -> Optional[object]:
        if lane_index in self.cleared_lanes:
            return None
        note = self.selected_targets.get(lane_index)
        self.cleared_lanes.add(lane_index)
        if note is None:
            return None
        if getattr(note, "cleared_by_agv", False) or getattr(note, "removed", False):
            return None
        if note_already_gone(note):
            return None
        note.cleared_by_agv = True
        note.agv_reserved = True
        note.agv_fade = 0.0
        note.agv_slide_x = 0.0
        note.holding = False
        cx = lane_center_x(lane_index, self.lane_w)
        self.effects.append(
            {
                "x": cx,
                "y": self.y + self.height * 0.55,
                "life": AGV_CLEAR_FADE_SEC,
                "max_life": AGV_CLEAR_FADE_SEC,
            }
        )
        return note

    def update(self, dt: float) -> List[object]:
        newly_cleared: List[object] = []

        for note in list(self.selected_targets.values()):
            if note is None:
                continue
            if getattr(note, "cleared_by_agv", False) and not getattr(note, "removed", False):
                note.agv_fade = min(1.0, getattr(note, "agv_fade", 0.0) + dt / AGV_CLEAR_FADE_SEC)
                note.agv_slide_x = getattr(note, "agv_slide_x", 0.0) + 90.0 * dt
                if note.agv_fade >= 1.0:
                    note.removed = True
                    note.clicked = True
                    if note.is_long:
                        note.hold_completed = True

        for fx in self.effects:
            fx["life"] -= dt
        self.effects = [fx for fx in self.effects if fx["life"] > 0]

        if self.message_timer > 0:
            self.message_timer = max(0.0, self.message_timer - dt)
        if self.no_targets_timer > 0:
            self.no_targets_timer = max(0.0, self.no_targets_timer - dt)

        if not self.active:
            return newly_cleared

        self.x += self.speed * dt
        front = self.shovel_front_x()
        prev = self._prev_front_x

        for lane in range(self.cols):
            if lane in self.cleared_lanes:
                continue
            center = lane_center_x(lane, self.lane_w)
            # Crossing detection: prev < center <= current (handles large dt)
            if prev < center <= front:
                note = self.clear_lane_target(lane)
                if note is not None:
                    newly_cleared.append(note)

        self._prev_front_x = front

        if self.x >= self.end_x:
            before = set(self.cleared_lanes)
            self.finish()
            for lane, note in self.selected_targets.items():
                if (
                    note is not None
                    and lane not in before
                    and getattr(note, "cleared_by_agv", False)
                ):
                    newly_cleared.append(note)
        return newly_cleared

    def finish(self) -> None:
        self.active = False
        self.finished = True
        for lane, note in self.selected_targets.items():
            if lane not in self.cleared_lanes and note is not None:
                if not getattr(note, "cleared_by_agv", False) and not note_already_gone(note):
                    self.clear_lane_target(lane)

    def cancel(self) -> None:
        for note in self.selected_targets.values():
            if note is None:
                continue
            if getattr(note, "cleared_by_agv", False):
                note.removed = True
                note.clicked = True
                if getattr(note, "is_long", False):
                    note.hold_completed = True
            else:
                note.agv_reserved = False
        self.reset()

    def draw(self, surface: pygame.Surface) -> None:
        if self.message_timer > 0:
            self._draw_message(surface)
        if self.no_targets_timer > 0 and not self.selected_targets:
            self._draw_no_targets(surface)
        if self.active:
            self._draw_agv(surface)

        for fx in self.effects:
            t = fx["life"] / max(1e-6, fx["max_life"])
            r = int(12 + 28 * (1.0 - t) * (self.scale / 5.0))
            alpha = int(180 * t)
            blob = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(blob, (220, 220, 220, alpha), (r, r), r)
            pygame.draw.circle(blob, (255, 220, 80, alpha), (r, r), max(2, r // 2))
            surface.blit(blob, (int(fx["x"] - r), int(fx["y"] - r)))
            if self._font and t > 0.4:
                lab = self._font.render("CLEARED!", True, (255, 230, 80))
                surface.blit(lab, (int(fx["x"] - lab.get_width() // 2), int(fx["y"] - 28)))

    def _draw_message(self, surface: pygame.Surface) -> None:
        font = self._font or pygame.font.SysFont("arial", 26, bold=True)
        alpha = 255
        if self.message_timer < 0.35:
            alpha = int(255 * (self.message_timer / 0.35))
        title = font.render(f"AGV SWEEP — {self.threshold} POINTS!", True, (220, 40, 40))
        tmp = pygame.Surface(title.get_size(), pygame.SRCALPHA)
        tmp.blit(title, (0, 0))
        tmp.set_alpha(alpha)
        surface.blit(tmp, (surface.get_width() // 2 - title.get_width() // 2, 118))

    def _draw_no_targets(self, surface: pygame.Surface) -> None:
        font = self._font or pygame.font.SysFont("arial", 18, bold=True)
        lab = font.render("No targets", True, (80, 80, 90))
        surface.blit(lab, (surface.get_width() // 2 - lab.get_width() // 2, 150))

    def _draw_agv(self, surface: pygame.Surface) -> None:
        x, y = int(self.x), int(self.y)
        w, h = self.width, self.height
        s = w / float(AGV_WIDTH)

        def sc(v: float) -> int:
            return int(round(v * s))

        # Body
        pygame.draw.rect(
            surface, AGV_RED, (x + sc(8), y + sc(8), w - sc(16), h - sc(16)), border_radius=max(2, sc(4))
        )
        pygame.draw.rect(
            surface,
            AGV_DARK_RED,
            (x + sc(8), y + sc(8), w - sc(16), h - sc(16)),
            max(1, sc(2)),
            border_radius=max(2, sc(4)),
        )
        # Top panel
        pygame.draw.rect(
            surface, AGV_GRAY, (x + sc(14), y + sc(4), w - sc(34), sc(10)), border_radius=max(1, sc(2))
        )
        # Bumper
        pygame.draw.rect(
            surface,
            AGV_BLACK,
            (x + w - sc(14), y + sc(12), sc(10), h - sc(20)),
            border_radius=max(1, sc(2)),
        )
        # Front shovel / wedge
        shovel = [
            (x + w - sc(6), y + sc(10)),
            (x + w + sc(10), y + h // 2),
            (x + w - sc(6), y + h - sc(10)),
        ]
        pygame.draw.polygon(surface, AGV_DARK_RED, shovel)
        pygame.draw.polygon(surface, AGV_BLACK, shovel, max(1, sc(1)))
        # Wheels
        for wx in (x + sc(18), x + w - sc(28)):
            pygame.draw.ellipse(surface, AGV_BLACK, (wx, y + h - sc(12), sc(14), sc(12)))
            pygame.draw.ellipse(surface, (60, 60, 60), (wx + sc(3), y + h - sc(9), sc(8), sc(6)))
        # Warning light
        pygame.draw.circle(surface, AGV_WARNING, (x + sc(22), y + sc(6)), max(3, sc(5)))
        pygame.draw.circle(surface, (255, 240, 160), (x + sc(22), y + sc(6)), max(1, sc(2)))
        # Label
        label_size = max(12, sc(12))
        font = pygame.font.SysFont("arial", label_size, bold=True)
        label = font.render("AGV", True, AGV_WHITE)
        surface.blit(label, (x + w // 2 - label.get_width() // 2 - sc(4), y + h // 2 - label.get_height() // 2))


def note_already_gone(note: object) -> bool:
    if getattr(note, "removed", False):
        return True
    if getattr(note, "missed", False):
        return True
    if getattr(note, "clicked", False) and not getattr(note, "is_long", False):
        return True
    if getattr(note, "hold_completed", False):
        return True
    return False
