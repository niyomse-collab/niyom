import ast
from pathlib import Path
from types import SimpleNamespace
import sys

import numpy as np
import pytest
from PIL import Image
from signprint_ai.independent_core import DeviceInfo, DeviceManager, RealESRGANEngine

ROOT = Path(__file__).resolve().parents[1]


def test_no_legacy_imports():
    for path in (ROOT / 'signprint_ai').rglob('*.py'):
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or '').startswith(('app.engine', 'app.device'))
    assert not (ROOT / 'app/engine/realesrgan_engine.py').exists()


def test_device_priority_and_explicit_selection():
    manager = DeviceManager.__new__(DeviceManager)
    manager.devices = [DeviceInfo('cpu', 'CPU', 'CPU'), DeviceInfo('dml:0', 'AMD', 'DIRECTML'),
                       DeviceInfo('cuda:1', 'NVIDIA', 'CUDA')]
    assert manager.get_default_device().device_id == 'cuda:1'
    assert manager.get_device('dml:0').name == 'AMD'
    manager.devices.pop()
    assert manager.get_default_device().backend == 'DIRECTML'
    assert manager.get_device('missing') is None


def fake_engine(monkeypatch, fail=False):
    monkeypatch.setitem(sys.modules, 'torch', SimpleNamespace())
    engine = RealESRGANEngine.__new__(RealESRGANEngine)
    engine.selected = DeviceInfo('cpu', 'CPU', 'CPU')
    state = SimpleNamespace(callback=None, removed=False)
    def register(callback):
        state.callback = callback
        return SimpleNamespace(remove=lambda: setattr(state, 'removed', True))
    def enhance(pixels, outscale):
        state.callback(None, None, None)
        if fail:
            raise RuntimeError('inference failed')
        return np.repeat(np.repeat(pixels, outscale, axis=0), outscale, axis=1), None
    engine.upsampler = SimpleNamespace(tile_size=128, model=SimpleNamespace(register_forward_hook=register), enhance=enhance)
    return engine, state


@pytest.mark.parametrize('scale', [2, 4])
def test_pixels_progress_and_hook_cleanup(monkeypatch, tmp_path, scale):
    engine, state = fake_engine(monkeypatch)
    src, dst = tmp_path/'in.png', tmp_path/'out.png'
    Image.new('RGB', (3, 2), (201, 31, 8)).save(src)
    progress = []
    result = engine.enhance(src, dst, scale, progress.append)
    assert result['output_size'] == (3*scale, 2*scale)
    assert Image.open(dst).getpixel((0, 0)) == (201, 31, 8)
    assert progress == [100] and state.removed


def test_cancel_without_progress_listener(monkeypatch, tmp_path):
    engine, state = fake_engine(monkeypatch)
    src, dst = tmp_path/'in.png', tmp_path/'out.png'
    Image.new('RGB', (3, 2)).save(src)
    checks = iter([False, True])
    with pytest.raises(InterruptedError):
        engine.enhance(src, dst, cancel_check=lambda: next(checks))
    assert state.removed and not dst.exists()


def test_hook_cleanup_on_inference_failure(monkeypatch, tmp_path):
    engine, state = fake_engine(monkeypatch, fail=True)
    src, dst = tmp_path/'in.png', tmp_path/'out.png'
    Image.new('RGB', (3, 2)).save(src)
    with pytest.raises(RuntimeError, match='inference failed'):
        engine.enhance(src, dst)
    assert state.removed and not dst.exists()


def test_adapter_passes_and_unfiltered_export(monkeypatch, tmp_path):
    from signprint_ai import independent_core
    monkeypatch.setattr(independent_core, 'DeviceManager', lambda: SimpleNamespace(
        get_default_device=lambda: DeviceInfo('cpu', 'CPU', 'CPU')))
    from signprint_ai.niyomsil_core_adapter import NiyomSilpCoreAdapter
    from signprint_ai.arm_core_adapter import ARMCoreAdapter
    assert ARMCoreAdapter is NiyomSilpCoreAdapter
    from signprint_ai.processing import EnhanceSettings
    adapter = ARMCoreAdapter()
    def unexpected_face_layer(*args, **kwargs):
        raise AssertionError('Disabled face processing must never touch output pixels')
    adapter.face_module.apply = unexpected_face_layer
    calls = []
    devices = []
    def enhance(src, dst, scale, **kwargs):
        calls.append(scale)
        with Image.open(src) as image:
            image.resize((image.width*scale, image.height*scale), Image.Resampling.NEAREST).save(dst)
    adapter.engine_manager.engine = SimpleNamespace(enhance=enhance, device_name=lambda: 'CPU')
    def select(device):
        devices.append(device)
        return adapter.engine_manager.engine
    adapter.engine_manager.create_engine = select
    src = tmp_path/'in.png'
    pixels = np.array([[[201,31,8], [0,255,0], [255,255,255]],
                       [[0,0,0], [33,74,198], [255,0,255]]], dtype=np.uint8)
    Image.fromarray(pixels).save(src)
    for scale, passes in [(2, [2]), (4, [4]), (8, [4, 2])]:
        calls.clear()
        dst = tmp_path/f'out{scale}.png'
        result = adapter.process(src, dst, EnhanceSettings(ai_scale=scale, device='cuda:1'))
        assert calls == passes
        assert devices[-1] == 'cuda:1'
        assert result['output_size'] == (3*scale, 2*scale)
        expected = np.repeat(np.repeat(pixels, scale, axis=0), scale, axis=1)
        np.testing.assert_array_equal(np.array(Image.open(dst)), expected)

