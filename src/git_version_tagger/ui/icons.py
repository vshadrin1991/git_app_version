from __future__ import annotations

import sys
from importlib.resources import files

from PySide6.QtGui import QIcon


def resource_path(name: str) -> str:
    return str(files("git_version_tagger") / "resources" / name)


def tray_icon() -> QIcon:
    if sys.platform == "darwin":
        icon = QIcon(resource_path("tray-icon.svg"))
        icon.setIsMask(True)  # template image: macOS recolors it for light and dark menu bars
        return icon
    return QIcon(resource_path("tray-icon-light.svg"))


def app_icon() -> QIcon:
    return QIcon(resource_path("app-icon.svg"))
