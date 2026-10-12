"""Behavioral checks for exact-size V2 disk processing and failure cleanup."""
from types import SimpleNamespace

import cv2
import numpy as np
import pytest
from PIL import Image
from pypdf import PdfReader

from signprint_ai import independent_core, large_image
from signprint_ai.independent_core import DeviceInfo
from signprint_ai.niyomsil_core_adapter import NiyomSilpCoreAdapter
from signprint_ai.processing import EnhanceSettings, print_pixels
from signprint_ai.preview_viewport import PreviewViewport


@pytest.fixture
def adapter(monkeypatch):
    monkeypatch.setattr(independent_core, "DeviceManager", lambda: SimpleNamespace(
        get_default_device=lambda: DeviceInfo("cpu", "CPU", "CPU")))
    return NiyomSilpCoreAdapter()


def source_file(tmp_path):
    pixels = np.arange(19*13*3, dtype="uint16").reshape(13, 19, 3).astype("uint8")
    path = tmp_path / "source.png"
    Image.fromarray(pixels).save(path)
    return path, pixels


def settings_for(size, mode="stretch", dpi=300):
    return EnhanceSettings(print_width=size[0]/dpi, print_height=size[1]/dpi,
                           print_unit="inch", dpi=dpi, resize_mode=mode)


@pytest.mark.parametrize("size", [(700, 100), (1400, 300), (5000, 1500)])
def test_large_print_requests_are_accepted_without_clamping(size):
    target = print_pixels(*size, "cm", 300)
    large_image.validate_target_size(target)
    assert large_image.needs_streaming((1000, 600), target)


@pytest.mark.parametrize("value,expected", [("16x",16), ("32X",32), (" 128 ",128), (1,1)])
def test_custom_scale(value, expected):
    assert large_image.parse_scale(value) == expected


@pytest.mark.parametrize("value", ["0x", "-3", "NaN", "inf", "3.5", ""])
def test_invalid_scale_is_reported(value):
    with pytest.raises(ValueError):
        large_image.parse_scale(value)


@pytest.mark.parametrize("suffix", [".png", ".tif", ".jpg", ".pdf"])
@pytest.mark.parametrize("mode", ["fit", "stretch"])
def test_streamed_output_dimensions_dpi_and_border_color(adapter, monkeypatch, tmp_path, suffix, mode):
    monkeypatch.setattr(large_image, "IN_MEMORY_PIXELS", 1)
    src, dst = tmp_path/"in.png", tmp_path/("out"+suffix)
    color = (41, 123, 207)
    Image.new("RGB", (60, 40), color).save(src)
    target = (200, 70)
    result = adapter.process(src, dst, settings_for(target, mode), use_ai=False)
    assert result["output_size"] == target and result["processing_mode"] == "disk_tiles"
    if suffix == ".pdf":
        page = PdfReader(dst).pages[0]
        assert float(page.mediabox.width)*page.get("/UserUnit",1) == pytest.approx(target[0]*72/300)
        image = page.images[0].image
    else:
        image = Image.open(dst)
        assert image.info["dpi"] == pytest.approx((300,300), abs=.03)
    assert image.size == target
    center = image.convert("RGB").getpixel((100,35))
    assert max(abs(a-b) for a,b in zip(center,color)) <= (3 if suffix == ".jpg" else 0)
    edge = image.convert("RGB").getpixel((0,0))
    expected = color if mode == "stretch" else (255,255,255)
    assert max(abs(a-b) for a,b in zip(edge,expected)) <= (3 if suffix == ".jpg" else 0)
    image.close()
    assert not list(tmp_path.glob(".niyomsil*"))


def test_wide_png_exceeds_old_side_ceiling(adapter, tmp_path):
    src = tmp_path/"in.png"
    Image.new("RGB", (20,20), (18,91,203)).save(src)
    target = (130_001, 2)
    result = adapter.process(src, tmp_path/"wide.png", settings_for(target), use_ai=False)
    assert result["output_size"] == target
    with Image.open(result["output"]) as output:
        assert output.size == target and output.getpixel((130_000,1)) == (18,91,203)


