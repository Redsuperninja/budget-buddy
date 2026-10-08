"""Budget Buddy's icon, drawn in code so the repo needs no image files: a blue rounded square with a
white "B". Used for the tray and, saved as ``.ico``, for the ``.exe`` files."""

import sys

ACCENT = (31, 111, 235)  # the dashboard's light-mode accent, #1f6feb
SIZES = (16, 24, 32, 48, 64, 128, 256)


def make_icon(size: int = 256):
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=size // 5, fill=ACCENT)
    font = ImageFont.load_default(size=int(size * 0.7))
    draw.text((size / 2, size / 2), "B", fill="white", font=font, anchor="mm")
    return image


def save_ico(path) -> None:
    make_icon(256).save(path, format="ICO", sizes=[(s, s) for s in SIZES])


if __name__ == "__main__":  # python -m budget_buddy_desktop.icon <file.ico> (the build script)
    save_ico(sys.argv[1])
