from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

from git_version_tagger.ui.icons import app_icon, resource_path, tray_icon

ICON_FILES = ("tray-icon.svg", "tray-icon-light.svg", "tray-icon-busy.svg", "tray-icon-light-busy.svg", "app-icon.svg")


def test_resources_are_packaged():
    for name in ICON_FILES:
        assert Path(resource_path(name)).is_file()


@pytest.mark.parametrize("name", ICON_FILES)
def test_svg_draws_something(qapp, name):
    renderer = QSvgRenderer(resource_path(name))
    assert renderer.isValid()
    image = QImage(64, 64, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    assert any(image.pixelColor(x, y).alpha() for x in range(64) for y in range(64))


def test_tray_icon_renders(qapp):
    assert not tray_icon().pixmap(22, 22).isNull()


def test_app_icon_renders(qapp):
    assert not app_icon().pixmap(64, 64).isNull()


def test_busy_tray_icon_renders(qapp):
    assert not tray_icon(busy=True).pixmap(22, 22).isNull()
