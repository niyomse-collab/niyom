"""NAFNet photo deblur stays opt-in and cannot rewrite V2 graphics/faces."""
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from signprint_ai.v211_nafnet_deblur import (
    NAFNET_SHA256, verify_nafnet_checkpoint, blend_photo_deblur
)
from signprint_ai.v211_swinir_preprocess import PreRestoreV2Engine


def test_weight_is_pinned_and_missing_or_wrong_weights_fail_closed(tmp_path):
    assert len(NAFNET_SHA256) == 64
    with pytest.raises(FileNotFoundError):
        verify_nafnet_checkpoint(tmp_path/"missing.pth")
    p = tmp_path/"model.pth"
    p.write_bytes(b"fake weight")
    with pytest.raises(RuntimeError, match="checkpoint"):
        verify_nafnet_checkpoint(p)


def test_contrasting_print_ink_not_replaced_by_deblur():
    source = np.full((120, 120, 3), (110, 150, 145), dtype=np.uint8)
    source[12:42, 10:90] = (245, 20, 30)
    source[45:72, 10:90] = (20, 70, 245)
    source[82:87, 10:90] = (7, 8, 9)
    altered = 255-source
    result = blend_photo_deblur(source, altered, strength=1)
    np.testing.assert_array_equal(result[17:38, 17:83], source[17:38, 17:83])
    np.testing.assert_array_equal(result[50:68, 17:83], source[50:68, 17:83])
    np.testing.assert_array_equal(result[83:86, 30:70], source[83:86, 30:70])


def test_true_photographic_blur_correction_can_change_many_pixels():
    yy, xx = np.mgrid[:128, :128]
    original = np.stack((
        np.clip(xx*2, 0, 255),
        np.clip(35+yy*1.5, 0, 255),
        np.clip(70+xx+yy*.3, 0, 255)), axis=-1
    ).astype(np.uint8)
    original[20:100, 20:100] = (140, 125, 115)
    deblurred = cv2.addWeighted(original, 1.3,
                               cv2.GaussianBlur(original, (0,0), 2), -.3, 0)
    output = blend_photo_deblur(original, deblurred, strength=1)
    assert output.shape == original.shape
    assert np.any(output != original)
    assert np.max(np.abs(output.astype('int16')-original)) <= 90


def test_protected_face_roi_is_pixel_exact():
    rng = np.random.default_rng(123)
    src = rng.integers(30, 160, (96, 112, 3), dtype=np.uint8)
    dest = 255-src
    result = blend_photo_deblur(
        src, dest, 1.0, protected_regions=((.20, .25, .80, .75),))
    np.testing.assert_array_equal(result[25:70, 25:80], src[25:70, 25:80])


def test_zero_strength_exact_original():
    src = np.arange(16*16*3, dtype=np.uint8).reshape(16,16,3)
    np.testing.assert_array_equal(
        blend_photo_deblur(src, 255-src, strength=0), src)


@pytest.mark.parametrize("strength", [-1, 2, float("nan"), float("inf")])
def test_bad_strength_refused(strength):
    rgb = np.zeros((16,16,3), dtype=np.uint8)
    with pytest.raises(ValueError):
        blend_photo_deblur(rgb, rgb, strength)


def test_invalid_face_selection_refused():
    rgb = np.full((32, 32, 3), 120, dtype=np.uint8)
    with pytest.raises(ValueError):
        blend_photo_deblur(rgb,rgb,protected_regions=((0,0,1,float("nan")),))


class V2Stub:
    def __init__(self, log):
        self.log = log
        self.upsampler = SimpleNamespace(tile_size=128, tile_pad=16)
    def device_name(self):return "CPU"
    def enhance_tile(self, rgb,scale=2,cancel_check=None):
        self.log.append(("v2",rgb.copy()))
        return np.repeat(np.repeat(rgb,scale,0),scale,1)

class NAFStub:
    def __init__(self,log):
        self.log=log
        self.upsampler=SimpleNamespace(tile_size=64,tile_pad=24)
    def denoise_tile(self,rgb,cancel_check=None):
        self.log.append(("nafnet",rgb.copy()))
        return cv2.GaussianBlur(rgb,(3,3),1)

def test_nafnet_runs_before_original_v2_engine():
    log=[]
    engine=PreRestoreV2Engine(
        V2Stub(log), NAFStub(log), strength=.85,
        blend_callback=blend_photo_deblur)
    pixels=np.full((72,80,3),126,np.uint8)
    pixels[20:44,20:48]=100
    output=engine.enhance_tile(pixels,scale=2)
    assert output.shape==(144,160,3)
    assert [x[0] for x in log] == ["nafnet","v2"]
    assert engine.next_pass_engine() is engine.v2


def test_adapter_selects_nafnet_without_replacing_v2(monkeypatch):
    from signprint_ai import v211_nafnet_deblur
    from signprint_ai.niyomsil_core_adapter import NiyomSilpCoreAdapter
    log=[]
    v2=V2Stub(log)
    v2.selected=SimpleNamespace(device_id="cpu",name="CPU",backend="CPU")
    class FakeNAF(NAFStub):
        def __init__(self,selected):
            assert selected is v2.selected
            super().__init__(log)
    monkeypatch.setattr(v211_nafnet_deblur,"NAFNetGoProDeblurrer",FakeNAF)
    adapter=NiyomSilpCoreAdapter.__new__(NiyomSilpCoreAdapter)
    adapter.engine_manager=SimpleNamespace(create_engine=lambda _:v2)
    settings=SimpleNamespace(
        v211_photo_model="v2_nafnet_deblur",device="AUTO",
        v211_nafnet_pre_strength=.85,face_regions=None,face_protection=False)
    engine=adapter.create_job_engine(settings)
    assert isinstance(engine,PreRestoreV2Engine)
    assert engine.v2 is v2
    assert engine.next_pass_engine() is v2


def test_ui_and_quality_runner_include_nafnet_research_mode():
    import inspect
    from signprint_ai.app_v2 import App
    from tools.v211_generate_ab import run_pair
    assert "v2_nafnet_deblur" in inspect.getsource(App._settings)
    assert "v2_nafnet_deblur" in inspect.getsource(App.start_processing)
    assert "v2_nafnet_deblur" in inspect.getsource(run_pair)