@pytest.mark.parametrize("scale", [2,4,8,16])
def test_tiled_ai_keeps_passes_exact_size_and_bounded_tiles(adapter, monkeypatch, tmp_path, scale):
    monkeypatch.setattr(large_image, "IN_MEMORY_PIXELS", 1)
    src, pixels = source_file(tmp_path)
    calls = []
    def enhance_tile(tile, amount, cancel):
        calls.append((amount,tile.shape))
        return np.repeat(np.repeat(tile, amount, axis=0), amount, axis=1)
    engine = SimpleNamespace(upsampler=SimpleNamespace(tile_size=8,tile_pad=3),
                             enhance_tile=enhance_tile, device_name=lambda: "CPU")
    adapter.engine_manager.create_engine = lambda device: engine
    result = adapter.process(src, tmp_path/"ai.png", EnhanceSettings(ai_scale=scale))
    assert result["output_size"] == (19*scale,13*scale)
    assert result["requested_ai_scale"] == scale
    assert {n for n,_ in calls} == ({4,2} if scale >= 8 else {scale})
    assert max(max(shape[:2]) for _,shape in calls) <= 14
    if scale <= 8:
        with Image.open(result["output"]) as output:
            np.testing.assert_array_equal(np.asarray(output), np.repeat(np.repeat(pixels,scale,axis=0),scale,axis=1))
    assert not list(tmp_path.glob(".niyomsil*"))


def test_tile_context_matches_whole_image_filter(tmp_path):
    _, pixels = source_file(tmp_path)
    src, dst = tmp_path/"src.tif", tmp_path/"out.tif"
    Image.fromarray(pixels).save(src)
    def enhance(tile, scale, cancel):
        filtered = cv2.GaussianBlur(tile, (5,5), .9)
        return np.repeat(np.repeat(filtered,scale,axis=0),scale,axis=1)
    engine = SimpleNamespace(upsampler=SimpleNamespace(tile_size=8,tile_pad=3),enhance_tile=enhance)
    size = large_image.upscale_raster(src,dst,(19,13),4,engine,None,None,0,100)
    with Image.open(dst) as result:
        actual = np.array(result)
    expected = np.repeat(np.repeat(cv2.GaussianBlur(pixels,(5,5),.9),4,axis=0),4,axis=1)
    np.testing.assert_array_equal(actual,expected)


@pytest.mark.parametrize("exception", [InterruptedError("stop"), RuntimeError("inference failed")])
def test_failed_ai_preserves_existing_output_and_cleans_temp(adapter, monkeypatch, tmp_path, exception):
    monkeypatch.setattr(large_image, "IN_MEMORY_PIXELS", 1)
    src,_ = source_file(tmp_path)
    dst = tmp_path/"existing.png"
    dst.write_bytes(b"original output")
    def fail(*args):
        raise exception
    engine = SimpleNamespace(upsampler=SimpleNamespace(tile_size=8,tile_pad=3),enhance_tile=fail)
    adapter.engine_manager.create_engine = lambda device: engine
    with pytest.raises(type(exception)):
        adapter.process(src,dst,EnhanceSettings(ai_scale=4))
    assert dst.read_bytes() == b"original output"
    assert not list(tmp_path.glob(".niyomsil*"))


def test_export_cancellation_is_atomic(adapter, monkeypatch, tmp_path):
    monkeypatch.setattr(large_image, "IN_MEMORY_PIXELS", 1)
    src,_ = source_file(tmp_path)
    dst = tmp_path/"existing.png"
    dst.write_bytes(b"original output")
    stopped = [False]
    def progress(value, label):
        if value >= 99:
            stopped[0] = True
    with pytest.raises(InterruptedError):
        adapter.process(src,dst,settings_for((1000,700)),use_ai=False,
                        progress=progress,cancel=lambda: stopped[0])
    assert dst.read_bytes() == b"original output"
    assert not list(tmp_path.glob(".niyomsil*"))


def test_insufficient_disk_preserves_pixel_request(adapter, monkeypatch, tmp_path):
    monkeypatch.setattr(large_image, "IN_MEMORY_PIXELS", 1)
    monkeypatch.setattr(large_image.shutil,"disk_usage",lambda path: SimpleNamespace(free=0))
    src,_ = source_file(tmp_path)
    with pytest.raises(OSError, match="พื้นที่ดิสก์ไม่พอ"):
        adapter.process(src,tmp_path/"out.png",settings_for((200,100)),use_ai=False)
    assert not (tmp_path/"out.png").exists() and not list(tmp_path.glob(".niyomsil*"))


