from __future__ import annotations

import base64
import io
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
SOURCE = ASSETS / "logo.b64"
OUT = ASSETS / "app_icon.ico"
PREVIEW = ASSETS / "logo_transparent.png"


def remove_white_background(image: Image.Image) -> Image.Image:
    image = image.convert("RGBA")
    px = image.load()
    width, height = image.size
    for y in range(height):
        for x in range(width):
            r, g, b, a = px[x, y]
            spread = max(r, g, b) - min(r, g, b)
            if r > 246 and g > 246 and b > 246 and spread < 6:
                px[x, y] = (255, 255, 255, 0)
    bbox = image.getchannel("A").getbbox()
    return image.crop(bbox) if bbox else image


def main() -> None:
    raw = base64.b64decode(SOURCE.read_text(encoding="utf-8").strip())
    logo = remove_white_background(Image.open(io.BytesIO(raw)))
    logo.save(PREVIEW, "PNG")

    canvas = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    icon_logo = logo.copy()
    icon_logo.thumbnail((228, 228), Image.Resampling.LANCZOS)
    x = (256 - icon_logo.width) // 2
    y = (256 - icon_logo.height) // 2
    canvas.alpha_composite(icon_logo, (x, y))

    canvas.save(
        OUT,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"Created transparent logo: {PREVIEW}")
    print(f"Created transparent Windows icon: {OUT}")


if __name__ == "__main__":
    main()
