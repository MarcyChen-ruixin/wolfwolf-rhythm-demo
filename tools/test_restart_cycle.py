"""100-cycle soft-restart state test (no interactive window required)."""

from __future__ import annotations

import os
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pygame

pygame.init()
try:
    pygame.mixer.init()
except pygame.error:
    pass

import rhythm_game as rg  # noqa: E402
from soft_restart import COUNTDOWN_SECONDS, STEP_DONE  # noqa: E402


def drive_soft_restart_to_playing(timeout: float = 2.0) -> float:
    """Queue + step pipeline until playing. Returns elapsed seconds."""
    t0 = time.perf_counter()
    rg.queue_soft_restart(from_menu=False)
    assert rg.restart_requested
    rg.begin_soft_restart_pipeline()
    assert rg.game_state == "restarting"

    while rg.game_state == "restarting":
        if time.perf_counter() - t0 > timeout:
            raise TimeoutError(f"stuck restarting step={rg.restart_step}")
        rg.perform_soft_restart_step()

    assert rg.game_state == "countdown"
    # Simulate countdown frames
    rg.countdown_timer = 0.0
    rg.finish_countdown_and_start_playing()
    assert rg.game_state == "playing"
    return time.perf_counter() - t0


def assert_clean_run() -> None:
    assert rg.run.score == 0
    assert rg.run.combo == 0
    assert rg.run.defeated_count == 0
    assert rg.run.escaped_count == 0
    assert rg.run.agv_cleared_count == 0
    assert rg.run.triggered_agv_milestones == set()
    assert len(rg.run.pending_agv_rewards) == 0
    assert not rg.run.game_over
    assert not rg.run.results_entered
    assert not rg.run.ending
    assert rg.run.gameplay_active
    assert len(rg.run.notes) > 0
    times = [n.hit_time for n in rg.run.notes]
    assert times == sorted(times)
    if rg.run.agv_reward is not None:
        assert not rg.run.agv_reward.active
        assert not any(
            getattr(n, "agv_reserved", False) for n in rg.run.notes
        )


def main() -> int:
    rg.selected_song_index = 0
    rg.selected_difficulty = "Easy"
    # Seed an initial run then enter results
    assert rg.start_new_run(from_results=False)
    rg.enter_results("game_over")
    assert rg.run.results_entered

    latencies = []
    for i in range(100):
        # Dirty state before restart
        rg.run.score = 99
        rg.run.escaped_count = 3
        rg.run.results_entered = True
        rg.game_state = "results"
        elapsed = drive_soft_restart_to_playing(timeout=2.0)
        latencies.append(elapsed)
        assert_clean_run()
        if elapsed > 2.0:
            print(f"FAIL cycle {i} elapsed={elapsed:.3f}s")
            return 1
        # Re-enter results for next cycle
        rg.enter_results("game_over")

    avg = sum(latencies) / len(latencies)
    mx = max(latencies)
    print(f"PASS 100 soft-restart cycles avg={avg*1000:.1f}ms max={mx*1000:.1f}ms")
    print(f"countdown_seconds={COUNTDOWN_SECONDS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