def test_jpeg_format_limit_does_not_change_requested_size(adapter, tmp_path):
    src,_ = source_file(tmp_path)
    with pytest.raises(ValueError, match="PNG, TIFF หรือ PDF"):
        adapter.process(src,tmp_path/"out.jpg",settings_for((80_000,2)),use_ai=False)
    assert not (tmp_path/"out.jpg").exists()


def test_bigtiff_is_valid_and_retains_dpi(adapter, monkeypatch, tmp_path):
    monkeypatch.setattr(large_image,"IN_MEMORY_PIXELS",1)
    monkeypatch.setattr(large_image,"TIFF_BIG_THRESHOLD_BYTES",1)
    src,_ = source_file(tmp_path)
    dst = tmp_path/"big.tif"
    adapter.process(src,dst,settings_for((64,32)),use_ai=False)
    assert dst.read_bytes()[:4] in (b"II+\x00",b"MM\x00+")
    with Image.open(dst) as output:
        assert output.size == (64,32) and output.info["dpi"] == (300,300)


def test_pdf_tiles_reconstruct_exact_pixels_and_large_physical_page(tmp_path):
    from signprint_ai.large_pdf import save_pdf
    pixels = np.arange(2080*1100*3,dtype="uint32").reshape(1100,2080,3).astype("uint8")
    image = large_image.vips().Image.new_from_memory(pixels.tobytes(),2080,1100,3,"uchar")
    dst = tmp_path/"banner.pdf"
    save_pdf(image,dst,dpi=1)
    page = PdfReader(dst).pages[0]
    assert page.get("/UserUnit") > 1
    assert float(page.mediabox.width)*page["/UserUnit"] == pytest.approx(2080*72)
    restored = np.empty_like(pixels)
    count = 0
    for y in range(0,1100,512):
        for x in range(0,2080,1024):
            tile = np.asarray(page.images[f"/Im{count}"].image)
            restored[y:y+tile.shape[0],x:x+tile.shape[1]] = tile
            count += 1
    np.testing.assert_array_equal(restored,pixels)
    assert count == 9 and page.get_contents().get_data().count(b" Do Q") == 9


@pytest.mark.parametrize("view", ["fit","actual","zoom"])
def test_lazy_viewport_keeps_real_dimensions_and_only_allocates_panel(monkeypatch,tmp_path,view):
    monkeypatch.setattr(large_image,"IN_MEMORY_PIXELS",1)
    src = tmp_path/"in.png"
    Image.new("RGB",(1000,600),(13,81,207)).save(src)
    source = large_image.preview_source(src)
    assert isinstance(source,large_image.LazyPreviewSource) and source.size == (1000,600)
    viewport = PreviewViewport()
    if view == "actual":
        viewport.one_to_one()
    elif view == "zoom":
        viewport.magnify(2)
    output = viewport.render(source,(120,80))
    assert output.size == (120,80) and output.getpixel((60,40)) == (13,81,207)


def test_large_protect_uses_source_detail_without_full_face_canvas(adapter,monkeypatch,tmp_path):
    monkeypatch.setattr(large_image,"IN_MEMORY_PIXELS",1)
    src = tmp_path/"face.png"
    Image.new("RGB",(20,20),(210,91,43)).save(src)
    engine = SimpleNamespace(upsampler=SimpleNamespace(tile_size=8,tile_pad=3),
        enhance_tile=lambda tile,scale,cancel: np.zeros((tile.shape[0]*scale,tile.shape[1]*scale,3),dtype="uint8"),
        device_name=lambda: "CPU")
    adapter.engine_manager.create_engine=lambda device: engine
    result=adapter.process(src,tmp_path/"protected.png",EnhanceSettings(ai_scale=4,face_protection=True,
                                               face_regions=((.2,.2,.6,.6),),face_mode="protect"))
    assert result["face_protection"]["applied"] and result["face_protection"]["face_count"] == 1
    with Image.open(result["output"]) as output:
        assert output.getpixel((32,32)) == (210,91,43)
        assert output.getpixel((72,72)) == (0,0,0)


@pytest.mark.parametrize("width,height,dpi", [(float("nan"),10,300),(10,float("inf"),300),(0,10,300),(10,10,0)])
def test_invalid_print_settings_fail_clearly(adapter,tmp_path,width,height,dpi):
    src,_=source_file(tmp_path)
    with pytest.raises(ValueError):
        adapter.process(src,tmp_path/"out.png",EnhanceSettings(print_width=width,print_height=height,dpi=dpi),use_ai=False)
