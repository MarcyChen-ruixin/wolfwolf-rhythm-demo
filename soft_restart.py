"""
Deferred soft-restart pipeline for Werewolf Rhythm.

KEYDOWN only queues a flag. The main loop advances one restart step per frame:
RESULTS -> RESTARTING (steps) -> COUNTDOWN -> PLAYING
"""

from __future__ import annotations

import os
import sys
import time
from typing import Callable, Optional, TextIO


def userdata_dir(app_name: str = "WerewolfRhythmDemo") -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    folder = os.path.join(base, app_name)
    os.makedirs(folder, exist_ok=True)
    return folder


def restart_log_path(*, frozen: bool, project_root: str) -> str:
    if frozen:
        return os.path.join(userdata_dir(), "restart_debug.log")
    log_dir = os.path.join(project_root, "logs")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "restart_debug.log")


class RestartLogger:
    def __init__(self, path: str, enabled: bool = True) -> None:
        self.path = path
        self.enabled = enabled
        self._fh: Optional[TextIO] = None
        if enabled:
            try:
                self._fh = open(path, "a", encoding="utf-8", buffering=1)
            except OSError:
                self._fh = None

    def log(self, message: str) -> None:
        if not self.enabled:
            return
        line = f"{time.strftime('%H:%M:%S')}.{int((time.time() % 1) * 1000):03d} {message}"
        try:
            if self._fh is not None:
                self._fh.write(line + "\n")
                self._fh.flush()
                try:
                    os.fsync(self._fh.fileno())
                except OSError:
                    pass
        except OSError:
            pass
        # Dev console only — never spam release UI
        if not getattr(sys, "frozen", False):
            try:
                print(line, flush=True)
            except OSError:
                pass

    def close(self) -> None:
        if self._fh is not None:
            try:
                self._fh.close()
            except OSError:
                pass
            self._fh = None


COUNTDOWN_SECONDS = 0.85
RESTART_WATCHDOG_SECONDS = 3.0

# Restart pipeline step ids
STEP_STOP_MUSIC = 0
STEP_CLEAR_NOTES = 1
STEP_CLEAR_AGV = 2
STEP_RESET_COUNTERS = 3
STEP_GENERATE_CHART = 4
STEP_PREPARE_AUDIO = 5
STEP_ENTER_COUNTDOWN = 6
STEP_DONE = 7
