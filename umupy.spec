# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_data_files

datas = [("UI/dist", "UI/dist"), ("Features", "Features")]
datas += collect_data_files("yt_dlp")
datas += collect_data_files("yt_dlp_ejs")
datas += collect_data_files("ytmusicapi")
datas += collect_data_files("pyrekordbox")

a = Analysis(
    ["app.py"],
    pathex=["Features"],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "yt_downloader",
        "fix_artwork",
        "spotify_converter",
        "rekordbox_playlist_creator",
        "sync_playlists",
        "history",
        "providers",
        "providers.base",
        "providers.ytdlp",
        "providers.youtube",
        "providers.spotify",
        "providers.soundcloud",
        "yt_dlp",
        "yt_dlp_ejs",
        "mutagen",
        "PIL",
        "spotipy",
        "ytmusicapi",
        "thefuzz",
        "pyrekordbox",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="UMUPY",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="UMUPY",
)

app = BUNDLE(
    coll,
    name="UMUPY.app",
    icon=None,
    bundle_identifier="com.urso.umupy",
    info_plist={
        "CFBundleName": "UMUPY",
        "CFBundleDisplayName": "UMUPY",
        "CFBundleShortVersionString": "0.1.0",
        "NSHighResolutionCapable": True,
    },
)
