"""Automated checks for recurring 50-point AGV rewards + queue."""

from __future__ import annotations

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from agv_reward import (  # noqa: E402
    AGV_REWARD_INTERVAL,
    AGV_RENDER_HEIGHT,
    AGV_RENDER_WIDTH,
    AGV_SWEEP_DURATION_SECONDS,
    AGVRewardSweep,
    crossed_milestones,
)


def test_milestone_math():
    assert crossed_milestones(0, 49) == []
    assert crossed_milestones(49, 50) == [50]
    assert crossed_milestones(50, 99) == []
    assert crossed_milestones(99, 100) == [100]
    assert crossed_milestones(148, 152) == [150]
    assert crossed_milestones(145, 205) == [150, 200]
    assert crossed_milestones(48, 53) == [50]
    assert crossed_milestones(95, 105) == [100]
    assert crossed_milestones(200, 205, already={150, 200}) == []


def test_sweep_duration_speed():
    agv = AGVRewardSweep()
    start_x = float(-AGV_RENDER_WIDTH - 24)
    end_x = 540.0
    agv.start(50, {}, y=462, start_x=start_x, end_x=end_x, lane_w=130, cols=4)
    travel = end_x - start_x
    expected = travel / AGV_SWEEP_DURATION_SECONDS
    assert abs(agv.speed - expected) < 0.01
    assert agv.width == AGV_RENDER_WIDTH
    assert agv.height == AGV_RENDER_HEIGHT
    # Simulate full travel time
    t = 0.0
    while agv.active and t < 6.0:
        agv.update(0.05)
        t += 0.05
    assert not agv.active
    assert 3.5 <= t <= 4.6


def main() -> int:
    failed = 0
    for fn in (test_milestone_math, test_sweep_duration_speed):
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception as exc:
            failed += 1
            print(f"FAIL {fn.__name__}: {exc}")

    import pygame

    pygame.init()
    try:
        pygame.mixer.init()
    except pygame.error:
        pass
    import rhythm_game as rg

    # 0 -> 49: none
    rg.reset_game()
    rg.add_score_points(49)
    assert not rg.run.pending_agv_rewards and not rg.run.agv_reward.active
    print("PASS 0_to_49")

    # 49 -> 50
    rg.add_score_points(1)
    assert 50 in rg.run.triggered_agv_milestones
    assert rg.run.agv_reward.active and rg.run.agv_reward.threshold == 50
    print("PASS 49_to_50")

    # Stay below 100: no second while first active; enqueue at 100
    rg.add_score_points(49)  # score 99
    assert list(rg.run.pending_agv_rewards) == []
    rg.add_score_points(1)  # 100
    assert 100 in rg.run.triggered_agv_milestones
    assert 100 in rg.run.pending_agv_rewards or (
        rg.run.agv_reward.active and rg.run.agv_reward.threshold == 50
    )
    print("PASS queue_100_while_50_active")

    # Jump 145 -> 205 queues 150 and 200
    rg.reset_game()
    rg.add_score_points(145)
    assert 50 in rg.run.triggered_agv_milestones and 100 in rg.run.triggered_agv_milestones
    # finish / clear active then jump
    rg.run.agv_reward.cancel()
    rg.run.pending_agv_rewards.clear()
    rg.run.agv_queue_delay = 0
    # re-add jump from 145
    prev = rg.run.score
    assert prev == 145
    rg.add_score_points(60)  # 205
    assert list(rg.run.pending_agv_rewards) + (
        [rg.run.agv_reward.threshold] if rg.run.agv_reward.active else []
    )
    milestones = set(rg.run.pending_agv_rewards)
    if rg.run.agv_reward.active:
        milestones.add(rg.run.agv_reward.threshold)
    assert 150 in milestones and 200 in milestones
    print("PASS jump_145_to_205")

    # No recursion from AGV clear
    s0 = rg.run.score
    rg.run.register_agv_clear()
    assert rg.run.score == s0
    print("PASS no_score_from_agv_clear")

    # Restart clears
    rg.reset_game()
    assert rg.run.triggered_agv_milestones == set()
    assert len(rg.run.pending_agv_rewards) == 0
    assert not rg.run.agv_reward.active
    rg.add_score_points(50)
    assert rg.run.agv_reward.active
    print("PASS restart_allows_50_again")

    # Results cancel queue
    rg.add_score_points(100)  # push more milestones
    rg.enter_results("game_over")
    assert len(rg.run.pending_agv_rewards) == 0
    assert not rg.run.agv_reward.active
    print("PASS results_clear_queue")

    print("ALL AGV MILESTONE TESTS PASSED" if failed == 0 else f"{failed} FAILED")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
