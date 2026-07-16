# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller macOS application bundle for Werewolf Rhythm Demo."""

import os
from pathlib import Path

block_cipher = None
root = Path(SPECPATH).resolve().parent
packaging = Path(SPECPATH).resolve()

datas = [
    (str(root / "assets"), "assets"),
    (str(root / "ART_PROVENANCE.md"), "."),
    (str(root / "THIRD_PARTY_NOTICES.md"), "."),
    (str(root / "AUDIO_CREDITS.md"), "."),
    (str(root / "PRIVACY.md"), "."),
    (str(root / "README_MAC_FIRST.txt"), "."),
]

icon_path = packaging / "WerewolfRhythmDemo.icns"
bundle_icon = str(icon_path) if icon_path.is_file() else None

a = Analysis(
    [str(root / "rhythm_game.py")],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=["soft_restart", "chart_gen", "agv_reward", "config", "paths"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "librosa"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="WerewolfRhythmDemo",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="WerewolfRhythmDemo",
)

bundle_kwargs = {
    "name": "Werewolf Rhythm Demo.app",
    "bundle_identifier": "com.ruixinchen.werewolfrhythmdemo",
    "info_plist": {
        "CFBundleName": "Werewolf Rhythm Demo",
        "CFBundleDisplayName": "Werewolf Rhythm Demo",
        "CFBundleIdentifier": "com.ruixinchen.werewolfrhythmdemo",
        "CFBundleExecutable": "WerewolfRhythmDemo",
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": "0.1.0-demo",
        "CFBundleVersion": "0.1.0",
        "NSPrincipalClass": "NSApplication",
        "NSHighResolutionCapable": True,
        # No microphone, camera, location, contacts, network, or accessibility usage.
    },
}
if bundle_icon:
    bundle_kwargs["icon"] = bundle_icon

app = BUNDLE(coll, **bundle_kwargs)
