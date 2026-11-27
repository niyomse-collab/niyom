"""Regression tests for disk-backed four-engine native tile orchestration."""
import hashlib

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

def _sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _observed_processors(observation):
    base = _processors()

    def wrap(name):
        def process(source, destination):
            with Image.open(source) as image:
                observation["input_sizes"].append(image.size)
            observation["active"] += 1
            observation["max_active"] = max(
                observation["max_active"], observation["active"]
            )
            try:
                base[name](source, destination)
                with Image.open(destination) as output:
                    observation["output_sizes"].append(output.size)
            finally:
                observation["active"] -= 1
        return process

    return {name: wrap(name) for name in ENGINES}


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
    # Initial preflight, engine 0, then one fail-closed check for engine 1.
    assert checks["count"] == 3
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



def test_streamed_rgba_seed_bleeds_only_fully_transparent_hidden_rgb(tmp_path):
    """Large-job seed preparation must match V2's alpha-safe small-image path."""
    pytest.importorskip("pyvips")
    from signprint_ai.v211_large_image_bridge import prepare_native_2x_inputs_streamed

    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    rgba = np.zeros((128, 128, 4), dtype=np.uint8)
    rgba[..., :3] = (0, 0, 0)
    rgba[32:96, 32:96, :3] = (220, 70, 40)
    rgba[32:96, 32:96, 3] = 255
    # A non-zero partial-alpha edge pixel is still visible and its RGB must
    # remain exact; only pixels with alpha == 0 may receive colour bleed.
    rgba[64, 40, :3] = (13, 201, 77)
    rgba[64, 40, 3] = 128
    source = tmp_path / "transparent-source.png"
    Image.fromarray(rgba, "RGBA").save(
        source, dpi=(300, 300), icc_profile=profile
    )
    with Image.open(source) as image:
        v2_image = image.resize((256, 256), Image.Resampling.LANCZOS)
        baseline = tmp_path / "accepted-v2.png"
        v2_image.save(baseline, dpi=(300, 300), icc_profile=profile)
        v2_image.close()

    accepted_v2_bytes = baseline.read_bytes()
    work_dir = tmp_path / "streamed-seed-work"
    seed_path = reference_path = None
    try:
        seed_path, reference_path, target_size, padded_size, source_size, metadata = (
            prepare_native_2x_inputs_streamed(
                source, baseline, work_dir, resize_mode="stretch"
            )
        )
        assert source_size == (128, 128)
        assert target_size == padded_size == (256, 256)
        assert metadata["icc_profile"] == profile
        assert metadata["dpi"][0] == pytest.approx(300, abs=0.1)

        with Image.open(seed_path) as seed:
            pixels = np.asarray(seed).copy()
            assert seed.mode == "RGBA"
            # x=31 is fully transparent but immediately adjacent to the
            # visible square. Its hidden RGB should be foreground-colour
            # propagated, not the original black matte.
            assert tuple(pixels[64, 31, :3]) == pytest.approx((220, 70, 40), abs=8)
            # Visible opaque and partially transparent source RGB must
            # remain byte-identical; only alpha==0 pixels are repaired.
            np.testing.assert_array_equal(pixels[64, 64, :3], (220, 70, 40))
            np.testing.assert_array_equal(pixels[64, 40, :3], (13, 201, 77))
            assert seed.info["icc_profile"] == profile
            assert seed.info["dpi"][0] == pytest.approx(300, abs=0.1)

        assert baseline.read_bytes() == accepted_v2_bytes
    finally:
        if seed_path is not None:
            seed_path.unlink(missing_ok=True)
        if reference_path is not None:
            reference_path.unlink(missing_ok=True)


def test_tiled_runner_checks_nearest_existing_output_ancestor_for_disk_space(
    tmp_path, monkeypatch
):
    from pathlib import Path
    from types import SimpleNamespace
    import tools.v211_four_engine_tiled_inference as tiled

    source = tmp_path / "source.png"
    Image.new("RGB", (64, 64), (20, 40, 60)).save(source)
    v2 = tmp_path / "v2.png"
    Image.new("RGB", (128, 128), (20, 40, 60)).save(v2)

    # The output's immediate parent does not exist yet. Disk capacity must be
    # queried on the nearest existing ancestor on that same destination volume,
    # never on an unrelated process working directory.
    output_volume = tmp_path / "output-volume"
    output_volume.mkdir()
    output = output_volume / "not-created-yet" / "four-engine-output"
    observed_paths = []

    def disk_usage(path):
        observed_paths.append(Path(path))
        return SimpleNamespace(free=0)

    monkeypatch.setattr(tiled.shutil, "disk_usage", disk_usage)
    with pytest.raises(RuntimeError, match="four native candidates and fusion workspace"):
        run_tiled_candidates(
            source, v2, output, (128, 128), _processors(),
            tile_size=64, overlap=8,
        )

    assert observed_paths == [output_volume]
    assert not output.exists()




