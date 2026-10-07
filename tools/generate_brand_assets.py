from __future__ import annotations

import base64
import io
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
SOURCE = ASSETS / "logo.b64"
OUT = ASSETS / "app_icon.ico"


def main() -> None:
    raw = base64.b64decode(SOURCE.read_text(encoding="utf-8").strip())
    image = Image.open(io.BytesIO(raw)).convert("RGBA")

    # Remove only empty white margins; the logo artwork itself is preserved.
    white = Image.new("RGB", image.size, "white")
    diff = ImageChops.difference(image.convert("RGB"), white).convert("L")
    bbox = diff.point(lambda value: 255 if value > 12 else 0).getbbox()
    if bbox:
        image = image.crop(bbox)

    # Remove only white background connected to the outer image edges.
    # Internal white artwork in the user's logo is preserved.
    rgb = image.convert("RGB")
    mask = Image.new("L", image.size, 0)
    src = rgb.load()
    mp = mask.load()
    for y in range(image.height):
        for x in range(image.width):
            r, g, b = src[x, y]
            if min(r, g, b) >= 238 and max(r, g, b) - min(r, g, b) <= 18:
                mp[x, y] = 255

    for seed in ((0, 0), (image.width - 1, 0), (0, image.height - 1), (image.width - 1, image.height - 1)):
        try:
            if mask.getpixel(seed) == 255:
                ImageDraw.floodfill(mask, seed, 128, thresh=0)
        except Exception:
            pass

    bg = mask.point(lambda v: 255 if v == 128 else 0)
    bg = bg.filter(ImageFilter.GaussianBlur(0.7))
    alpha = ImageChops.subtract(image.getchannel("A"), bg)
    image.putalpha(alpha)

    bbox = image.getchannel("A").getbbox()
    if bbox:
        image = image.crop(bbox)

    canvas = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    image.thumbnail((224, 224), Image.Resampling.LANCZOS)
    x = (256 - image.width) // 2
    y = (256 - image.height) // 2
    canvas.alpha_composite(image, (x, y))

    canvas.save(
        OUT,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"Created brand icon: {OUT}")


if __name__ == "__main__":
    main()
