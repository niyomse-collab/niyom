"""Optional V2.1 graphic-detail model, blended only near flat contrasting ink.

The photo model owns low-frequency colour/shading. The graphic model supplies
bounded high-frequency differences. This is not OCR or guaranteed text recovery.
"""
from dataclasses import dataclass
from pathlib import Path
import hashlib
import tempfile
import cv2
import numpy as np
from PIL import Image
from .processing import EnhanceSettings

GRAPHIC_MODEL_SHA256 = 'f872d837d3c90ed2e05227bed711af5671a6fd1c9f7d7e91c911a61f155e99da'


@dataclass
class V21Settings(EnhanceSettings):
    # Experimental transfer is opt-in; preserve the established photo core by default.
    graphic_ai: bool = False


def blend_graphic_detail(photo, graphic, strength=1., protected_regions=()):
    base = photo.astype(np.float32)
    low, high = photo.min(2), photo.max(2)
    white = (low > 210) & (high - low < 40)
    distance = cv2.distanceTransform((~white).astype('uint8'), cv2.DIST_L2, 5)
    ink = ((high - low > 60) & (low < 170)) | (high < 105)
    r, g, b = base[..., 0], base[..., 1], base[..., 2]
    skin = (r > 90) & (r > g) & (g > b) & (r-g > 15) & (r-b > 25)
    clean = cv2.bilateralFilter(photo, 5, 24, 1.7)
    texture = cv2.GaussianBlur(np.mean(abs(base-clean), axis=2), (17,17), 2)
    mask = ink & (distance < 48) & (~skin) & (texture < 4)
    weight = cv2.GaussianBlur(cv2.dilate(mask.astype('float32'), np.ones((7,7),np.uint8)), (11,11), 1.2)
    weight *= .9 * np.sqrt(np.clip(strength,0,1))
    difference = graphic.astype(np.float32) - base
    detail = np.clip(difference-cv2.GaussianBlur(difference,(33,33),4),-96,96)
    out = np.rint(np.clip(base+detail*weight[...,None],
                         cv2.erode(photo,np.ones((7,7),np.uint8)),
                         cv2.dilate(photo,np.ones((7,7),np.uint8)))).astype('uint8')
    h,w = photo.shape[:2]
    for x1,y1,x2,y2 in protected_regions or ():
        if not all(np.isfinite(v) for v in (x1,y1,x2,y2)) or x2<=x1 or y2<=y1:
            continue
        margin=max(8,round(min((x2-x1)*w,(y2-y1)*h)*.12))
        left,top=max(0,int(np.floor(x1*w))-margin),max(0,int(np.floor(y1*h))-margin)
        right,bottom=min(w,int(np.ceil(x2*w))+margin),min(h,int(np.ceil(y2*h))+margin)
        out[top:bottom,left:right]=photo[top:bottom,left:right]
    return out


class GraphicDetailEngine:
    """Wrap the selected photo engine without changing its V1 implementation."""
    def __init__(self, photo_engine, strength, protected_regions=()):
        from basicsr.archs.rrdbnet_arch import RRDBNet
        from realesrgan import RealESRGANer
        from .independent_core import model_path
        self.photo = photo_engine
        self.upsampler = photo_engine.upsampler
        self.strength = strength
        self.protected_regions = protected_regions
        checkpoint = model_path().with_name('RealESRGAN_x4plus_anime_6B.pth')
        if not checkpoint.is_file():
            raise RuntimeError('ไม่พบโมเดลเก็บขอบข้อความ V2.1 กรุณาติดตั้งชุด V2.1 ให้ครบ หรือปิด AI เก็บขอบข้อความ')
        with checkpoint.open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=GRAPHIC_MODEL_SHA256:
                raise RuntimeError('โมเดลเก็บขอบข้อความ V2.1 ไม่ตรงกับไฟล์ที่ตรวจสอบไว้')
        network = RRDBNet(num_in_ch=3,num_out_ch=3,num_feat=64,num_block=6,num_grow_ch=32,scale=4)
        self.graphics = RealESRGANer(scale=4,model_path=str(checkpoint),model=network,
                                    tile=self.upsampler.tile_size,tile_pad=16,pre_pad=0,
                                    half=False,device=photo_engine.device)

    def device_name(self):
        return self.photo.device_name()

    def _graphics(self, pixels, scale, cancel, tiled):
        if cancel and cancel():raise InterruptedError('Processing stopped by user')
        def check(*args):
            if cancel and cancel():raise InterruptedError('Processing stopped by user')
        hook=self.graphics.model.register_forward_hook(check)
        previous=self.graphics.tile_size
        if tiled:self.graphics.tile_size=0
        try:
            result,_=self.graphics.enhance(pixels,outscale=scale)
            return result
        finally:
            hook.remove();self.graphics.tile_size=previous
            self.graphics.img=None;self.graphics.output=None

    def enhance_graphic_tile(self, pixels, scale, cancel, protected_regions=()):
        photo=self.photo.enhance_tile(pixels,scale,cancel)
        graphic=self._graphics(pixels,scale,cancel,True)
        return blend_graphic_detail(photo,graphic,self.strength,protected_regions)

    def enhance_tile(self, pixels, scale=4, cancel_check=None):
        return self.enhance_graphic_tile(pixels,scale,cancel_check,self.protected_regions)

    def enhance(self, src, dst, scale=4, progress_callback=None, cancel_check=None):
        with tempfile.TemporaryDirectory(prefix='niyomsil_v21_') as folder:
            intermediate=Path(folder)/'photo.png'
            result=self.photo.enhance(src,intermediate,scale,progress_callback,cancel_check)
            with Image.open(src) as image:
                from PIL import ImageOps
                pixels=np.asarray(ImageOps.exif_transpose(image).convert('RGB'))
            with Image.open(intermediate) as image:photo=np.asarray(image.convert('RGB'))
            graphic=self._graphics(pixels,scale,cancel_check,False)
            blended=blend_graphic_detail(photo,graphic,self.strength,self.protected_regions)
            Image.fromarray(blended).save(dst)
        return result
