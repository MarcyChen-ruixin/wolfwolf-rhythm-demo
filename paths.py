"""
Centralized resource and user-data paths for Werewolf Rhythm Demo.

Works for:
- normal Python execution
- Windows PyInstaller onedir
- macOS PyInstaller .app
- GitHub Actions macOS builds
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

# Display name used in the macOS Application Support folder.
MACOS_APP_SUPPORT_NAME = "Werewolf Rhythm Demo"
# Folder name under %LOCALAPPDATA% on Windows.
WINDOWS_APPDATA_NAME = "WerewolfRhythmDemo"

_userdata_ok = True


def resource_root() -> Path:
    """Directory that contains the `assets` folder (and bundled notices)."""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidate = Path(meipass)
            if (candidate / "assets").is_dir():
                return candidate

        exe = Path(sys.executable).resolve()
        search = [
            exe.parent,
            exe.parent / "_internal",
            # Contents/MacOS -> Contents/Resources | Contents/Frameworks
            exe.parent.parent / "Resources",
            exe.parent.parent / "Frameworks",
            exe.parent.parent / "Frameworks" / "_internal",
        ]
        if meipass:
            search.insert(0, Path(meipass))
        for path in search:
            if (path / "assets").is_dir():
                return path
        return Path(meipass) if meipass else exe.parent

    return Path(__file__).resolve().parent


def resource_path(relative_path: str) -> Path:
    """
    Resolve a path relative to the application/resource root.

    Do not assume the process cwd is the application directory.
    """
    if getattr(sys, "frozen", False):
        bundle_root = Path(getattr(sys, "_MEIPASS", resource_root()))
        # Prefer the root that actually contains assets when _MEIPASS differs.
        if not (bundle_root / "assets").is_dir():
            bundle_root = resource_root()
    else:
        bundle_root = Path(__file__).resolve().parent
    rel = Path(relative_path.replace("\\", "/"))
    return bundle_root / rel


def userdata_dir(app_name: Optional[str] = None) -> Path:
    """
    User-writable directory for settings / local high score.

    Windows: %LOCALAPPDATA%\\WerewolfRhythmDemo\\
    macOS:   ~/Library/Application Support/Werewolf Rhythm Demo/
    Other:   ~/.local/share/WerewolfRhythmDemo/

    If the directory cannot be created, returns a path and marks userdata
    unavailable; callers must not crash and should keep in-memory defaults.
    """
    global _userdata_ok
    try:
        if sys.platform == "darwin":
            folder = (
                Path.home()
                / "Library"
                / "Application Support"
                / MACOS_APP_SUPPORT_NAME
            )
        elif sys.platform == "win32":
            base = os.environ.get("LOCALAPPDATA")
            if base:
                folder = Path(base) / (app_name or WINDOWS_APPDATA_NAME)
            else:
                folder = (
                    Path.home()
                    / "AppData"
                    / "Local"
                    / (app_name or WINDOWS_APPDATA_NAME)
                )
        else:
            folder = (
                Path.home()
                / ".local"
                / "share"
                / (app_name or WINDOWS_APPDATA_NAME)
            )
        folder.mkdir(parents=True, exist_ok=True)
        _userdata_ok = True
        return folder
    except OSError:
        _userdata_ok = False
        # Best-effort fallback path; writes should still be guarded by callers.
        return Path.home() / f".{WINDOWS_APPDATA_NAME}"


def userdata_available() -> bool:
    return _userdata_ok


def settings_path() -> Path:
    return userdata_dir() / "settings.json"


def restart_log_path(*, frozen: bool, project_root: Optional[Path] = None) -> Path:
    if frozen:
        return userdata_dir() / "restart_debug.log"
    root = project_root or resource_root()
    log_dir = Path(root) / "logs"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return userdata_dir() / "restart_debug.log"
    return log_dir / "restart_debug.log"
