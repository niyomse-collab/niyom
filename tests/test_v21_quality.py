"""Acceptance of edge geometry and selected AI scale, independent of colour deltas."""
from types import SimpleNamespace
import cv2
import numpy as np
import pytest
from PIL import Image
from signprint_ai.v2_graphic_edges import refine_sign_edges
from signprint_ai.v21_contours import contour_delta, _contour_delta_tile
from signprint_ai.processing import EnhanceSettings


def controls(text=100):
    return EnhanceSettings(denoise=0,flat_smoothing=0,text_graphic_boost=text,
                           sharpness=0,contrast=0,saturation=0)


def positions(rgb, lo, hi, channel=0):
    coverage=(rgb[25:-25,:,channel].astype(float)-lo)/(hi-lo)
    j=np.argmax(coverage>.5,axis=1);rows=np.arange(len(j))
    return j-1+(.5-coverage[rows,j-1])/(coverage[rows,j]-coverage[rows,j-1])


@pytest.mark.parametrize('amplitude,period', [(1,7),(2,12),(3,20)])
@pytest.mark.parametrize('text', [28,100])
def test_wavy_stroke_contour_is_smoother_without_shifting_center(amplitude,period,text):
    y,x=np.mgrid[:256,:256]
    mask=(x>120+amplitude*np.sin(y*2*np.pi/period)).astype(float)
    bg=np.array([236,225,184]);ink=np.array([15,45,150])
    rgb=cv2.GaussianBlur((bg*(1-mask[:,:,None])+ink*mask[:,:,None]).astype(np.float32),(0,0),.8).astype('uint8')
    out=np.asarray(refine_sign_edges(Image.fromarray(rgb),settings=controls(text)))
    before,after=positions(rgb,236,15),positions(out,236,15)
    assert after.std() < before.std() * .94
    assert abs(after.mean()-before.mean()) < .15
    assert np.max(np.abs(after-before)) < 1.8


def test_equal_luminance_coloured_edge_is_not_missed():
    y,x=np.mgrid[:256,:256]
    mask=(x>120+2*np.sin(y*2*np.pi/12)).astype(float)
    bg=np.array([197,0,0]);ink=np.array([0,100,0])  # both grey approx 59
    rgb=cv2.GaussianBlur((bg*(1-mask[:,:,None])+ink*mask[:,:,None]).astype(np.float32),(0,0),.8).astype('uint8')
    out=np.asarray(refine_sign_edges(Image.fromarray(rgb),settings=controls()))
    assert positions(out,197,0).std() < positions(rgb,197,0).std() * .8


def test_ring_hole_stroke_and_detached_marks_survive():
    rgb=np.full((256,256,3),240,np.uint8)
    cv2.circle(rgb,(128,150),60,(20,20,20),10,lineType=cv2.LINE_AA)
    # tone marks at several small sizes, separated from the larger outline
    for x,r in [(40,2),(80,3),(120,5),(160,7)]:
        cv2.circle(rgb,(x,35),r,(20,20,20),-1,lineType=cv2.LINE_AA)
    out=np.asarray(refine_sign_edges(Image.fromarray(rgb),settings=controls()))
    a=(rgb[:,:,0]<128).astype('uint8');b=(out[:,:,0]<128).astype('uint8')
    assert cv2.connectedComponents(a)[0] == cv2.connectedComponents(b)[0] == 6
    assert b[150,128] == 0
    for x in (40,80,120,160):assert b[35,x] == 1
    assert abs(int(a.sum())-int(b.sum())) / a.sum() < .025


def test_bounded_geometry_tiles_match_whole_frame():
    y,x=np.mgrid[:620,:650]
    mask=(x>510+2*np.sin(y*2*np.pi/12)).astype(float)
    rgb=np.rint(240*(1-mask[:,:,None])+np.array([20,40,100])*mask[:,:,None]).astype('uint8')
    np.testing.assert_allclose(np.rint(contour_delta(rgb,1)), np.rint(_contour_delta_tile(rgb,1)), atol=1)


