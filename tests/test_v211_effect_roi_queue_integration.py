"""Per-file styled-effect ROI routing from the UI queue into the V2.1.1 bridge.

These tests use synthetic rasters and fake V2/native runners. They prove only
routing, snapshot isolation, and preservation contracts—not AI quality or GPU use.
"""
from __future__ import annotations

import queue
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image, ImageCms

from signprint_ai import niyomsil_core_adapter as adapter_module
from signprint_ai.niyomsil_core_adapter import NiyomSilpCoreAdapter


def test_queue_snapshots_distinct_effect_rois_for_each_file(tmp_path):
    from signprint_ai.app_v2 import App
    from signprint_ai.v21_graphics_ai import V21Settings

    files = [tmp_path / "sign-a.png", tmp_path / "sign-b.png", tmp_path / "photo-c.png"]
    for index, path in enumerate(files):
        path.write_bytes(("synthetic-" + str(index)).encode("ascii"))

    class QueueHarness:
        _face_key = staticmethod(App._face_key)

        def __init__(self):
            self.files = files
            self._queue_lock = threading.Lock()
            self._active_index = None
            self._queued_indices = set()
            self._completed_indices = set()
            self._face_reviews = {self._face_key(path): () for path in files}
            self._effect_reviews = {
                self._face_key(files[0]): ((0.05, 0.10, 0.45, 0.55),),
                self._face_key(files[1]): ((0.55, 0.20, 0.95, 0.85),),
            }
            self._job_queue = queue.Queue()
            self._reserved_output_paths = set()
            self._events = queue.Queue()

        def _output_path(self, source, _settings):
            return tmp_path / (source.stem + ".accepted-V2.png")

        def _scan_faces(self, source):
            pytest.fail("pre-reviewed synthetic files must not start face scanning")

    harness = QueueHarness()
    queued = App._enqueue_jobs(harness, [0, 1, 2], V21Settings())
    assert queued == 3

    jobs = [harness._job_queue.get_nowait() for _ in range(3)]
    by_index = {index: (source, output, settings) for index, source, output, settings in jobs}

    roi_a = ((0.05, 0.10, 0.45, 0.55),)
    roi_b = ((0.55, 0.20, 0.95, 0.85),)
    assert by_index[0][2].v211_protected_effect_regions == roi_a
    assert by_index[1][2].v211_protected_effect_regions == roi_b
    assert by_index[2][2].v211_protected_effect_regions == ()

    # Changing a review after enqueue must not mutate the queued job snapshots.
    harness._effect_reviews[harness._face_key(files[0])] = roi_b
    assert by_index[0][2].v211_protected_effect_regions == roi_a
    assert by_index[1][2].v211_protected_effect_regions == roi_b
    assert by_index[2][2].v211_protected_effect_regions == ()

    assert by_index[0][0] == files[0]
    assert by_index[1][0] == files[1]
    assert by_index[2][0] == files[2]
    assert len({entry[1] for entry in by_index.values()}) == 3


def test_adapter_maps_queued_effect_roi_to_bridge_after_v2_is_saved(tmp_path, monkeypatch):
    source = tmp_path / "source.png"
    destination = tmp_path / "accepted-V2.png"
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    Image.new("RGB", (8, 8), (35, 80, 120)).save(
        source, dpi=(300, 300), icc_profile=profile
    )

    class FakeEngine:
        def enhance(self, src, out, *, scale, progress_callback=None, cancel_check=None):
            assert scale == 2
            with Image.open(src) as image:
                image.resize((16, 16), Image.Resampling.NEAREST).save(
                    out, dpi=(300, 300)
                )

    adapter = NiyomSilpCoreAdapter.__new__(NiyomSilpCoreAdapter)
    adapter.engine_manager = SimpleNamespace(
        engine=None,
        device_manager=SimpleNamespace(
            get_default_device=lambda: SimpleNamespace(name="CPU")
        ),
    )
    adapter.create_job_engine = lambda _settings: FakeEngine()

    monkeypatch.setattr(adapter_module, "image_size", lambda _path: (8, 8))
    monkeypatch.setattr(adapter_module, "needs_streaming", lambda *_args: False)
    monkeypatch.setattr(adapter_module, "validate_export", lambda *_args: None)
    monkeypatch.setattr(adapter_module, "refine_sign_edges", lambda image, **_kwargs: image)

    from signprint_ai import v211_blur_gate, v211_face_contract, v211_four_engine_bridge

    monkeypatch.setattr(
        v211_blur_gate, "select_photo_restoration",
        lambda settings, _source, **_kwargs: (settings, None),
    )
    monkeypatch.setattr(
        v211_face_contract, "enforce_requested_face_restoration",
        lambda *_args, **_kwargs: None,
    )

    roi = ((0.20, 0.15, 0.80, 0.90),)
    observed = {}

    def fake_bridge(src, v2_output, **kwargs):
        assert Path(src) == source
        assert Path(v2_output) == destination
        assert destination.is_file(), "the accepted V2 raster must be durable before bridge execution"
        with Image.open(destination) as saved:
            assert saved.size == (16, 16)
            assert saved.getpixel((8, 8)) == (35, 80, 120)
            assert saved.info.get("icc_profile") == profile
        observed.update(kwargs)
        return {
            "status": "four_engine_fusion_preview_ready",
            "v2_output_preserved": True,
            "quality_certified": False,
        }

    monkeypatch.setattr(
        v211_four_engine_bridge, "maybe_run_four_engine_assist", fake_bridge
    )

    settings = SimpleNamespace(
        print_width=None,
        print_height=None,
        print_unit="cm",
        dpi=300,
        ai_scale=2,
        color_mode="RGB",
        export_format="PNG",
        resize_mode="stretch",
        device="AUTO",
        face_protection=False,
        face_mode="protect",
        face_strength=35,
        face_regions=(),
        graphic_ai=False,
        text_graphic_boost=0,
        icc_profile_path=None,
        v211_photo_model="real_esrgan",
        v211_source_guided_ink=False,
        v211_verified_text_regions=(),
        v211_protected_effect_regions=roi,
        v21_v2_quality_baseline=False,
    )

    result = adapter.process(source, destination, settings, use_ai=True)

    assert destination.is_file()
    assert observed["protected_regions"] == ()
    assert observed["protected_effect_regions"] == roi
    assert observed["preserve_all_v2_faces"] is False
    assert result["four_engine_research"]["status"] == "four_engine_fusion_preview_ready"
    with Image.open(destination) as saved:
        assert saved.info.get("icc_profile") == profile
