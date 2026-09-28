#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."

VERSION=$(python -c "import sys; sys.path.insert(0, 'src'); import git_version_tagger as m; print(m.__version__)")
ARCH=$(uname -m)

python packaging/macos/make_icns.py src/git_version_tagger/resources/app-icon.svg build/AppIcon.icns
python -m PyInstaller --noconfirm --clean --distpath dist --workpath build packaging/macos/GitVersionTagger.spec
codesign --force --deep --sign - dist/GitVersionTagger.app   # ad-hoc signature (no Apple Developer ID)
rm -f "dist/GitVersionTagger-${VERSION}-macos-${ARCH}.dmg"
hdiutil create -volname "Git Version Tagger" -srcfolder dist/GitVersionTagger.app -ov -format UDZO \
  "dist/GitVersionTagger-${VERSION}-macos-${ARCH}.dmg"
echo "Built dist/GitVersionTagger-${VERSION}-macos-${ARCH}.dmg"
