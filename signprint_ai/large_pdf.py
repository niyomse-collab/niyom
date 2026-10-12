"""A single physical-size PDF page made from bounded, lossless image tiles."""
from __future__ import annotations

import math
import shutil
import tempfile
import zlib


def save_pdf(image, path, dpi, profile=None, progress=None, cancel=None):
    from .large_image import check_cancel

    points = image.width * 72 / dpi, image.height * 72 / dpi
    unit = max(1, math.ceil(max(points) / 14_400))
    if unit > 75_000:
        raise ValueError("ขนาดจริงของหน้ากระดาษเกินช่วงที่รูปแบบ PDF รองรับ กรุณาเลือก TIFF หรือ PNG")
    width, height = points[0] / unit, points[1] / unit
    offsets = [0, 0, 0, 0, 0]
    resources = []
    # Content instructions are spooled to disk rather than held with image data.
    with open(path, "wb") as output, tempfile.TemporaryFile() as commands:
        output.write(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")

        def object_at(number, data):
            while len(offsets) <= number:
                offsets.append(0)
            offsets[number] = output.tell()
            output.write(f"{number} 0 obj\n".encode())
            output.write(data)
            output.write(b"\nendobj\n")

        def stream_at(number, header, data):
            object_at(number, f"<< {header} /Length {len(data)} >>\nstream\n".encode() + data + b"\nendstream")

        color = "/DeviceCMYK" if image.bands == 4 else "/DeviceRGB"
        next_id = 5
        if profile:
            from pathlib import Path
            stream_at(next_id, f"/N {image.bands} /Alternate {color}", Path(profile).read_bytes())
            color = f"[/ICCBased {next_id} 0 R]"
            next_id += 1
        total = math.ceil(image.width / 1024) * math.ceil(image.height / 512)
        done = 0
        for y in range(0, image.height, 512):
            for x in range(0, image.width, 1024):
                check_cancel(cancel)
                w, h = min(1024, image.width - x), min(512, image.height - y)
                tile = image.crop(x, y, w, h)
                data = zlib.compress(tile.write_to_memory(), level=3)
                name = f"Im{done}"
                stream_at(next_id, f"/Type /XObject /Subtype /Image /Width {w} /Height {h} "
                          f"/ColorSpace {color} /BitsPerComponent 8 /Filter /FlateDecode", data)
                resources.append(f"/{name} {next_id} 0 R")
                next_id += 1
                factor = 72 / dpi / unit
                commands.write((f"q {w*factor:.10f} 0 0 {h*factor:.10f} "
                                f"{x*factor:.10f} {(image.height-y-h)*factor:.10f} cm /{name} Do Q\n").encode())
                done += 1
                if progress:
                    progress(88 + round(11 * done / total), f"บันทึก PDF · ส่วน {done:,}/{total:,}")
        check_cancel(cancel)
        object_at(1, b"<< /Type /Catalog /Pages 2 0 R >>")
        object_at(2, b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
        object_at(3, (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width:.10f} {height:.10f}] "
                      f"/UserUnit {unit} /Resources << /XObject << {' '.join(resources)} >> >> "
                      "/Contents 4 0 R >>").encode())
        offsets[4] = output.tell()
        output.write(f"4 0 obj\n<< /Length {commands.tell()} >>\nstream\n".encode())
        commands.seek(0)
        shutil.copyfileobj(commands, output, length=1024 * 1024)
        output.write(b"\nendstream\nendobj\n")
        start = output.tell()
        # Xref streams use 64-bit offsets, allowing PDFs larger than 10 GB.
        xref_id = len(offsets)
        offsets.append(start)
        entries = b"\x00" + (0).to_bytes(8, "big") + (65535).to_bytes(2, "big")
        entries += b"".join(b"\x01" + offset.to_bytes(8, "big") + b"\x00\x00" for offset in offsets[1:])
        compressed = zlib.compress(entries)
        stream_at(xref_id, f"/Type /XRef /Size {len(offsets)} /Root 1 0 R /W [1 8 2] /Filter /FlateDecode", compressed)
        output.write(f"startxref\n{start}\n%%EOF\n".encode())
