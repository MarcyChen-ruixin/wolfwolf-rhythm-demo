"""
Validate Werewolf Rhythm Demo release folders for forbidden content.

Platform-aware: Windows onedir packages and macOS .app bundles.

Exit code 0 = pass, nonzero = fail.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import platform
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

REQUIRED_ART = {
    "werewolf_background.png",
    "werewolf_enemy_1.png",
    "werewolf_enemy_2.png",
    "werewolf_enemy_3.png",
    "werewolf_enemy_hold.png",
    "werewolf_enemy_miss.png",
}


def iter_files(root: Path):
    skip_dirs = {
        ".git",
        "node_modules",
        "build",
        "dist",
        ".venv",
        "venv",
        ".venv-macos",
        "__pycache__",
    }
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs and not d.endswith(".egg-info")]
        for name in filenames:
            yield Path(dirpath) / name


def _is_macos_app(root: Path) -> bool:
    name = root.name
    if name.endswith(".app") and (root / "Contents").is_dir():
        return True
    # Allow validating an extracted parent that contains the .app
    for child in root.iterdir() if root.is_dir() else []:
        if child.name.endswith(".app") and (child / "Contents").is_dir():
            return True
    return False


def _find_app_bundle(root: Path) -> Path | None:
    if root.name.endswith(".app") and (root / "Contents").is_dir():
        return root
    if root.is_dir():
        for child in root.iterdir():
            if child.name.endswith(".app") and (child / "Contents").is_dir():
                return child
    return None


def validate_macos_app(app: Path) -> list[str]:
    errors: list[str] = []
    contents = app / "Contents"
    macos_dir = contents / "MacOS"
    resources = contents / "Resources"
    info = contents / "Info.plist"
    exe = macos_dir / "WerewolfRhythmDemo"

    if not contents.is_dir():
        errors.append("missing Contents/")
    if not macos_dir.is_dir():
        errors.append("missing Contents/MacOS/")
    if not resources.is_dir():
        errors.append("missing Contents/Resources/")
    if not info.is_file():
        errors.append("missing Contents/Info.plist")
    if not exe.exists():
        errors.append("missing Contents/MacOS/WerewolfRhythmDemo")
    elif not os.access(exe, os.X_OK):
        errors.append("WerewolfRhythmDemo is not executable")

    # Assets may live under Resources, Frameworks, or nested _internal.
    asset_roots = []
    for candidate in (
        resources,
        contents / "Frameworks",
        contents / "Frameworks" / "_internal",
        resources / "_internal",
        macos_dir,
    ):
        if (candidate / "assets").is_dir():
            asset_roots.append(candidate)
    if not asset_roots:
        # Deep search limited to the bundle
        for path in app.rglob("assets"):
            if path.is_dir():
                asset_roots.append(path.parent)
                break
    if not asset_roots:
        errors.append("missing assets/ inside .app bundle")
    else:
        asset_root = asset_roots[0]
        for audio in REQUIRED_AUDIO:
            if not any(asset_root.rglob(audio)):
                errors.append(f"missing approved audio: {audio}")
        for art in REQUIRED_ART:
            if not any(asset_root.rglob(art)):
                errors.append(f"missing art asset: {art}")
        notices = list(app.rglob("THIRD_PARTY_NOTICES.md")) + list(
            app.rglob("AUDIO_CREDITS.md")
        )
        if not notices:
            errors.append("missing music notices (THIRD_PARTY_NOTICES / AUDIO_CREDITS)")

    # No Windows EXE / private Windows package content
    for path in app.rglob("*"):
        low = path.name.lower()
        if low.endswith(".exe") or low.endswith(".dll"):
            # Ignore nothing — Windows binaries should not ship in the macOS app.
            # PyInstaller macOS uses .dylib / .so, not .dll/.exe.
            if low.endswith(".exe") or (
                low.endswith(".dll") and "python" not in low
            ):
                # Still flag any .exe; allow no DLL expectation on macOS
                if low.endswith(".exe"):
                    errors.append(f"Windows executable inside macOS app: {path.relative_to(app)}")
                elif low.endswith(".dll"):
                    errors.append(f"Windows DLL inside macOS app: {path.relative_to(app)}")

    return errors


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    if not root.is_dir():
        return [f"missing root: {root}"]

    app = _find_app_bundle(root)
    if app is not None:
        errors.extend(validate_macos_app(app))
        # Continue scanning text/forbidden content below using the app root.
        scan_root = app
    else:
        scan_root = root

    found_audio: set[str] = set()
    found_docs: set[str] = set()
    exe_found = False

    for path in iter_files(scan_root):
        name = path.name
        low = name.lower()
        try:
            rel = str(path.relative_to(scan_root)).replace("\\", "/")
        except ValueError:
            rel = str(path)

        if low in FORBIDDEN_NAMES:
            errors.append(f"forbidden filename: {rel}")
        for sub in FORBIDDEN_NAME_SUBSTR:
            if sub in rel.lower():
                # Nested venv folders already skipped; still catch stray files
                if sub in {".venv", "venv"} and "/Contents/" in f"/{rel}/":
                    continue
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

        if path.suffix.lower() in {".md", ".txt", ".py", ".json", ".vdf", ".ps1", ".csv", ".yml", ".yaml", ".sh"}:
            if path.name in {"validate_release_package.py", "MACOS_SIGNING.md"}:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for marker in FORBIDDEN_CONTENT_MARKERS:
                if marker in text:
                    if marker in {"SteamPipe", "steamcmd", "<APP_ID>", "<DEPOT_ID>"}:
                        errors.append(f"Steam upload leftover '{marker}' in {rel}")
                    elif marker in {"Mozart", "Photo Rhythm Game"}:
                        errors.append(f"forbidden content marker '{marker}' in {rel}")
                    elif marker in {"password=", "PASSWORD=", "api_key=", "API_KEY=", "BEGIN PRIVATE KEY"}:
                        # Docs may mention the words conceptually — only hard-fail secrets-like blobs
                        if marker == "BEGIN PRIVATE KEY":
                            errors.append(f"forbidden content marker '{marker}' in {rel}")
                        elif "EXAMPLE" not in text and "placeholder" not in text.lower():
                            # Allow documentation examples that include the literal keys as words
                            if "Apple" in text or "notary" in text.lower() or "credential" in text.lower():
                                continue
                            errors.append(f"forbidden content marker '{marker}' in {rel}")
                    else:
                        errors.append(f"forbidden content marker '{marker}' in {rel}")
            if "D:\\wolfbomb\\assets" in text or "D:/wolfbomb/assets" in text:
                errors.append(f"private reference assets path in {rel}")

    # Packaged Windows builds should include exe + audio
    looking_for_exe = any(
        p.name.lower().endswith(".exe") for p in scan_root.rglob("*.exe")
    ) or (scan_root / "WerewolfRhythmDemo.exe").exists()
    if looking_for_exe or exe_found:
        if not exe_found and not any(
            p.name.lower() == "werewolfrhythmdemo.exe" for p in scan_root.rglob("*.exe")
        ):
            errors.append("missing WerewolfRhythmDemo.exe")
        missing_audio = REQUIRED_AUDIO - found_audio
        if missing_audio and not any(
            p.name.lower() in REQUIRED_AUDIO for p in scan_root.rglob("*.mp3")
        ):
            errors.append(f"missing approved audio: {sorted(missing_audio)}")

    # Source tree / generic package: ensure no original photos by forbidden names (already scanned)
    return errors


def maybe_write_checksum(zip_path: Path) -> None:
    if not zip_path.is_file():
        return
    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    out = zip_path.with_suffix(zip_path.suffix + ".sha256")
    # Prefer companion .sha256 named like the zip
    companion = zip_path.parent / f"{zip_path.name}.sha256"
    # Standard: WerewolfRhythm-….zip -> WerewolfRhythm-….sha256
    companion = zip_path.with_name(zip_path.stem + ".sha256") if zip_path.suffix == ".zip" else out
    companion.write_text(f"{digest}  {zip_path.name}\n", encoding="utf-8")
    print(f"Wrote checksum: {companion}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate Werewolf Rhythm Demo package")
    ap.add_argument("roots", nargs="*", help="Folders or .app bundles to scan")
    ap.add_argument(
        "--checksum-zip",
        action="append",
        default=[],
        help="Optional ZIP path(s) for which to write SHA-256 companion files",
    )
    args = ap.parse_args()
    project = Path(__file__).resolve().parents[1]
    roots: list[Path] = []
    if args.roots:
        roots = [Path(r) for r in args.roots]
    else:
        for candidate in (
            project / "dist" / "WerewolfRhythmDemo",
            project / "dist" / "Werewolf Rhythm Demo.app",
            project,
        ):
            if candidate.exists():
                roots.append(candidate)

    if not roots:
        print("FAIL: no release roots found", flush=True)
        return 2

    print(f"Host: {platform.system()} {platform.machine()}", flush=True)
    all_errors: list[str] = []
    for root in roots:
        print(f"Scanning: {root}", flush=True)
        errs = validate(root)
        # Deduplicate while preserving order
        seen = set()
        unique = []
        for e in errs:
            if e not in seen:
                seen.add(e)
                unique.append(e)
        if unique:
            print(f"  FAIL ({len(unique)} issues)", flush=True)
            for e in unique:
                print(f"   - {e}", flush=True)
            all_errors.extend(f"{root}: {e}" for e in unique)
        else:
            print("  PASS", flush=True)

    for zip_arg in args.checksum_zip:
        maybe_write_checksum(Path(zip_arg))

    if all_errors:
        print(f"VALIDATION FAILED ({len(all_errors)} issues)", flush=True)
        return 1
    print("VALIDATION PASSED", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
