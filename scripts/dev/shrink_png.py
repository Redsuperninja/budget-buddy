"""Make PNG pictures smaller: at most 256 colours, transparency kept, saved only if smaller.

    python3 scripts/dev/shrink_png.py <file or folder> [...]

On Windows, type py instead of python3. Needs Pillow, which the Home Base's developer setup
has, so run it with that Python (server/.venv). A folder means every .png directly inside it.
Screenshots of the dashboard come out about a third of their size and look the same; check
pictures with smooth gradients (like app icons) by eye before keeping the result.
"""

import argparse
import io
import sys
from pathlib import Path

ALREADY_FEW_COLOURS = {"1", "L", "LA", "P", "PA"}


def shrink(path: Path) -> tuple[int, int]:
    """Quantize the PNG at path in place; returns (size before, size after) in bytes.
    The file is left as it was unless the new one is smaller."""
    from PIL import Image  # here, so --help works without Pillow

    before = path.stat().st_size
    with Image.open(path) as image:
        image.load()
    if image.mode in ALREADY_FEW_COLOURS:
        return before, before
    if image.mode == "RGBA" or "transparency" in image.info:
        # Fast octree is the method that keeps the alpha channel.
        fewer = image.convert("RGBA").quantize(256, method=Image.Quantize.FASTOCTREE)
    else:
        fewer = image.convert("RGB").quantize(256, method=Image.Quantize.MEDIANCUT)
    out = io.BytesIO()
    fewer.save(out, "PNG", optimize=True)
    if out.tell() >= before:
        return before, before
    path.write_bytes(out.getvalue())
    return before, out.tell()


def pngs(targets: list[Path]) -> list[Path]:
    found = []
    for target in targets:
        found += sorted(target.glob("*.png")) if target.is_dir() else [target]
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Make PNG pictures smaller (256 colours).")
    parser.add_argument("paths", nargs="+", type=Path, help="PNG files or folders of them")
    args = parser.parse_args(argv)
    try:
        import PIL  # noqa: F401
    except ImportError:
        print("Needs Pillow: run this with the Home Base's Python (server/.venv).")
        return 1
    total_before = total_after = 0
    for path in pngs(args.paths):
        before, after = shrink(path)
        total_before, total_after = total_before + before, total_after + after
        print(f"{path.name}: {before // 1024} KB -> {after // 1024} KB")
    print(f"Total: {total_before // 1024} KB -> {total_after // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
