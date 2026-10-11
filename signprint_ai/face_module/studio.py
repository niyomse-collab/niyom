"""Native, non-generative retouch inspired by the supplied Photoshop actions.

This does not execute ATN files or embed Imagenomic. Surface smoothing,
thresholded high-pass detail and a mild luminance curve are implemented here.
Only confirmed face rectangles are composited; the core image stays untouched
elsewhere. Colour-based skin selection is a heuristic, not semantic parsing.
"""
import math
import cv2
import numpy as np
from PIL import Image, ImageOps
from .detection import map_regions


def retouch_crop(image, strength):
    amount = max(0., min(1., float(strength) / 100.))
    if not amount:
        return image.copy()
    rgb = np.asarray(image.convert('RGB'))
    # Compute the retouch delta at bounded size, retaining full-size source
    # texture when applying that delta. Never synthesize a replacement face.
    h, w = rgb.shape[:2]
    scale = min(1., 1600 / max(h, w))
    small = cv2.resize(rgb, (max(1, round(w*scale)), max(1, round(h*scale))),
                       interpolation=cv2.INTER_AREA) if scale < 1 else rgb
    base = small.astype(np.float32)
    ycc = cv2.cvtColor(small, cv2.COLOR_RGB2YCrCb).astype(np.float32)
    lum = ycc[..., 0]
    # Soft chroma weights avoid abrupt colour-selection borders.
    cr, cb = ycc[..., 1], ycc[..., 2]
    skin = np.clip((cr-128)/12, 0, 1) * np.clip((182-cr)/14, 0, 1)
    skin *= np.clip((cb-72)/16, 0, 1) * np.clip((140-cb)/16, 0, 1)
    skin *= np.clip((lum-25)/35, 0, 1) * np.clip((250-lum)/20, 0, 1)
    edge = cv2.magnitude(cv2.Sobel(lum, cv2.CV_32F, 1, 0),
                         cv2.Sobel(lum, cv2.CV_32F, 0, 1))
    skin *= 1 - np.clip(edge/100, 0, 1)
    smooth = cv2.bilateralFilter(small, 9, 24, 5).astype(np.float32)
    delta = (smooth-base) * skin[..., None] * (.65*amount)
    high = lum-cv2.GaussianBlur(lum, (0, 0), 1.0)
    high = np.where(np.abs(high) > 2.5, np.clip(high, -6, 6), 0)
    curve = 2.0 * np.sin((lum/255-.5)*np.pi*2)
    delta += (high*.35 + curve)[..., None]*amount
    delta = np.clip(delta, -10*amount, 10*amount)
    if scale < 1:
        delta = cv2.resize(delta, (w, h), interpolation=cv2.INTER_LINEAR)
    return Image.fromarray(np.clip(np.rint(rgb.astype(np.float32)+delta), 0, 255).astype('uint8'))


def apply_studio(output, source_path, regions, strength=35, resize_mode='fit',
                 cancel=None, progress=None):
    if not regions or strength <= 0:
        return output, 0
    if output.width * output.height > 80_000_000:
        raise ValueError("Studio รองรับภาพไม่เกิน 80 ล้านพิกเซลต่อรอบ")
    result = output.copy()
    count = 0
    with Image.open(source_path) as raw:
        source = ImageOps.exif_transpose(raw).convert('RGB')
        for region in regions:
            if cancel and cancel():
                raise InterruptedError('Studio retouch cancelled')
            x1, y1, x2, y2 = (max(0., min(1., float(v))) for v in region)
            if x2 <= x1 or y2 <= y1:
                continue
            srcbox = (math.floor(x1*source.width), math.floor(y1*source.height),
                      math.ceil(x2*source.width), math.ceil(y2*source.height))
            mapped = map_regions(((x1,y1,x2,y2),), source.size, output.size, resize_mode)[0]
            box = tuple(round(v*s) for v,s in zip(mapped, (output.width,output.height)*2))
            w,h = box[2]-box[0],box[3]-box[1]
            if min(w,h) < 1:
                continue
            detail = retouch_crop(source.crop(srcbox), strength).resize((w,h), Image.Resampling.LANCZOS)
            if cancel and cancel():
                raise InterruptedError('Studio retouch cancelled')
            yy,xx = np.ogrid[-1:1:complex(h), -1:1:complex(w)]
            radius = np.sqrt(xx*xx+yy*yy)
            mask = Image.fromarray(np.rint(np.clip((1-radius)/.22,0,1)*255).astype('uint8'))
            result.paste(detail, box[:2], mask)
            count += 1
            if progress:
                progress(round(100*count/len(regions)), f'NiyomSilp Studio · ใบหน้า {count}/{len(regions)}')
    return result, count
