import cv2
import numpy as np
from signprint_ai.v21_graphics_ai import blend_graphic_detail


def fixture():
    y,x=np.mgrid[:180,:240]
    rgb=np.full((180,240,3),245,np.uint8)
    rgb[40:140,40:200]=(180,20,110)
    photo=cv2.GaussianBlur(rgb,(0,0),1.1)
    return photo,rgb


def test_zero_and_no_confident_graphics_are_exact_bypass():
    a,b=fixture();np.testing.assert_array_equal(blend_graphic_detail(a,b,0),a)
    a=np.full((128,128,3),(60,120,170),np.uint8)
    np.testing.assert_array_equal(blend_graphic_detail(a,np.zeros_like(a)),a)


def test_detail_transfer_changes_edges_without_global_recolouring():
    a,b=fixture();out=blend_graphic_detail(a,b)
    assert np.any(out!=a)
    np.testing.assert_array_equal(out[70:110,70:170],a[70:110,70:170])
    kernel=np.ones((7,7),np.uint8)
    assert np.all(out>=cv2.erode(a,kernel)) and np.all(out<=cv2.dilate(a,kernel))
    # On the straight edge, the transition should narrow, not smear further.
    old_width=np.count_nonzero((a[90,:,0]>185)&(a[90,:,0]<240))
    new_width=np.count_nonzero((out[90,:,0]>185)&(out[90,:,0]<240))
    assert new_width < old_width


def test_low_frequency_model_colour_difference_is_not_copied():
    a,b=fixture();b=np.clip(a.astype(int)+4,0,255).astype('uint8')
    np.testing.assert_array_equal(blend_graphic_detail(a,b),a)


def test_selected_face_is_exactly_photo_model_output():
    a,b=fixture();out=blend_graphic_detail(a,b,protected_regions=((.4,.1,.9,.9),))
    np.testing.assert_array_equal(out[18:162,96:216],a[18:162,96:216])


def test_padded_tile_detail_transfer_matches_full_image():
    a,b=fixture();out=blend_graphic_detail(a,b)
    tile=blend_graphic_detail(a[0:160,0:200],b[0:160,0:200])
    np.testing.assert_allclose(out[64:96,64:136],tile[64:96,64:136],atol=1)


def test_graphic_ai_is_opt_in_to_preserve_approved_photo_core(monkeypatch):
    from types import SimpleNamespace
    from signprint_ai import v21_graphics_ai
    from signprint_ai.niyomsil_core_adapter import NiyomSilpCoreAdapter
    from signprint_ai.v21_graphics_ai import V21Settings

    base_engine = object()
    adapter = NiyomSilpCoreAdapter.__new__(NiyomSilpCoreAdapter)
    adapter.engine_manager = SimpleNamespace(create_engine=lambda device: base_engine)
    default = V21Settings(text_graphic_boost=100)
    assert default.graphic_ai is False
    assert adapter.create_job_engine(default) is base_engine

    calls = []
    class StubGraphicEngine:
        def __init__(self, engine, strength, protected_regions):
            calls.append((engine, strength, protected_regions))
    monkeypatch.setattr(v21_graphics_ai, 'GraphicDetailEngine', StubGraphicEngine)
    assert adapter.create_job_engine(V21Settings(graphic_ai=True, text_graphic_boost=0)) is base_engine
    regions = ((.1, .2, .5, .6),)
    # Opting in to graphic AI now works even with V2 quality finishing on.
    # Default remains OFF to avoid changing existing print jobs silently.
    selected = V21Settings(graphic_ai=True, text_graphic_boost=60,
                           face_protection=True, face_regions=regions)
    assert isinstance(adapter.create_job_engine(selected), StubGraphicEngine)
    assert calls == [(base_engine, .6, regions)]

    experimental = V21Settings(graphic_ai=True, text_graphic_boost=60,
                           face_protection=True, face_regions=regions,
                           v21_v2_quality_baseline=False)
    assert isinstance(adapter.create_job_engine(experimental), StubGraphicEngine)
    assert calls == [(base_engine, .6, regions), (base_engine, .6, regions)]
