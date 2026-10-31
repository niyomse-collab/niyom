"""Cross-platform exact Thai/Latin shaping without requiring Pillow RAQM.

Pillow on the Windows GitHub Actions runner has RAQM disabled, even when
Pillow is installed successfully. This fallback shapes the original Unicode
with HarfBuzz and rasterizes glyph indices with FreeType from the user's
*installed* font file. No font is guessed, synthesized or redistributed.
Absence of both libraries fails closed; DO NOT fall back to naive per-char
Pillow drawing, which misplaces Thai above/below vowels and tone marks.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image


def backend_available() -> bool:
    try:
        import uharfbuzz  # noqa: F401
        import freetype  # noqa: F401
        return True
    except (ImportError, OSError):
        return False


def render_shaped_line(text: str, font_path: str, size: int) -> Image.Image:
    """Return tightly cropped 8-bit coverage mask using actual shaped glyphs."""
    import freetype
    import uharfbuzz as hb

    path = Path(font_path)
    if not path.is_file() or size <= 0:
        raise ValueError("Installed font path and positive glyph size required")
    font_data = path.read_bytes()
    hb_face = hb.Face(font_data)
    hb_font = hb.Font(hb_face)
    hb_font.scale = (size * 64, size * 64)
    hb.ot_font_set_funcs(hb_font)
    buffer = hb.Buffer()
    buffer.add_str(text)
    buffer.guess_segment_properties()
    hb.shape(hb_font, buffer)
    ft_face = freetype.Face(str(path))
    ft_face.set_pixel_sizes(0, size)

    pen_x, pen_y = 0.0, 0.0
    glyphs = []
    for glyph, advance in zip(buffer.glyph_infos, buffer.glyph_positions):
        ft_face.load_glyph(glyph.codepoint, freetype.FT_LOAD_RENDER)
        slot = ft_face.glyph
        bitmap = slot.bitmap
        if bitmap.width and bitmap.rows:
            pitch = abs(bitmap.pitch)
            data = np.asarray(bitmap.buffer, dtype=np.uint8)
            pixels = data.reshape((bitmap.rows, pitch))[:, :bitmap.width].copy()
            if bitmap.pitch < 0:
                pixels = pixels[::-1]
            left = round(pen_x + advance.x_offset / 64.0 + slot.bitmap_left)
            # FreeType y-axis grows upward, Pillow mask y-axis down.
            top = round(-pen_y - advance.y_offset / 64.0 - slot.bitmap_top)
            glyphs.append((left, top, pixels))
        pen_x += advance.x_advance / 64.0
        pen_y += advance.y_advance / 64.0
    if not glyphs:
        return Image.new("L", (1, 1), 0)
    left = min(x for x, y, b in glyphs)
    top = min(y for x, y, b in glyphs)
    right = max(x + b.shape[1] for x, y, b in glyphs)
    bottom = max(y + b.shape[0] for x, y, b in glyphs)
    mask = np.zeros((bottom-top, right-left), dtype=np.uint8)
    for x, y, bitmap in glyphs:
        py, px = y-top, x-left
        slot = mask[py:py+bitmap.shape[0], px:px+bitmap.shape[1]]
        # Overlapping combining marks keep maximum true coverage, not a
        # fabricated bright pixel from naive uint8 addition.
        np.maximum(slot, bitmap, out=slot)
    return Image.fromarray(mask, "L")


def rasterize_shaped_text(text: str, font_path: str, size: int) -> Image.Image:
    """Multi-line Thai-safe HarfBuzz shaping, returns grayscale tight mask."""
    import freetype

    face = freetype.Face(str(font_path))
    face.set_pixel_sizes(0, size)
    line_advance = max(size, round(face.size.height / 64.0)) + size // 4
    lines = [render_shaped_line(line, font_path, size)
             for line in text.split("\n")]
    width = max(line.width for line in lines)
    height = (len(lines)-1)*line_advance + max(
        i*line_advance + line.height - (len(lines)-1)*line_advance
        for i, line in enumerate(lines)
    )
    out = Image.new("L", (max(1, width), max(1, height)), 0)
    for i, line in enumerate(lines):
        out.paste(line, (0, i*line_advance))
    return out
