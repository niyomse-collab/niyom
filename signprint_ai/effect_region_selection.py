"""Interactive, source-normalized ROI selection for protecting styled sign effects.

The selector only marks pixels to copy from the accepted V2 raster. It never
reads text, reconstructs glyphs, or edits the source image.
"""
from __future__ import annotations

import math


def normalized_drag_rectangle(start, end, canvas_size, *, min_edge=3):
    """Convert a drag on a fitted preview into a normalized (x1,y1,x2,y2) ROI.

    Coordinates are clamped to the displayed image. A tiny/zero-area drag is
    ignored so accidental clicks cannot create an almost invisible mask.
    """
    if not isinstance(canvas_size, (tuple, list)) or len(canvas_size) != 2:
        raise ValueError("canvas size must contain width and height")
    width, height = canvas_size
    if (isinstance(width, bool) or isinstance(height, bool)
            or not isinstance(width, int) or not isinstance(height, int)
            or width <= 0 or height <= 0):
        raise ValueError("canvas dimensions must be positive integers")
    if (not isinstance(start, (tuple, list)) or len(start) != 2
            or not isinstance(end, (tuple, list)) or len(end) != 2):
        raise ValueError("drag endpoints must contain x and y")
    points = []
    for value in (*start, *end):
        if isinstance(value, bool):
            raise ValueError("drag coordinates must be finite numbers")
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("drag coordinates must be finite numbers") from exc
        if not math.isfinite(number):
            raise ValueError("drag coordinates must be finite numbers")
        points.append(number)
    x0, y0, x1, y1 = points
    left = max(0.0, min(float(width), min(x0, x1)))
    top = max(0.0, min(float(height), min(y0, y1)))
    right = max(0.0, min(float(width), max(x0, x1)))
    bottom = max(0.0, min(float(height), max(y0, y1)))
    if right - left < max(1, int(min_edge)) or bottom - top < max(1, int(min_edge)):
        return None
    return (
        round(left / width, 8),
        round(top / height, 8),
        round(right / width, 8),
        round(bottom / height, 8),
    )


def _validated_regions(regions):
    if not isinstance(regions, (tuple, list)):
        raise ValueError("effect regions must be a list of normalized rectangles")
    result = []
    for region in regions:
        if not isinstance(region, (tuple, list)) or len(region) != 4:
            raise ValueError("each effect region must contain four coordinates")
        values = []
        for value in region:
            if isinstance(value, bool):
                raise ValueError("effect region coordinates must be numeric")
            try:
                number = float(value)
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError("effect region coordinates must be numeric") from exc
            if not math.isfinite(number) or not 0.0 <= number <= 1.0:
                raise ValueError("effect region coordinates must be finite and within 0..1")
            values.append(number)
        x1, y1, x2, y2 = values
        if x1 >= x2 or y1 >= y2:
            raise ValueError("effect region must have positive width and height")
        result.append(tuple(values))
    return result


