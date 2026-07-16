"""
Deferred soft-restart pipeline for Werewolf Rhythm.

KEYDOWN only queues a flag. The main loop advances one restart step per frame:
RESULTS -> RESTARTING (steps) -> COUNTDOWN -> PLAYING
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Optional, TextIO

from paths import restart_log_path as _restart_log_path
from paths import userdata_dir as _userdata_dir


def userdata_dir(app_name: str = "WerewolfRhythmDemo") -> str:
    """Return user-data directory as str for backward compatibility."""
    return str(_userdata_dir(app_name if sys.platform == "win32" else None))


def restart_log_path(*, frozen: bool, project_root: str) -> str:
    return str(
        _restart_log_path(
            frozen=frozen,
            project_root=Path(project_root) if project_root else None,
        )
    )


class RestartLogger:
    def __init__(self, path: str, enabled: bool = True) -> None:
        self.path = path
        self.enabled = enabled
        self._fh: Optional[TextIO] = None
        if enabled:
            try:
                parent = os.path.dirname(path)
                if parent:
                    os.makedirs(parent, exist_ok=True)
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
