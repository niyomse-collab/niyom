"""Shared preview coordinates, independent of Tk and inference."""
from dataclasses import dataclass
from PIL import Image


@dataclass
class PreviewViewport:
    zoom: float = 1.0
    actual: bool = False
    center_x: float = 0.5
    center_y: float = 0.5

    def fit(self):
        self.zoom, self.actual = 1.0, False
        self.center_x = self.center_y = 0.5

    def one_to_one(self):
        self.zoom, self.actual = 1.0, True
        self.center_x = self.center_y = 0.5

    def magnify(self, factor):
        self.zoom = max(0.05, min(64.0, self.zoom * factor))

    def scale(self, image_size, box, reference_size=None):
        if self.actual:
            # 1:1 means output pixels; Before is mapped to the same output scale.
            base = reference_size[0]/image_size[0] if reference_size else 1.0
        else:
            base = min(box[0]/image_size[0], box[1]/image_size[1])
        return self.zoom * base

    def pan(self, dx, dy, image_size, box, reference_size=None):
        scale = self.scale(image_size, box, reference_size)
        self.center_x = max(0.0, min(1.0, self.center_x - dx/(image_size[0]*scale)))
        self.center_y = max(0.0, min(1.0, self.center_y - dy/(image_size[1]*scale)))

    def render(self, image, box, reference_size=None):
        # Allocate only the viewport, even when viewing a very large print at 1:1.
        width, height = box
        scale = self.scale(image.size, box, reference_size)
        left = self.center_x*image.width - width/(2*scale)
        top = self.center_y*image.height - height/(2*scale)
        return image.transform(box, Image.Transform.AFFINE,
                               (1/scale, 0, left, 0, 1/scale, top),
                               resample=Image.Resampling.BICUBIC, fillcolor=(23, 23, 23))