@pytest.mark.parametrize('streaming',[False,True])
@pytest.mark.parametrize('selected,expected',[(1,[]),(2,[2]),(4,[4]),(8,[4,2])])
def test_print_target_does_not_override_selected_ai_passes(tmp_path,monkeypatch,streaming,selected,expected):
    from signprint_ai import large_image,independent_core
    from signprint_ai.niyomsil_core_adapter import NiyomSilpCoreAdapter
    calls=[]
    class Engine:
        upsampler=SimpleNamespace(tile_size=512,tile_pad=10)
        def enhance_tile(self,rgb,scale,cancel):
            calls.append(scale);return np.repeat(np.repeat(rgb,scale,0),scale,1)
        def enhance(self,src,dst,scale,**kwargs):
            with Image.open(src) as im:Image.fromarray(self.enhance_tile(np.asarray(im.convert('RGB')),scale,None)).save(dst)
        def device_name(self):return 'CPU'
    monkeypatch.setattr(independent_core,'DeviceManager',lambda:SimpleNamespace())
    adapter=NiyomSilpCoreAdapter();adapter.engine_manager.create_engine=lambda device:Engine()
    monkeypatch.setattr(large_image,'IN_MEMORY_PIXELS',1 if streaming else 10**9)
    src=tmp_path/'source.png';dst=tmp_path/'out.png';Image.new('RGB',(68,100),(20,40,80)).save(src)
    settings=controls(0);settings.ai_scale=selected
    settings.print_unit='inch';settings.dpi=100;settings.print_width=3.54;settings.print_height=5.21
    report=adapter.process(src,dst,settings)
    assert calls == expected
    assert report['ai_scale'] == selected
    with Image.open(dst) as im:assert im.size == (354,521)


@pytest.mark.parametrize('streaming',[False,True])
def test_translucent_border_rgb_not_filtered_in_either_route(tmp_path,monkeypatch,streaming):
    from signprint_ai import large_image,independent_core
    from signprint_ai.niyomsil_core_adapter import NiyomSilpCoreAdapter
    class Engine:
        upsampler=SimpleNamespace(tile_size=48,tile_pad=10)
        def enhance_tile(self,rgb,scale,cancel):return np.repeat(np.repeat(rgb,scale,0),scale,1)
        def enhance(self,src,dst,scale,**kwargs):
            with Image.open(src) as im:Image.fromarray(self.enhance_tile(np.asarray(im.convert('RGB')),scale,None)).save(dst)
        def device_name(self):return 'CPU'
    monkeypatch.setattr(independent_core,'DeviceManager',lambda:SimpleNamespace())
    adapter=NiyomSilpCoreAdapter();adapter.engine_manager.create_engine=lambda device:Engine()
    monkeypatch.setattr(large_image,'IN_MEMORY_PIXELS',1 if streaming else 10**9)
    rgb=np.full((96,96,3),235,np.uint8);rgb[25:75,20:80]=(30,40,140)
    alpha=np.full((96,96),128,np.uint8);alpha[40:60,40:60]=255
    src=tmp_path/'rgba.png';Image.fromarray(np.dstack((rgb,alpha))).save(src)
    paths=[]
    for value in (0,100):
        out=tmp_path/f'{value}.png';adapter.process(src,out,controls(value));paths.append(out)
    with Image.open(paths[0]) as a,Image.open(paths[1]) as b:
        aa,bb=np.asarray(a),np.asarray(b)
        np.testing.assert_array_equal(aa[...,3],bb[...,3])
        partial=aa[...,3]<255
        np.testing.assert_array_equal(aa[partial],bb[partial])


def test_v21_brand_preserves_v1_metadata_and_labels_new_candidate(monkeypatch):
    from signprint_ai import v21_brand
    monkeypatch.setattr(v21_brand,'load_release_info',lambda:{'channel':'v2','version':'2.1.0-beta.1'})
    assert v21_brand.release_label()=='v2.1'
    monkeypatch.setattr(v21_brand.sys,'frozen',True,raising=False)
    monkeypatch.setattr(v21_brand,'load_release_info',lambda:{'channel':'v1','version':'1.0.1'})
    assert v21_brand.release_label()=='v1'