@pytest.mark.parametrize('backend,tile', [('CPU', 128), ('CUDA', 256), ('DIRECTML', 128)])
def test_constructor_preserves_model_contract(monkeypatch, tmp_path, backend, tile):
    from signprint_ai import independent_core
    checkpoint = tmp_path/'RealESRGAN_x4plus.pth'
    checkpoint.touch()
    monkeypatch.setattr(independent_core, 'model_path', lambda: checkpoint)
    captured = {}
    def network(**kwargs):
        captured['network'] = kwargs
        return 'network'
    def upsampler(**kwargs):
        captured['inference'] = kwargs
        return SimpleNamespace()
    monkeypatch.setitem(sys.modules, 'torch', SimpleNamespace(device=lambda device: device))
    monkeypatch.setitem(sys.modules, 'torch_directml', SimpleNamespace(device=lambda index: f'dml:{index}'))
    monkeypatch.setitem(sys.modules, 'basicsr', SimpleNamespace())
    monkeypatch.setitem(sys.modules, 'basicsr.archs', SimpleNamespace())
    monkeypatch.setitem(sys.modules, 'basicsr.archs.rrdbnet_arch', SimpleNamespace(RRDBNet=network))
    monkeypatch.setitem(sys.modules, 'realesrgan', SimpleNamespace(RealESRGANer=upsampler))
    identifier = {'CPU': 'cpu', 'CUDA': 'cuda:1', 'DIRECTML': 'dml:0'}[backend]
    RealESRGANEngine(DeviceInfo(identifier, backend, backend))
    assert captured['network'] == dict(num_in_ch=3, num_out_ch=3, num_feat=64,
                                       num_block=23, num_grow_ch=32, scale=4)
    assert captured['inference'] == dict(scale=4, model_path=str(checkpoint), model='network',
                                         tile=tile, tile_pad=10, pre_pad=0, half=False, device=identifier)

@pytest.mark.parametrize('target', [(120, 40), (60, 100)])
@pytest.mark.parametrize('mode', ['fit', 'stretch'])
def test_print_size_export_respects_resize_mode(monkeypatch, tmp_path, target, mode):
    from signprint_ai import independent_core
    from signprint_ai.niyomsil_core_adapter import NiyomSilpCoreAdapter
    from signprint_ai.processing import EnhanceSettings
    monkeypatch.setattr(independent_core, 'DeviceManager', lambda: SimpleNamespace(
        get_default_device=lambda: DeviceInfo('cpu', 'CPU', 'CPU')))
    src, dst = tmp_path/'source.png', tmp_path/'printed.png'
    color = (201, 31, 8)
    Image.new('RGB', (60, 40), color).save(src)
    settings = EnhanceSettings(print_width=target[0], print_height=target[1],
                               print_unit='inch', dpi=1, resize_mode=mode)
    NiyomSilpCoreAdapter().process(src, dst, settings, use_ai=False)
    with Image.open(dst) as output:
        assert output.size == target
        assert output.getpixel((target[0]//2, target[1]//2)) == color
        assert output.getpixel((0, 0)) == (color if mode == 'stretch' else (255, 255, 255))


def test_ui_transmits_lock_state_without_changing_ratio_sync():
    tree = ast.parse((ROOT/'signprint_ai/app_v2.py').read_text(encoding='utf-8'))
    settings = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == '_settings')
    init = next(n for n in ast.walk(settings) if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Name) and n.func.id == 'EnhanceSettings')
    mode = next(k.value for k in init.keywords if k.arg == 'resize_mode')
    for locked, expected in [(True, 'fit'), (False, 'stretch')]:
        obj = SimpleNamespace(lock_ratio=SimpleNamespace(get=lambda: locked))
        assert eval(compile(ast.Expression(mode), '<resize-mode>', 'eval'), {'self': obj}) == expected
