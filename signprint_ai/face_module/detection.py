"""Detection-only preflight and confirmed-region matching."""
from pathlib import Path
import threading
import numpy as np
from PIL import Image
from .face_protection import resource_root


class FaceDetector:
    def __init__(self):
        self._model = None
        self._lock = threading.Lock()

    def detect(self, path):
        import torch
        import cv2
        from facexlib.detection import init_detection_model
        with self._lock:
            folder = resource_root() / 'models' / 'face'
            checkpoint = folder / 'detection_Resnet50_Final.pth'
            if not checkpoint.is_file():
                raise FileNotFoundError(f'ไม่พบโมเดลตรวจจับใบหน้า: {checkpoint}')
            if self._model is None:
                # CPU preflight does not compete with an active CUDA render.
                self._model = init_detection_model('retinaface_resnet50', half=False,
                                                   device='cpu', model_rootpath=str(folder))
            with Image.open(path) as source:
                image = source.convert('RGB')
                image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
                pixels = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
            with torch.no_grad():
                boxes = self._model.detect_faces(pixels, 0.9)
            regions = []
            for box in boxes:
                x1, y1, x2, y2 = box[:4]
                region = (max(0., float(x1)/image.width), max(0., float(y1)/image.height),
                          min(1., float(x2)/image.width), min(1., float(y2)/image.height))
                if region[2] > region[0] and region[3] > region[1]:
                    regions.append(region)
            return tuple(regions)


def map_regions(regions, source_size, target_size):
    """Map source normalized regions through the existing fit/white-padding stage."""
    # Match ImageOps.contain without allocating a print-sized temporary image.
    ratio = source_size[0]/source_size[1]
    if ratio > target_size[0]/target_size[1]:
        contained = (target_size[0], round(target_size[0]/ratio))
    else:
        contained = (round(target_size[1]*ratio), target_size[1])
    offset_x = (target_size[0]-contained[0])//2
    offset_y = (target_size[1]-contained[1])//2
    return tuple(((x1*contained[0]+offset_x)/target_size[0],
                  (y1*contained[1]+offset_y)/target_size[1],
                  (x2*contained[0]+offset_x)/target_size[0],
                  (y2*contained[1]+offset_y)/target_size[1]) for x1,y1,x2,y2 in regions)


def selected_indices(boxes, regions, size):
    """Use spatial association, never detector order, to keep face consent stable."""
    result = []
    for index, box in enumerate(boxes):
        cx, cy = (float(box[0])+float(box[2]))/(2*size[0]), (float(box[1])+float(box[3]))/(2*size[1])
        if any(x1 <= cx <= x2 and y1 <= cy <= y2 for x1,y1,x2,y2 in regions):
            result.append(index)
    return result
