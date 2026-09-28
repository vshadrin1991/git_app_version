#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."

VERSION=$(python -c "import sys; sys.path.insert(0, 'src'); import git_version_tagger as m; print(m.__version__)")
ARCH=$(dpkg --print-architecture)
PKG="build/deb/git-version-tagger_${VERSION}_${ARCH}"

python -m PyInstaller --noconfirm --clean --distpath dist --workpath build packaging/linux/git-version-tagger.spec

rm -rf "$PKG"
mkdir -p "$PKG/DEBIAN" "$PKG/opt" "$PKG/usr/bin" "$PKG/usr/share/applications" \
  "$PKG/usr/share/icons/hicolor/scalable/apps"
cp -r dist/git-version-tagger "$PKG/opt/git-version-tagger"
ln -s /opt/git-version-tagger/git-version-tagger "$PKG/usr/bin/git-version-tagger"
cp packaging/linux/git-version-tagger.desktop "$PKG/usr/share/applications/"
cp src/git_version_tagger/resources/app-icon.svg "$PKG/usr/share/icons/hicolor/scalable/apps/git-version-tagger.svg"
sed -e "s/@VERSION@/${VERSION}/" -e "s/@ARCH@/${ARCH}/" packaging/linux/control.in > "$PKG/DEBIAN/control"
dpkg-deb --build --root-owner-group "$PKG" "dist/git-version-tagger_${VERSION}_${ARCH}.deb"
echo "Built dist/git-version-tagger_${VERSION}_${ARCH}.deb"
