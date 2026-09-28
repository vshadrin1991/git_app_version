"""Turn the app icon SVG into the .icns that macOS shows in Finder: make_icns.py <icon.svg> <out.icns>"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ICON_SIZES = (16, 32, 128, 256, 512)  # iconutil wants each of these at 1x and 2x


def render_iconset(svg: Path, iconset: Path) -> None:
    renderer = QSvgRenderer(str(svg))
    if not renderer.isValid():
        raise ValueError(f"{svg} is not a valid SVG")
    iconset.mkdir(parents=True, exist_ok=True)
    for size in ICON_SIZES:
        for suffix, pixels in (("", size), ("@2x", size * 2)):
            image = QImage(pixels, pixels, QImage.Format.Format_ARGB32)
            image.fill(Qt.GlobalColor.transparent)
            painter = QPainter(image)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            renderer.render(painter)
            painter.end()
            image.save(str(iconset / f"icon_{size}x{size}{suffix}.png"))


def main(svg: str, icns: str) -> None:
    app = QGuiApplication.instance() or QGuiApplication([])  # noqa: F841 - QPainter needs a Qt app
    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "AppIcon.iconset"
        render_iconset(Path(svg), iconset)
        Path(icns).parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", icns], check=True)


if __name__ == "__main__":
    main(*sys.argv[1:3])
