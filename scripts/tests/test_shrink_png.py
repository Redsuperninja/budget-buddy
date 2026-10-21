"""shrink_png: fewer colours, transparency kept, and never a bigger file."""

import random
import sys
from pathlib import Path

import pytest

Image = pytest.importorskip("PIL.Image")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dev"))

import shrink_png  # noqa: E402


def noisy(mode: str, size: int = 64) -> "Image.Image":
    """A picture with thousands of colours, so 256 colours make it smaller."""
    rand = random.Random(0)
    image = Image.new(mode, (size, size))
    image.putdata(
        [
            (rand.randrange(256), rand.randrange(256), rand.randrange(256), 0 if x < 8 else 255)[
                : len(mode)
            ]
            for y in range(size)
            for x in range(size)
        ]
    )
    return image


def test_a_screenshot_gets_smaller_and_looks_the_same(tmp_path):
    path = tmp_path / "page.png"
    noisy("RGB").save(path)
    before, after = shrink_png.shrink(path)
    assert after < before
    assert path.stat().st_size == after
    with Image.open(path) as shrunk:
        assert len(shrunk.convert("RGB").getcolors(256 * 256)) <= 256
        assert shrunk.size == (64, 64)


def test_transparency_is_kept(tmp_path):
    path = tmp_path / "icon.png"
    noisy("RGBA").save(path)
    shrink_png.shrink(path)
    with Image.open(path) as shrunk:
        rgba = shrunk.convert("RGBA")
    assert rgba.getpixel((0, 10))[3] == 0  # the clear strip on the left stays clear
    assert rgba.getpixel((40, 10))[3] == 255


def test_a_file_that_would_grow_is_left_alone(tmp_path):
    path = tmp_path / "flat.png"
    Image.new("RGB", (16, 16), (10, 120, 60)).save(path, optimize=True)
    original = path.read_bytes()
    before, after = shrink_png.shrink(path)
    assert before == after
    assert path.read_bytes() == original


def test_the_command_shrinks_every_png_in_a_folder(tmp_path, capsys):
    for name in "a.png", "b.png":
        noisy("RGB").save(tmp_path / name)
    sizes = {p.name: p.stat().st_size for p in tmp_path.iterdir()}
    assert shrink_png.main([str(tmp_path)]) == 0
    assert all((tmp_path / name).stat().st_size < size for name, size in sizes.items())
    assert "Total:" in capsys.readouterr().out
