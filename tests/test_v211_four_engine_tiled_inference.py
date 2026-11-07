"""Regression tests for disk-backed four-engine native tile orchestration."""
import pytest
from PIL import Image, ImageCms, PngImagePlugin
import numpy as np

from tools.v211_four_engine_coordinator import ENGINES
from tools.v211_four_engine_tiled_inference import run_tiled_candidates


pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


def _processors(*, drop_alpha=False, corrupt_right_seam=False):
    def process(source, destination):
        with Image.open(source) as image:
            output = image.convert("RGB") if drop_alpha else image.copy()
            output = output.resize(
                (image.width * 2, image.height * 2),
                resample=Image.Resampling.NEAREST,
            )
            if corrupt_right_seam and "tile-r0-c1" in source.name:
                pixels = np.asarray(output).copy()
                pixels[:, 16:18, :3] = 250
                output = Image.fromarray(pixels, "RGB")
            options = {}
            if image.info.get("icc_profile") is not None:
                options["icc_profile"] = image.info["icc_profile"]
            if image.info.get("dpi") is not None:
                options["dpi"] = image.info["dpi"]
            output.save(destination, format="PNG", **options)
            output.close()
    return {name: process for name in ENGINES}


def test_tiled_runner_reserves_all_candidate_and_fusion_disk_before_native_launch(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import tools.v211_four_engine_tiled_inference as tiled

    source = tmp_path / "source.png"
    Image.new("RGB", (64, 64), (20, 40, 60)).save(source)
    v2 = tmp_path / "v2.png"
    Image.new("RGB", (128, 128), (20, 40, 60)).save(v2)
    raw_bytes = 128 * 128 * 3
    # Enough for the old two-raster check, but not for four candidate
    # rasters plus the raw fusion and atomic PNG workspace.
    monkeypatch.setattr(
        tiled.shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(free=64 * 1024 * 1024 + raw_bytes * 5),
    )
    calls = []
    processors = {name: lambda _src, _dst: calls.append(name) for name in ENGINES}
    output = tmp_path / "low-disk-output"

    with pytest.raises(RuntimeError, match="four native candidates and fusion workspace"):
        run_tiled_candidates(
            source, v2, output, (128, 128), processors,
            tile_size=64, overlap=8,
        )

    assert calls == []
    assert not output.exists()


def test_tiled_runner_rechecks_disk_before_each_remaining_engine(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import tools.v211_four_engine_tiled_inference as tiled

    pytest.importorskip("pyvips")
    source = tmp_path / "source.png"
    Image.new("RGB", (64, 64), (20, 40, 60)).save(source)
    v2 = tmp_path / "v2.png"
    Image.new("RGB", (128, 128), (20, 40, 60)).save(v2)
    raw_bytes = 128 * 128 * 3
    checks = {"count": 0}

    def disk_usage(_path):
        checks["count"] += 1
        # After engine 0 is saved, 6.5 raster equivalents remain. The old
        # shrinking formula incorrectly reduced the reserve to 6 and launched
        # engine 1 even though engine 0's candidate still occupied disk space.
        free = (
            64 * 1024 * 1024 + raw_bytes * 8
            if checks["count"] <= 2
            else 64 * 1024 * 1024 + raw_bytes * 6 + raw_bytes // 2
        )
        return SimpleNamespace(free=free)

    monkeypatch.setattr(tiled.shutil, "disk_usage", disk_usage)
    base = _processors()
    calls = []

    def wrap(name):
        def process(src, dst):
            calls.append(name)
            if name == ENGINES[0]:
                # Make the retained first candidate nearly incompressible so
                # its real on-disk bytes must be included in the next reserve.
                with Image.open(src) as image:
                    shape = (image.height * 2, image.width * 2, 3)
                noise = np.random.default_rng(7).integers(
                    0, 256, size=shape, dtype=np.uint8
                )
                Image.fromarray(noise).save(dst, format="PNG")
            else:
                base[name](src, dst)
        return process

    processors = {name: wrap(name) for name in ENGINES}
    output = tmp_path / "disk-drops-mid-run"
    result = run_tiled_candidates(
        source, v2, output, (128, 128), processors,
        tile_size=64, overlap=8,
    )

    assert calls == [ENGINES[0]]
    # Initial preflight, engine 0, then one recheck for each rejected engine.
    assert checks["count"] == 5
    assert result["ready_for_fusion_research"] is False
    assert [item.engine for item in result["candidates"]] == [ENGINES[0]]
    assert set(result["failures"]) == set(ENGINES[1:])
    first_candidate = output / (ENGINES[0] + ".png")
    assert first_candidate.is_file()
    assert first_candidate.stat().st_size > raw_bytes // 2
    assert not any((output / (name + ".png")).exists() for name in ENGINES[1:])


def test_tiled_native_candidates_stitch_exact_2x_pixels_and_metadata(tmp_path):
    pytest.importorskip("pyvips")
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    source = tmp_path / "source.png"
    pixels = np.zeros((128, 130, 3), dtype=np.uint8)
    pixels[..., 0] = np.arange(130, dtype=np.uint8)[None, :]
    pixels[..., 1] = np.arange(128, dtype=np.uint8)[:, None]
    pixels[..., 2] = 73
    Image.fromarray(pixels, "RGB").save(
        source, dpi=(300, 300), icc_profile=profile
    )
    with Image.open(source) as image:
        expected = image.resize((260, 256), Image.Resampling.NEAREST)
        v2 = tmp_path / "accepted-v2.png"
        expected.save(v2, dpi=(300, 300), icc_profile=profile)
        expected.close()

    original_load = PngImagePlugin.PngImageFile.load

    def reject_full_raster_decode(image, *args, **kwargs):
        if image.size in ((130, 128), (260, 256)):
            raise AssertionError("native tile path must not decode a full source/V2 raster")
        return original_load(image, *args, **kwargs)

    with pytest.MonkeyPatch.context() as patcher:
        patcher.setattr(PngImagePlugin.PngImageFile, "load", reject_full_raster_decode)
        result = run_tiled_candidates(
            source, v2, tmp_path / "candidates", (260, 256), _processors(),
            tile_size=64, overlap=8,
        )

    assert result["ready_for_fusion_research"] is True
    assert result["native_tiled_inference"]["all_four_engines_completed"] is True
    assert result["native_tiled_inference"]["native_scale"] == 2
    for name in ENGINES:
        candidate = tmp_path / "candidates" / (name + ".png")
        with Image.open(candidate) as actual, Image.open(v2) as reference:
            np.testing.assert_array_equal(np.asarray(actual), np.asarray(reference))
            assert actual.info["icc_profile"] == profile
            assert actual.info["dpi"][0] == pytest.approx(300, abs=0.1)
        engine = result["native_tiled_inference"]["engine_results"][name]
        assert engine["status"] == "stitched"
        assert engine["tile_count"] == 6
        assert engine["seam_count"] == 7
        assert engine["seam_validation"] == "passed"


def test_tiled_rgba_candidate_uses_accepted_v2_alpha_not_engine_alpha(tmp_path):
    pytest.importorskip("pyvips")
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    source = tmp_path / "source-rgba.png"
    rgba = np.zeros((128, 128, 4), dtype=np.uint8)
    rgba[..., 0] = 40
    rgba[..., 1] = 90
    rgba[..., 2] = 140
    rgba[..., 3] = 255
    rgba[::3, ::5, 3] = 128
    rgba[1::7, 2::9, 3] = 0
    Image.fromarray(rgba, "RGBA").save(
        source, dpi=(300, 300), icc_profile=profile
    )
    with Image.open(source) as image:
        v2_image = image.resize((256, 256), Image.Resampling.LANCZOS)
        v2 = tmp_path / "accepted-v2-rgba.png"
        v2_image.save(v2, dpi=(300, 300), icc_profile=profile)
        expected_alpha = np.asarray(v2_image.getchannel("A")).copy()
        v2_image.close()

    result = run_tiled_candidates(
        source, v2, tmp_path / "rgba-candidates", (256, 256),
        _processors(drop_alpha=True), tile_size=64, overlap=8,
    )

    assert result["ready_for_fusion_research"] is True
    for name in ENGINES:
        with Image.open(tmp_path / "rgba-candidates" / (name + ".png")) as output:
            assert output.mode == "RGBA"
            np.testing.assert_array_equal(
                np.asarray(output.getchannel("A")), expected_alpha
            )
            assert output.info["icc_profile"] == profile
            assert output.info["dpi"][0] == pytest.approx(300, abs=0.1)


def test_tiled_native_candidate_is_rejected_on_seam_disagreement(tmp_path):
    pytest.importorskip("pyvips")
    source = tmp_path / "source.png"
    Image.new("RGB", (128, 128), (20, 40, 60)).save(source)
    v2 = tmp_path / "v2.png"
    Image.new("RGB", (256, 256), (20, 40, 60)).save(v2)

    result = run_tiled_candidates(
        source, v2, tmp_path / "seam-failure", (256, 256),
        _processors(corrupt_right_seam=True), tile_size=64, overlap=8,
    )

    assert result["ready_for_fusion_research"] is False
    assert not result["candidates"]
    for name in ENGINES:
        assert name in result["failures"]
        assert result["native_tiled_inference"]["engine_results"][name]["status"] == "rejected"
        assert not (tmp_path / "seam-failure" / (name + ".png")).exists()


def test_tiled_native_cancellation_removes_all_candidate_and_temp_files(tmp_path):
    pytest.importorskip("pyvips")
    source = tmp_path / "source.png"
    Image.new("RGB", (128, 128), (20, 40, 60)).save(source)
    v2 = tmp_path / "v2.png"
    Image.new("RGB", (256, 256), (20, 40, 60)).save(v2)
    checks = {"count": 0}

    def cancel():
        checks["count"] += 1
        return checks["count"] >= 3

    with pytest.raises(InterruptedError, match="stopped"):
        run_tiled_candidates(
            source, v2, tmp_path / "cancelled", (256, 256), _processors(),
            tile_size=64, overlap=8, cancel_check=cancel,
        )

    assert not list((tmp_path / "cancelled").glob("*.png"))
    assert not list((tmp_path / "cancelled").glob(".v211_*"))


@pytest.mark.parametrize(
    "source_size,target_size",
    [((64, 64), (256, 256)), ((64, 64), (128, 64))],
)
def test_tiled_native_rejects_non_single_2x_geometry_before_processor(
    tmp_path, source_size, target_size
):
    source = tmp_path / "source.png"
    Image.new("RGB", source_size, (20, 40, 60)).save(source)
    v2 = tmp_path / "v2.png"
    Image.new("RGB", target_size, (20, 40, 60)).save(v2)
    calls = []
    processors = {
        name: lambda src, dst: calls.append(name) for name in ENGINES
    }
    with pytest.raises(ValueError, match="exact 2x"):
        run_tiled_candidates(
            source, v2, tmp_path / "rejected", target_size, processors,
            tile_size=64, overlap=8,
        )
    assert calls == []
    assert not (tmp_path / "rejected").exists()

def test_tiled_native_runner_stitches_a_real_24mp_target_without_full_pillow_decode(tmp_path):
    pytest.importorskip("pyvips")
    source = tmp_path / "large-source.png"
    v2 = tmp_path / "large-accepted-v2.png"
    Image.new("RGB", (3000, 2000), (34, 76, 118)).save(source)
    Image.new("RGB", (6000, 4000), (34, 76, 118)).save(v2)
    before_v2 = v2.read_bytes()
    original_load = PngImagePlugin.PngImageFile.load

    def reject_full_raster_decode(image, *args, **kwargs):
        if image.size in ((3000, 2000), (6000, 4000)):
            raise AssertionError("24 MP native tile runner must not decode full source/V2")
        return original_load(image, *args, **kwargs)

    with pytest.MonkeyPatch.context() as patcher:
        patcher.setattr(PngImagePlugin.PngImageFile, "load", reject_full_raster_decode)
        result = run_tiled_candidates(
            source, v2, tmp_path / "large-candidates", (6000, 4000),
            _processors(), tile_size=1024, overlap=32,
        )

    assert result["ready_for_fusion_research"] is True
    assert result["native_tiled_inference"]["all_four_engines_completed"] is True
    for name in ENGINES:
        candidate = tmp_path / "large-candidates" / (name + ".png")
        with Image.open(candidate) as image:
            assert image.size == (6000, 4000)
            assert image.mode == "RGB"
        report = result["native_tiled_inference"]["engine_results"][name]
        assert report["tile_count"] == 6
        assert report["seam_count"] == 7
        assert report["seam_validation"] == "passed"
    assert v2.read_bytes() == before_v2
    assert not list((tmp_path / "large-candidates").glob(".v211_*"))