def select_effect_regions(parent, preview_image, original_size, existing_regions=()):
    """Show a modal fitted-image selector; return ROIs or None when cancelled.

    Multiple rectangles may be added. The result is normalized to the full,
    EXIF-oriented source image so the processing adapter can map it through
    the same Fit/Stretch transform as the accepted V2 raster.
    """
    import tkinter as tk
    from tkinter import ttk
    from PIL import Image, ImageTk

    regions = _validated_regions(existing_regions)
    if (not isinstance(original_size, (tuple, list)) or len(original_size) != 2
            or any(isinstance(v, bool) or not isinstance(v, int) or v <= 0
                   for v in original_size)):
        raise ValueError("original image size is invalid")
    if not isinstance(preview_image, Image.Image):
        raise ValueError("effect selector requires a Pillow preview image")

    screen_w = max(420, int(parent.winfo_screenwidth()) - 100)
    screen_h = max(320, int(parent.winfo_screenheight()) - 210)
    display = preview_image.copy()
    display.thumbnail((min(1100, screen_w), min(720, screen_h)), Image.Resampling.LANCZOS)
    width, height = display.size
    if width < 1 or height < 1:
        raise ValueError("effect selector preview is empty")

    dialog = tk.Toplevel(parent)
    dialog.title("ปกป้องข้อความและเอฟเฟกต์จากการปรับภาพ AI")
    dialog.transient(parent.winfo_toplevel())
    dialog.resizable(False, False)
    result = {"value": None}

    heading = tk.Label(
        dialog,
        text=("ลากกรอบครอบข้อความ/โลโก้ที่มี Gradient, Stroke, Glow, Shadow หรือกรอบตกแต่ง\n"
              "พื้นที่ที่เลือกจะคงพิกเซลจาก V2 เดิมทุกพิกเซล • ไม่ใช้ OCR และไม่เขียนข้อความใหม่"),
        justify="left",
        anchor="w",
        padx=10,
        pady=8,
    )
    heading.pack(fill="x")

    canvas = tk.Canvas(dialog, width=width, height=height, bg="#171717",
                       highlightthickness=1, highlightbackground="#58636E",
                       cursor="crosshair")
    photo = ImageTk.PhotoImage(display)
    canvas.image = photo
    canvas.create_image(0, 0, image=photo, anchor="nw", tags=("preview",))
    canvas.pack(padx=10, pady=(0, 8))

    status = tk.StringVar()
    status_label = ttk.Label(dialog, textvariable=status, anchor="w")
    status_label.pack(fill="x", padx=10, pady=(0, 6))

    def draw_regions():
        canvas.delete("effect-roi")
        for index, (x1, y1, x2, y2) in enumerate(regions, 1):
            canvas.create_rectangle(
                x1 * width, y1 * height, x2 * width, y2 * height,
                outline="#FFD54F", width=2, tags=("effect-roi",),
            )
            canvas.create_text(
                x1 * width + 5, y1 * height + 5, text=str(index),
                anchor="nw", fill="#FFD54F", font=("TkDefaultFont", 10, "bold"),
                tags=("effect-roi",),
            )
        status.set(
            f"พื้นที่ปกป้อง {len(regions)} จุด • ต้นฉบับ {original_size[0]:,} × {original_size[1]:,} px"
        )

    draw_regions()
    drag_start = {"point": None}
    drag_item = {"id": None}

    def clamp_point(event):
        return (
            max(0.0, min(float(width), float(event.x))),
            max(0.0, min(float(height), float(event.y))),
        )

    def on_press(event):
        drag_start["point"] = clamp_point(event)
        if drag_item["id"] is not None:
            canvas.delete(drag_item["id"])
            drag_item["id"] = None

    def on_motion(event):
        if drag_start["point"] is None:
            return
        x0, y0 = drag_start["point"]
        x1, y1 = clamp_point(event)
        if drag_item["id"] is None:
            drag_item["id"] = canvas.create_rectangle(
                x0, y0, x1, y1, outline="#00E5FF", width=2,
            )
        else:
            canvas.coords(drag_item["id"], x0, y0, x1, y1)

    def on_release(event):
        if drag_start["point"] is None:
            return
        rect = normalized_drag_rectangle(
            drag_start["point"], clamp_point(event), (width, height)
        )
        drag_start["point"] = None
        if drag_item["id"] is not None:
            canvas.delete(drag_item["id"])
            drag_item["id"] = None
        if rect is None:
            status.set("กรอบเล็กเกินไป • ลากเลือกพื้นที่ให้กว้างขึ้น")
            return
        regions.append(rect)
        draw_regions()

    canvas.bind("<ButtonPress-1>", on_press)
    canvas.bind("<B1-Motion>", on_motion)
    canvas.bind("<ButtonRelease-1>", on_release)

    buttons = ttk.Frame(dialog, padding=(10, 0, 10, 10))
    buttons.pack(fill="x")

    def undo_last():
        if regions:
            regions.pop()
            draw_regions()

    def clear_all():
        regions.clear()
        draw_regions()

    def finish():
        result["value"] = tuple(regions)
        dialog.destroy()

    def cancel():
        dialog.destroy()

    ttk.Button(buttons, text="ย้อนกรอบล่าสุด", command=undo_last).pack(side="left")
    ttk.Button(buttons, text="ล้างทั้งหมด", command=clear_all).pack(side="left", padx=(6, 0))
    ttk.Button(buttons, text="ยกเลิก", command=cancel).pack(side="right")
    ttk.Button(buttons, text="ยืนยันพื้นที่", command=finish).pack(side="right", padx=(0, 6))

    dialog.protocol("WM_DELETE_WINDOW", cancel)
    dialog.bind("<Escape>", lambda _event: cancel())
    dialog.update_idletasks()
    dialog.grab_set()
    dialog.wait_window()
    return result["value"]
