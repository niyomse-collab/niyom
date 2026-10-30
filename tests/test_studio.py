import numpy as np
import pytest
from PIL import Image
from signprint_ai.face_module.studio import retouch_crop, apply_studio
from signprint_ai.face_module.detection import map_regions
from signprint_ai.face_module.face_protection import FaceProtectionModule


def test_stretch_region_mapping_keeps_normalized_coordinates():
    regions = ((.1,.2,.5,.6),)
    assert map_regions(regions, (100,50), (70,200), 'stretch') == regions


def test_native_retouch_is_bounded_and_zero_is_identity():
    rng = np.random.default_rng(4)
    pixels = np.clip(rng.normal((180,130,110), 5, (150,150,3)), 0,255).astype('uint8')
    original = Image.fromarray(pixels)
    assert retouch_crop(original, 0).tobytes() == original.tobytes()
    output = np.asarray(retouch_crop(original, 80))
    assert output.shape == pixels.shape
    assert np.abs(output.astype(int)-pixels).max() <= 8
    assert output.std(axis=(0,1)).mean() < pixels.std(axis=(0,1)).mean()


@pytest.mark.parametrize('mode', ['fit', 'stretch'])
def test_studio_changes_only_confirmed_face_and_no_backend(tmp_path, monkeypatch, mode):
    source = tmp_path/'in.png'
    Image.new('RGB', (200,100), (180,130,110)).save(source)
    core = Image.new('RGB', (200,200), (20,30,40))
    module = FaceProtectionModule()
    monkeypatch.setattr(module, '_load_backend', lambda *a: pytest.fail('Studio loaded GFPGAN'))
    region = ((.1,.1,.4,.5),)
    out, info = module.apply(core, device_name='cpu', mode='studio', source_path=source,
                             source_regions=region, resize_mode=mode)
    assert info.applied and info.face_count == 1
    mapped = map_regions(region, (200,100), (200,200), mode)[0]
    x1,y1,x2,y2 = (round(v*200) for v in mapped)
    mask = np.ones((200,200), dtype=bool)
    mask[y1:y2,x1:x2] = False
    assert np.array_equal(np.asarray(out)[mask], np.asarray(core)[mask])
    assert out.getpixel(((x1+x2)//2,(y1+y2)//2)) != core.getpixel((0,0))


def test_empty_selection_zero_strength_and_cancel(tmp_path):
    image = Image.new('RGB', (20,20))
    assert apply_studio(image, 'missing.png', ())[0] is image
    assert apply_studio(image, 'missing.png', ((0,0,1,1),), 0)[0] is image
    source = tmp_path/'src.png'
    image.save(source)
    with pytest.raises(InterruptedError):
        apply_studio(image, source, ((0,0,1,1),), cancel=lambda: True)


def test_protect_stretch_uses_correct_position(tmp_path):
    source = tmp_path/'src.png'
    Image.new('RGB',(200,100),(200,120,100)).save(source)
    output, info = FaceProtectionModule().apply(Image.new('RGB',(200,200)), device_name='cpu',
        mode='protect', source_path=source, source_regions=((.1,.05,.3,.25),), resize_mode='stretch')
    assert output.getpixel((40,30)) == (200,120,100)
    assert info.applied


def test_face_processing_precedes_whole_image_stretch(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from signprint_ai import independent_core
    from signprint_ai.independent_core import DeviceInfo
    from signprint_ai.niyomsil_core_adapter import NiyomSilpCoreAdapter
    from signprint_ai.processing import EnhanceSettings
    monkeypatch.setattr(independent_core, 'DeviceManager', lambda: SimpleNamespace(
        get_default_device=lambda: DeviceInfo('cpu','CPU','CPU')))
    source, dest = tmp_path/'in.png', tmp_path/'out.png'
    Image.new('RGB',(80,40),(180,130,110)).save(source)
    adapter = NiyomSilpCoreAdapter()
    seen = []
    original = adapter.face_module.apply
    def record(image, **kwargs):
        seen.append(image.size)
        return original(image, **kwargs)
    adapter.face_module.apply = record
    settings = EnhanceSettings(print_width=30, print_height=60, print_unit='inch', dpi=1,
        resize_mode='stretch', face_protection=True, face_mode='studio',
        face_regions=((.2,.2,.7,.8),))
    # Explicitly disable AI scaling; print size must not override this choice.
    settings.ai_scale = 1
    adapter.process(source, dest, settings)
    assert seen == [(80,40)]
    assert Image.open(dest).size == (30,60)


def test_studio_ai_retains_recovery_and_bounds_skin_strength(monkeypatch):
    import signprint_ai.face_module.studio as studio
    from signprint_ai.face_module.face_protection import FaceProtectionResult
    core = Image.new('RGB',(100,100),(20,30,40))
    restored = Image.new('RGB',(100,100),(180,130,110))
    module = FaceProtectionModule()
    original_apply = module.apply
    calls = []
    def fake_recover(image, **kwargs):
        calls.append(kwargs)
        return restored, FaceProtectionResult(enabled=True,applied=True,face_count=1,mode='recover')
    module.apply = fake_recover
    skin_strengths = []
    retouch = studio.retouch_crop
    def record(crop, strength):
        skin_strengths.append(strength)
        return retouch(crop, strength)
    monkeypatch.setattr(studio,'retouch_crop',record)
    out, info = original_apply(core, device_name='cpu', mode='studio ai', strength=80,
                              regions=((.2,.2,.8,.8),))
    assert calls[0]['strength'] == 80 and calls[0]['mode'] == 'recover'
    assert skin_strengths == [35]
    assert out.getpixel((50,50))[0] > 150
    assert out.getpixel((0,0)) == core.getpixel((0,0))
    assert info.mode == 'studio ai' and info.applied


def test_studio_ai_reports_missing_model_without_fake_success(monkeypatch):
    module = FaceProtectionModule()
    monkeypatch.setattr(FaceProtectionModule,'available',property(lambda self: False))
    image = Image.new('RGB',(40,40),(30,40,50))
    out, info = module.apply(image,device_name='cpu',mode='studio ai',regions=((.1,.1,.9,.9),))
    assert out.tobytes() == image.tobytes()
    assert not info.applied and info.skipped_reason and info.mode == 'studio ai'
