"""Protect selected face detail without generative reconstruction or a 512px bottleneck."""
import math
from PIL import Image, ImageDraw, ImageFilter
from .detection import map_regions


def preserve_source_faces(output, source_path, regions, cancel=None):
    if not regions:
        return output, 0
    result = output.copy()
    count = 0
    with Image.open(source_path) as source:
        source = source.convert('RGB')
        for region in regions:
            if cancel and cancel():
                raise InterruptedError('Processing stopped by user')
            x1,y1,x2,y2 = region
            # Include the face boundary; feather only the surrounding margin.
            padx, pady = (x2-x1)*.18, (y2-y1)*.18
            expanded = (max(0,x1-padx),max(0,y1-pady),min(1,x2+padx),min(1,y2+pady))
            mapped = map_regions((expanded,), source.size, result.size)[0]
            srcbox = (math.floor(expanded[0]*source.width),math.floor(expanded[1]*source.height),
                      math.ceil(expanded[2]*source.width),math.ceil(expanded[3]*source.height))
            dstbox = (max(0,round(mapped[0]*result.width)),max(0,round(mapped[1]*result.height)),
                      min(result.width,round(mapped[2]*result.width)),min(result.height,round(mapped[3]*result.height)))
            width,height = dstbox[2]-dstbox[0],dstbox[3]-dstbox[1]
            if min(width,height,srcbox[2]-srcbox[0],srcbox[3]-srcbox[1]) < 1:
                continue
            detail = source.crop(srcbox).resize((width,height), Image.Resampling.LANCZOS)
            margin = max(1,round(min(width,height)*.06))
            mask = Image.new('L',(width,height),0)
            if min(width,height) > margin*2:
                ImageDraw.Draw(mask).rectangle((margin,margin,width-margin-1,height-margin-1),fill=255)
                mask = mask.filter(ImageFilter.GaussianBlur(max(.5,margin/2)))
            else:
                mask.paste(255,(0,0,width,height))
            result.paste(detail,dstbox[:2],mask)
            count += 1
    return result,count
