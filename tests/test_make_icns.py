import importlib.util
from pathlib import Path

from PySide6.QtGui import QImage

ROOT = Path(__file__).resolve().parents[1]


def load_make_icns():
    spec = importlib.util.spec_from_file_location("make_icns", ROOT / "packaging" / "macos" / "make_icns.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_render_iconset_writes_every_size_macos_needs(qapp, tmp_path):
    iconset = tmp_path / "AppIcon.iconset"
    load_make_icns().render_iconset(ROOT / "src" / "git_version_tagger" / "resources" / "app-icon.svg", iconset)

    expected = {}
    for size in (16, 32, 128, 256, 512):
        expected[f"icon_{size}x{size}.png"] = size
        expected[f"icon_{size}x{size}@2x.png"] = size * 2
    assert sorted(path.name for path in iconset.iterdir()) == sorted(expected)
    for name, pixels in expected.items():
        image = QImage(str(iconset / name))
        assert (image.width(), image.height()) == (pixels, pixels)