def test_streamed_seed_maps_four_x_print_target_to_native_two_x_seed(tmp_path):
    """A 4x print target is prepared as a half-target seed for one native 2x pass."""
    pytest.importorskip("pyvips")
    from signprint_ai.v211_large_image_bridge import prepare_native_2x_inputs_streamed

    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    source = tmp_path / "source-1500x1000.png"
    baseline = tmp_path / "accepted-v2-6000x4000.png"
    Image.new("RGB", (1500, 1000), (38, 82, 126)).save(
        source, format="PNG", dpi=(300, 300), icc_profile=profile
    )
    # 24 MP target: four times the original dimensions in each axis.
    Image.new("RGB", (6000, 4000), (38, 82, 126)).save(
        baseline, format="PNG", dpi=(300, 300), icc_profile=profile
    )
    accepted_v2_bytes = baseline.read_bytes()
    seed_path = reference_path = None
    try:
        seed_path, reference_path, target_size, padded_size, source_size, metadata = (
            prepare_native_2x_inputs_streamed(
                source, baseline, tmp_path / "four-x-seed-work",
                resize_mode="stretch",
            )
        )
        assert source_size == (1500, 1000)
        assert target_size == padded_size == (6000, 4000)
        assert metadata["icc_profile"] == profile

        # The bridge resamples the source to half the final target, then all
        # four native engines perform one exact 2x pass over bounded tiles.
        with Image.open(seed_path) as seed:
            assert seed.size == (3000, 2000)
            assert seed.mode == "RGB"
            assert seed.info["icc_profile"] == profile
            assert seed.info["dpi"][0] == pytest.approx(300, abs=0.1)
        with Image.open(reference_path) as reference:
            assert reference.size == (6000, 4000)
            assert reference.mode == "RGB"
            assert reference.info["icc_profile"] == profile
        assert baseline.read_bytes() == accepted_v2_bytes
    finally:
        if seed_path is not None:
            seed_path.unlink(missing_ok=True)
        if reference_path is not None:
            reference_path.unlink(missing_ok=True)



def test_four_x_print_target_runs_disk_tiled_native_two_x_from_half_target_seed(tmp_path):
    """A 4x print canvas must flow through the same bounded 2x tile runner."""
    pytest.importorskip("pyvips")
    from signprint_ai.v211_large_image_bridge import prepare_native_2x_inputs_streamed

    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    source = tmp_path / "four-x-original.png"
    baseline = tmp_path / "four-x-accepted-v2.png"
    Image.new("RGB", (64, 64), (38, 82, 126)).save(
        source, format="PNG", dpi=(300, 300), icc_profile=profile
    )
    Image.new("RGB", (256, 256), (38, 82, 126)).save(
        baseline, format="PNG", dpi=(300, 300), icc_profile=profile
    )
    accepted_v2_bytes = baseline.read_bytes()
    seed_path = reference_path = None
    try:
        seed_path, reference_path, target_size, padded_size, source_size, metadata = (
            prepare_native_2x_inputs_streamed(
                source, baseline, tmp_path / "four-x-tiled-work",
                resize_mode="stretch",
            )
        )
        assert source_size == (64, 64)
        assert target_size == padded_size == (256, 256)
        assert metadata["icc_profile"] == profile
        with Image.open(seed_path) as seed:
            assert seed.size == (128, 128)
            assert seed.info["icc_profile"] == profile
            assert seed.info["dpi"][0] == pytest.approx(300, abs=0.1)

        result = run_tiled_candidates(
            seed_path,
            reference_path,
            tmp_path / "four-x-tiled-candidates",
            target_size,
            _processors(),
            tile_size=64,
            overlap=8,
        )
        assert result["ready_for_fusion_research"] is True
        assert result["native_tiled_inference"]["native_scale"] == 2
        assert result["native_tiled_inference"]["all_four_engines_completed"] is True
        for name in ENGINES:
            candidate = tmp_path / "four-x-tiled-candidates" / (name + ".png")
            with Image.open(candidate) as output:
                assert output.size == (256, 256)
                assert output.mode == "RGB"
                assert output.info["icc_profile"] == profile
                assert output.info["dpi"][0] == pytest.approx(300, abs=0.1)
        assert baseline.read_bytes() == accepted_v2_bytes
    finally:
        if seed_path is not None:
            seed_path.unlink(missing_ok=True)
        if reference_path is not None:
            reference_path.unlink(missing_ok=True)


