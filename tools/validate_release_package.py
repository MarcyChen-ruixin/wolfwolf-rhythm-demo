"""
Validate Werewolf Rhythm Demo release folders for forbidden content.

Exit code 0 = pass, nonzero = fail.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

FORBIDDEN_NAMES = {
    "background.jpg",
    "photo1.png",
    "photo2.png",
    "photo3.png",
    "music1.mp3",
    "music2.mp3",
    "music3.mp3",
    ".env",
    "steam_appid.txt",
}

FORBIDDEN_NAME_SUBSTR = (
    "__pycache__",
    ".pyc",
    ".venv",
    "venv",
)

FORBIDDEN_CONTENT_MARKERS = (
    "BEGIN PRIVATE KEY",
    "api_key=",
    "API_KEY=",
    "password=",
    "PASSWORD=",
    "Mozart",
    "Photo Rhythm Game",
    "<APP_ID>",
    "<DEPOT_ID>",
    "SteamPipe",
    "steamcmd",
)

REQUIRED_AUDIO = {
    "monkeys-spinning-monkeys.mp3",
    "fluffing-a-duck.mp3",
    "sneaky-snitch.mp3",
}

REQUIRED_DOCS = {
    "THIRD_PARTY_NOTICES.md",
    "PRIVACY.md",
}


def iter_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d
            for d in dirnames
            if d not in {".git", "node_modules", "build", "dist", ".venv", "venv"}
        ]
        for name in filenames:
            yield Path(dirpath) / name


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    if not root.is_dir():
        return [f"missing root: {root}"]

    found_audio: set[str] = set()
    found_docs: set[str] = set()
    exe_found = False

    for path in iter_files(root):
        name = path.name
        low = name.lower()
        rel = str(path.relative_to(root)).replace("\\", "/")

        if low in FORBIDDEN_NAMES:
            errors.append(f"forbidden filename: {rel}")
        for sub in FORBIDDEN_NAME_SUBSTR:
            if sub in rel.lower():
                errors.append(f"forbidden path component: {rel}")
                break

        if low in {"werewolfrhythmdemo.exe", "werewolfrhythm.exe"}:
            exe_found = True
        if low in REQUIRED_AUDIO:
            found_audio.add(low)
        if name in REQUIRED_DOCS or name == "THIRD_PARTY_NOTICES.txt":
            found_docs.add(
                "THIRD_PARTY_NOTICES.md"
                if name.startswith("THIRD_PARTY_NOTICES")
                else name
            )

        if path.suffix.lower() in {".md", ".txt", ".py", ".json", ".vdf", ".ps1", ".csv"}:
            # Do not false-positive on this validator's own forbidden-marker list
            if path.name == "validate_release_package.py":
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for marker in FORBIDDEN_CONTENT_MARKERS:
                if marker in text:
                    # Allow mentioning Steam only as "not affiliated" in notices
                    if marker in {"SteamPipe", "steamcmd", "<APP_ID>", "<DEPOT_ID>"}:
                        errors.append(f"Steam upload leftover '{marker}' in {rel}")
                    elif marker == "Mozart":
                        errors.append(f"forbidden content marker '{marker}' in {rel}")
                    elif marker == "Photo Rhythm Game":
                        errors.append(f"forbidden content marker '{marker}' in {rel}")
                    else:
                        errors.append(f"forbidden content marker '{marker}' in {rel}")
            if "D:\\wolfbomb\\assets" in text or "D:/wolfbomb/assets" in text:
                errors.append(f"private reference assets path in {rel}")

    # Packaged builds / ZIPs extracted should include exe + audio
    looking_for_exe = any(
        p.name.lower().endswith(".exe") for p in root.rglob("*.exe")
    ) or (root / "WerewolfRhythmDemo.exe").exists()
    if looking_for_exe or exe_found:
        if not exe_found and not any(
            p.name.lower() == "werewolfrhythmdemo.exe" for p in root.rglob("*.exe")
        ):
            errors.append("missing WerewolfRhythmDemo.exe")
        missing_audio = REQUIRED_AUDIO - found_audio
        if missing_audio and not any(
            p.name.lower() in REQUIRED_AUDIO for p in root.rglob("*.mp3")
        ):
            errors.append(f"missing approved audio: {sorted(missing_audio)}")

    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate Werewolf Rhythm Demo package")
    ap.add_argument("roots", nargs="*", help="Folders to scan")
    args = ap.parse_args()
    project = Path(__file__).resolve().parents[1]
    roots: list[Path] = []
    if args.roots:
        roots = [Path(r) for r in args.roots]
    else:
        for candidate in (
            project / "dist" / "WerewolfRhythmDemo",
            Path(r"D:\wolfbomb\github_demo_release\repository"),
            Path(r"D:\wolfbomb\github_demo_release\release_assets"),
        ):
            if candidate.is_dir():
                roots.append(candidate)

    if not roots:
        print("FAIL: no release roots found", flush=True)
        return 2

    all_errors: list[str] = []
    for root in roots:
        print(f"Scanning: {root}", flush=True)
        errs = validate(root)
        if errs:
            print(f"  FAIL ({len(errs)} issues)", flush=True)
            for e in errs:
                print(f"   - {e}", flush=True)
            all_errors.extend(f"{root}: {e}" for e in errs)
        else:
            print("  PASS", flush=True)

    if all_errors:
        print(f"VALIDATION FAILED ({len(all_errors)} issues)", flush=True)
        return 1
    print("VALIDATION PASSED", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
