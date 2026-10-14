"""Optional confirmed face regions on disk-backed V2 masters."""
from __future__ import annotations

import math
import numpy as np


def apply_faces(adapter, image, source, settings, folder, progress, cancel):
    from .large_image import check_cancel, resize_image, to_pillow, vips

    info = {"enabled": True, "applied": False, "face_count": 0,
            "mode": settings.face_mode, "strength": settings.face_strength,
            "skipped_reason": None}
    regions = settings.face_regions
    if regions is None:
        info["skipped_reason"] = "ภาพใหญ่ต้องเลือกและยืนยันบริเวณใบหน้าก่อนปรับใบหน้า"
        return image, info
    if not regions:
        return image, info
    for index, region in enumerate(regions):
        check_cancel(cancel)
        x1, y1, x2, y2 = (max(0.0, min(1.0, float(n))) for n in region)
        if x2 <= x1 or y2 <= y1:
            continue
        pad_x, pad_y = (x2-x1)*.18, (y2-y1)*.18
        expanded = max(0,x1-pad_x), max(0,y1-pad_y), min(1,x2+pad_x), min(1,y2+pad_y)

        def box(size):
            return (math.floor(expanded[0]*size[0]), math.floor(expanded[1]*size[1]),
                    math.ceil(expanded[2]*size[0]), math.ceil(expanded[3]*size[1]))

        left, top, right, bottom = box((image.width, image.height))
        sl, st, sr, sb = box((source.width, source.height))
        width, height = right-left, bottom-top
        patch = image.crop(left, top, width, height)
        original = source.crop(sl, st, sr-sl, sb-st)
        try:
            if settings.face_mode == "protect":
                detail = resize_image(original, (width, height), "stretch")
            else:
                factor = min(1.0, 1600 / max(width, height))
                small_size = max(1, round(width*factor)), max(1, round(height*factor))
                small = to_pillow(resize_image(patch, small_size, "stretch"))
                source_patch = folder / "face_source.png"
                resize_image(original, small_size, "stretch").pngsave(str(source_patch))
                local = (((x1-expanded[0])/(expanded[2]-expanded[0]),
                          (y1-expanded[1])/(expanded[3]-expanded[1]),
                          (x2-expanded[0])/(expanded[2]-expanded[0]),
                          (y2-expanded[1])/(expanded[3]-expanded[1])),)
                engine = adapter.engine_manager.engine
                selected = (engine.selected if engine else
                            adapter.engine_manager.device_manager.get_default_device())
                restored, face_result = adapter.face_module.apply(
                    small, device_name=selected.device_id, mode=settings.face_mode,
                    strength=settings.face_strength, regions=local,
                    source_path=source_patch, source_regions=local,
                    resize_mode="stretch", cancel=cancel)
                if not face_result.applied:
                    info["skipped_reason"] = face_result.skipped_reason
                    continue
                # Apply only the bounded restoration delta. The full master and
                # its texture are retained at their exact original resolution.
                delta = np.asarray(restored, dtype="float32") - np.asarray(small, dtype="float32")
                delta_image = vips().Image.new_from_memory(delta.tobytes(), small.width, small.height, 3, "float")
                detail = patch.cast("float") + resize_image(delta_image, (width, height), "stretch")
            coordinates = vips().Image.xyz(width, height)
            xx, yy = coordinates[0], coordinates[1]
            edge_x = (xx < width-1-xx).ifthenelse(xx, width-1-xx)
            edge_y = (yy < height-1-yy).ifthenelse(yy, height-1-yy)
            distance = (edge_x < edge_y).ifthenelse(edge_x, edge_y)
            mask = distance / max(1, min(width, height)*.06)
            mask = (mask > 1).ifthenelse(1, mask)
            mixed = (patch * (1-mask) + detail * mask).cast("uchar")
            image = image.insert(mixed, left, top)
            info["applied"] = True
            info["face_count"] += 1
        except InterruptedError:
            raise
        except Exception as exc:
            info["skipped_reason"] = f"Face ข้ามบางบริเวณ: {exc}"
        if progress:
            progress(82 + round(5*(index+1)/len(regions)), f"ปรับใบหน้าภาพใหญ่ · {index+1}/{len(regions)}")
    return image, info