def test_large_four_x_target_runs_all_four_tiled_passes_and_disk_backed_fusion(
    tmp_path, monkeypatch
):
    """Exercise the complete synthetic 4x (>18 MP) path without full Pillow decode."""
    pytest.importorskip("pyvips")
    from signprint_ai.v211_large_image_bridge import prepare_native_2x_inputs_streamed
    from tools.v211_four_engine_fusion import fuse_four_engine_details

    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    source = tmp_path / "source-1500x1000.png"
    baseline = tmp_path / "accepted-v2-6000x4000.png"
    Image.new("RGB", (1500, 1000), (38, 82, 126)).save(
        source, format="PNG", dpi=(300, 300), icc_profile=profile
    )
    # The print target is 4x the source in each axis and exceeds 18 MP.
    Image.new("RGB", (6000, 4000), (38, 82, 126)).save(
        baseline, format="PNG", dpi=(300, 300), icc_profile=profile
    )
    source_before = _sha256_file(source)
    baseline_before = _sha256_file(baseline)

    original_load = PngImagePlugin.PngImageFile.load

    def reject_large_pillow_decode(image, *args, **kwargs):
        if image.width * image.height > 18_000_000:
            raise AssertionError("large four-engine path must remain disk-backed")
        return original_load(image, *args, **kwargs)

    monkeypatch.setattr(
        PngImagePlugin.PngImageFile, "load", reject_large_pillow_decode
    )

    work_dir = tmp_path / "large-four-x-work"
    candidates_dir = tmp_path / "large-four-x-candidates"
    seed_path = reference_path = None
    try:
        seed_path, reference_path, target_size, padded_size, source_size, metadata = (
            prepare_native_2x_inputs_streamed(
                source, baseline, work_dir, resize_mode="stretch"
            )
        )
        assert source_size == (1500, 1000)
        assert target_size == padded_size == (6000, 4000)
        assert metadata["icc_profile"] == profile
        with Image.open(seed_path) as seed:
            assert seed.size == (3000, 2000)
            assert seed.mode == "RGB"
            assert seed.info["icc_profile"] == profile
            assert seed.info["dpi"][0] == pytest.approx(300, abs=0.1)

        # Four synthetic processors each perform one native-equivalent 2x tile
        # pass over the half-target seed. This validates geometry/streaming only.
        # Record every native input/output tile to prove the 24 MP print raster
        # is never handed to a processor as one full-frame allocation.
        observation = {
            "input_sizes": [], "output_sizes": [], "active": 0, "max_active": 0,
        }
        tiled = run_tiled_candidates(
            seed_path, reference_path, candidates_dir, target_size,
            _observed_processors(observation),
            tile_size=1024, overlap=32,
        )
        assert tiled["ready_for_fusion_research"] is True
        assert tiled["native_tiled_inference"]["all_four_engines_completed"] is True
        assert tiled["native_tiled_inference"]["native_scale"] == 2
        assert len(observation["input_sizes"]) == 24
        assert len(observation["output_sizes"]) == 24
        assert observation["max_active"] == 1
        resource_bounds = tiled["native_tiled_inference"]["resource_bounds"]
        assert resource_bounds["concurrent_native_processes"] == 1
        assert resource_bounds["measurement_scope"] == "tile_geometry_only_not_process_rss_or_vram"
        assert resource_bounds["max_input_tile_width"] <= 1024 + 2 * 32
        assert resource_bounds["max_input_tile_height"] <= 1024 + 2 * 32
        assert resource_bounds["max_input_tile_pixels"] <= (1024 + 2 * 32) ** 2
        assert resource_bounds["max_output_tile_width"] <= 2 * (1024 + 2 * 32)
        assert resource_bounds["max_output_tile_height"] <= 2 * (1024 + 2 * 32)
        assert resource_bounds["max_output_tile_pixels"] <= (2 * (1024 + 2 * 32)) ** 2
        assert max(width for width, _ in observation["input_sizes"]) <= 1088
        assert max(height for _, height in observation["input_sizes"]) <= 1088
        assert max(width for width, _ in observation["output_sizes"]) <= 2176
        assert max(height for _, height in observation["output_sizes"]) <= 2176
        for name in ENGINES:
            candidate = candidates_dir / (name + ".png")
            with Image.open(candidate) as image:
                assert image.size == (6000, 4000)
                assert image.mode == "RGB"
                assert image.info["icc_profile"] == profile
                assert image.info["dpi"][0] == pytest.approx(300, abs=0.1)
            engine = tiled["native_tiled_inference"]["engine_results"][name]
            assert engine["tile_count"] == 6
            assert engine["seam_validation"] == "passed"

        qa_output = tmp_path / "private-qa" / "large-four-x.V211-4AI-QA.png"
        fused = fuse_four_engine_details(
            source, reference_path,
            {name: candidates_dir / (name + ".png") for name in ENGINES},
            qa_output,
        )
        assert fused["all_four_engine_candidates_consumed"] is True
        assert fused["v2_file_not_modified"] is True
        assert fused["quality_certified"] is False
        assert fused["experimental_preview_only"] is True
        # A perfectly flat field has no eligible V2 edge; fusion must not add
        # texture/noise just because four candidate files exist.
        assert fused["all_four_engine_pixels_contributed"] is False
        assert all(
            fused["engine_pixel_effect_verified"][name] is False
            for name in ENGINES
        )
        with Image.open(qa_output) as image:
            assert image.size == (6000, 4000)
            assert image.mode == "RGB"
            assert image.info["icc_profile"] == profile
            assert image.info["dpi"][0] == pytest.approx(300, abs=0.1)

        # Read one pixel through libvips; never materialize the 24 MP raster.
        import pyvips
        qa_vips = pyvips.Image.new_from_file(str(qa_output), access="random")
        v2_vips = pyvips.Image.new_from_file(str(reference_path), access="random")
        assert bytes(qa_vips.crop(0, 0, 1, 1).write_to_memory()) == bytes(
            v2_vips.crop(0, 0, 1, 1).write_to_memory()
        )
        assert _sha256_file(source) == source_before
        assert _sha256_file(baseline) == baseline_before
    finally:
        if seed_path is not None:
            seed_path.unlink(missing_ok=True)
        if reference_path is not None:
            reference_path.unlink(missing_ok=True)



