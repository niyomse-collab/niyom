from __future__ import annotations

import base64
import io
from pathlib import Path

from PIL import Image, ImageChops

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

    # Keep the user's logo unchanged and center it on a clean square icon canvas.
    canvas = Image.new("RGBA", (256, 256), (255, 255, 255, 255))
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
