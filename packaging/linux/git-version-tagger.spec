# -*- mode: python ; coding: utf-8 -*-
# Build with: packaging/linux/build-deb.sh (on Ubuntu 22.04, so the binary runs on 22.04 and newer)
from pathlib import Path

root = Path(SPECPATH).parents[1]

a = Analysis(
    [str(root / "packaging" / "entry.py")],
    pathex=[str(root / "src")],
    datas=[(str(root / "src" / "git_version_tagger" / "resources"), "git_version_tagger/resources")],
    hiddenimports=["PySide6.QtDBus"],  # the tray icon talks to GNOME's AppIndicator over D-Bus
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="git-version-tagger", console=True)
coll = COLLECT(exe, a.binaries, a.datas, name="git-version-tagger")