def test_large_four_x_cancellation_discards_partial_tiles_and_preserves_v2(tmp_path):
    """A cancelled 24 MP / 4x job must leave no partial candidate or V2 edit."""
    pytest.importorskip("pyvips")
    from signprint_ai.v211_large_image_bridge import prepare_native_2x_inputs_streamed

    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    source = tmp_path / "cancel-source-1500x1000.png"
    baseline = tmp_path / "cancel-accepted-v2-6000x4000.png"
    Image.new("RGB", (1500, 1000), (38, 82, 126)).save(
        source, format="PNG", dpi=(300, 300), icc_profile=profile
    )
    Image.new("RGB", (6000, 4000), (38, 82, 126)).save(
        baseline, format="PNG", dpi=(300, 300), icc_profile=profile
    )
    source_before = _sha256_file(source)
    baseline_before = _sha256_file(baseline)
    work_dir = tmp_path / "cancel-large-four-x-work"
    output_dir = tmp_path / "cancel-large-four-x-candidates"
    seed_path = reference_path = None
    calls = []
    checks = {"count": 0}

    def cancel_after_one_native_tile():
        checks["count"] += 1
        return checks["count"] >= 3

    base = _processors()
    processors = {
        name: (lambda src, dst, name=name: (calls.append(name), base[name](src, dst))[1])
        for name in ENGINES
    }
    try:
        seed_path, reference_path, target_size, padded_size, _, _ = (
            prepare_native_2x_inputs_streamed(
                source, baseline, work_dir, resize_mode="stretch"
            )
        )
        assert target_size == padded_size == (6000, 4000)
        with Image.open(seed_path) as seed:
            assert seed.size == (3000, 2000)

        with pytest.raises(InterruptedError, match="stopped by user"):
            run_tiled_candidates(
                seed_path, reference_path, output_dir, target_size, processors,
                tile_size=1024, overlap=32,
                cancel_check=cancel_after_one_native_tile,
            )

        assert checks["count"] == 3
        assert calls == [ENGINES[0]]
        assert not list(output_dir.glob("*.png"))
        assert not list(output_dir.glob(".v211_*"))
        assert _sha256_file(source) == source_before
        assert _sha256_file(baseline) == baseline_before
    finally:
        if seed_path is not None:
            seed_path.unlink(missing_ok=True)
        if reference_path is not None:
            reference_path.unlink(missing_ok=True)



