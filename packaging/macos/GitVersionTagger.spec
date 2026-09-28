# -*- mode: python ; coding: utf-8 -*-
# Build with: packaging/macos/build.sh
import sys
from pathlib import Path

root = Path(SPECPATH).parents[1]
sys.path.insert(0, str(root / "src"))
from git_version_tagger import __version__  # noqa: E402

a = Analysis(
    [str(root / "packaging" / "entry.py")],
    pathex=[str(root / "src")],
    datas=[(str(root / "src" / "git_version_tagger" / "resources"), "git_version_tagger/resources")],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="GitVersionTagger", console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="GitVersionTagger")
app = BUNDLE(
    coll,
    name="GitVersionTagger.app",
    icon=str(root / "build" / "AppIcon.icns"),  # made by make_icns.py in build.sh
    bundle_identifier="com.vshadrin.git-version-tagger",
    version=__version__,
    info_plist={
        "CFBundleName": "Git Version Tagger",
        "CFBundleDisplayName": "Git Version Tagger",
        "LSUIElement": True,  # menu bar only: no Dock icon, no app menu
        "NSHighResolutionCapable": True,
    },
)
