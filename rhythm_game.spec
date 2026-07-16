# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None
root = os.path.abspath(SPECPATH)

datas = [
    (os.path.join(root, "assets"), "assets"),
    (os.path.join(root, "ART_PROVENANCE.md"), "."),
    (os.path.join(root, "THIRD_PARTY_NOTICES.md"), "."),
    (os.path.join(root, "AUDIO_CREDITS.md"), "."),
    (os.path.join(root, "PRIVACY.md"), "."),
]

a = Analysis(
    [os.path.join(root, "rhythm_game.py")],
    pathex=[root],
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