def test_large_rgba_four_x_tiled_inference_fusion_preserves_exact_v2_alpha_icc_dpi_and_cancel(
    tmp_path, monkeypatch
):
    """Exercise >18 MP RGBA through seed, four 2x tile engines, fusion and cancel.

    Pixels are synthetic and constant-colour so this is a geometry/metadata/
    alpha-integrity test, not a visual-quality or real-GPU inference claim.
    """
    pytest.importorskip("pyvips")
    from PIL import ImageDraw
    import pyvips
    from signprint_ai.v211_large_image_bridge import prepare_native_2x_inputs_streamed
    from tools.v211_four_engine_fusion import fuse_four_engine_details

    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    source_size = (1500, 1000)
    target_size = (6000, 4000)
    source = tmp_path / "source-rgba-1500x1000.png"
    baseline = tmp_path / "accepted-v2-rgba-6000x4000.png"

    def write_rgba(path, size):
        width, height = size
        image = Image.new("RGBA", size, (218, 73, 41, 0))
        alpha = Image.new("L", size, 0)
        draw = ImageDraw.Draw(alpha)
        draw.rectangle(
            (width // 8, height // 8, width * 7 // 8 - 1, height * 7 // 8 - 1),
            fill=255,
        )
        draw.rectangle(
            (width // 3, height // 3, width * 2 // 3 - 1, height * 2 // 3 - 1),
            fill=128,
        )
        image.putalpha(alpha)
        image.save(path, format="PNG", dpi=(300, 300), icc_profile=profile)
        image.close()
        alpha.close()

    write_rgba(source, source_size)
    write_rgba(baseline, target_size)
    source_before = _sha256_file(source)
    baseline_before = _sha256_file(baseline)

    # The large source and accepted V2 must never be decoded into one Pillow
    # frame. Tile candidates are allowed to decode only their bounded regions.
    original_load = PngImagePlugin.PngImageFile.load

    def reject_large_master_decode(image, *args, **kwargs):
        if image.filename in (str(source), str(baseline)) and image.width * image.height > 18_000_000:
            raise AssertionError("large RGBA masters must remain disk-backed")
        return original_load(image, *args, **kwargs)

    monkeypatch.setattr(PngImagePlugin.PngImageFile, "load", reject_large_master_decode)

    work_dir = tmp_path / "rgba-four-x-work"
    candidates_dir = tmp_path / "rgba-four-x-candidates"
    qa_output = tmp_path / "private-rgba-qa" / "large-rgba-four-x.V211-4AI-QA.png"
    seed_path = reference_path = None
    try:
        seed_path, reference_path, actual_target, padded_size, actual_source, metadata = (
            prepare_native_2x_inputs_streamed(
                source, baseline, work_dir, resize_mode="stretch"
            )
        )
        assert actual_source == source_size
        assert actual_target == padded_size == target_size
        assert metadata["icc_profile"] == profile
        assert metadata["dpi"][0] == pytest.approx(300, abs=0.1)
        with Image.open(seed_path) as seed:
            assert seed.size == (3000, 2000)
            assert seed.mode == "RGBA"
            assert seed.info["icc_profile"] == profile
            assert seed.info["dpi"][0] == pytest.approx(300, abs=0.1)
            # Fully transparent hidden RGB is safely bled from the visible
            # foreground; a partially transparent pixel remains meaningful.
            assert seed.getpixel((300, 1000))[3] == 0
            assert seed.getpixel((1500, 1000))[3] in (127, 128, 129)

        observation = {
            "input_sizes": [], "output_sizes": [], "active": 0, "max_active": 0,
        }
        tiled = run_tiled_candidates(
            seed_path, reference_path, candidates_dir, target_size,
            _observed_processors(observation),
            tile_size=1024, overlap=32,
        )
        assert tiled["ready_for_fusion_research"] is True
        assert tiled["native_tiled_inference"]["all_four_engines_completed"] is True
        assert tiled["native_tiled_inference"]["native_scale"] == 2
        assert observation["max_active"] == 1
        assert len(observation["input_sizes"]) == 24
        assert max(width for width, _ in observation["input_sizes"]) <= 1088
        assert max(height for _, height in observation["input_sizes"]) <= 1088
        for name in ENGINES:
            candidate = candidates_dir / (name + ".png")
            with Image.open(candidate) as image:
                assert image.size == target_size
                assert image.mode == "RGBA"
                assert image.info["icc_profile"] == profile
                assert image.info["dpi"][0] == pytest.approx(300, abs=0.1)
            result = tiled["native_tiled_inference"]["engine_results"][name]
            assert result["tile_count"] == 6
            assert result["seam_validation"] == "passed"

        fused = fuse_four_engine_details(
            source, reference_path,
            {name: candidates_dir / (name + ".png") for name in ENGINES},
            qa_output,
        )
        assert fused["all_four_engine_candidates_consumed"] is True
        assert fused["v2_file_not_modified"] is True
        assert fused["quality_certified"] is False
        assert fused["experimental_preview_only"] is True
        with Image.open(qa_output) as preview:
            assert preview.size == target_size
            assert preview.mode == "RGBA"
            assert preview.info["icc_profile"] == profile
            assert preview.info["dpi"][0] == pytest.approx(300, abs=0.1)

        # Compare every alpha sample in bounded row strips against accepted V2.
        # No Pillow full-frame decode is used for either 24 MP image.
        qa_vips = pyvips.Image.new_from_file(str(qa_output), access="random", fail_on="error")
        v2_vips = pyvips.Image.new_from_file(str(reference_path), access="random", fail_on="error")
        assert qa_vips.bands == v2_vips.bands == 4
        qa_alpha = qa_vips.extract_band(3)
        v2_alpha = v2_vips.extract_band(3)
        for y in range(0, target_size[1], 256):
            height = min(256, target_size[1] - y)
            for x in range(0, target_size[0], 1024):
                width = min(1024, target_size[0] - x)
                assert bytes(qa_alpha.crop(x, y, width, height).write_to_memory()) == bytes(
                    v2_alpha.crop(x, y, width, height).write_to_memory()
                )
        # Transparent outside, partially transparent centre, and opaque field
        # are all represented in the accepted alpha plane and retained exactly.
        assert bytes(qa_alpha.crop(0, 0, 1, 1).write_to_memory()) == bytes([0])
        assert bytes(qa_alpha.crop(600, 600, 1, 1).write_to_memory()) == bytes([255])
        assert _sha256_file(source) == source_before
        assert _sha256_file(baseline) == baseline_before

        # Repeat the same RGBA large-job route with cancellation after the first
        # native tile. No partial candidates, work rasters or accepted-V2 edits
        # may survive the cancelled transaction.
        cancel_dir = tmp_path / "rgba-cancelled-candidates"
        calls = []
        checks = {"count": 0}
        base = _processors()

        def cancel_after_first_native_tile():
            checks["count"] += 1
            return checks["count"] >= 3

        def wrap(name):
            def process(src, dst):
                calls.append(name)
                base[name](src, dst)
            return process

        with pytest.raises(InterruptedError, match="stopped by user"):
            run_tiled_candidates(
                seed_path, reference_path, cancel_dir, target_size,
                {name: wrap(name) for name in ENGINES},
                tile_size=1024, overlap=32,
                cancel_check=cancel_after_first_native_tile,
            )
        assert checks["count"] == 3
        assert calls == [ENGINES[0]]
        assert not list(cancel_dir.glob("*.png"))
        assert not list(cancel_dir.glob(".v211_*"))
        assert _sha256_file(source) == source_before
        assert _sha256_file(baseline) == baseline_before
    finally:
        if seed_path is not None:
            seed_path.unlink(missing_ok=True)
        if reference_path is not None:
            reference_path.unlink(missing_ok=True)
