from types import SimpleNamespace
from pathlib import Path
import sys
from contextlib import nullcontext

import numpy as np
from PIL import Image
from signprint_ai.face_module.detection import FaceDetector, map_regions, selected_indices


def test_detector_normalizes_boxes_without_restoration(monkeypatch, tmp_path):
    import signprint_ai.face_module.detection as module
    folder = tmp_path/'models/face'
    folder.mkdir(parents=True)
    (folder/'detection_Resnet50_Final.pth').touch()
    monkeypatch.setattr(module, 'resource_root', lambda: tmp_path)
    captured = []
    def initialize(name, **kwargs):
        captured.append((name, kwargs))
        return SimpleNamespace(detect_faces=lambda pixels, threshold: np.array([[160, 80, 320, 240, .99]]))
    monkeypatch.setitem(sys.modules, 'torch', SimpleNamespace(no_grad=nullcontext))
    monkeypatch.setitem(sys.modules, 'facexlib', SimpleNamespace())
    monkeypatch.setitem(sys.modules, 'facexlib.detection', SimpleNamespace(init_detection_model=initialize))
    src = tmp_path/'portrait.png'
    Image.new('RGB', (3200, 1600)).save(src)
    detector = FaceDetector()
    assert detector.detect(src) == ((.1, .1, .2, .3),)
    detector.detect(src)
    assert len(captured) == 1 and captured[0][1]['device'] == 'cpu'


def test_selected_face_matching_ignores_detection_order():
    boxes = [[70,10,90,30], [10,10,30,30]]
    assert selected_indices(boxes, ((.05,.05,.35,.35),), (100,100)) == [1]
    assert selected_indices(boxes, (), (100,100)) == []


def test_selected_regions_follow_fit_padding():
    assert map_regions(((0,0,1,1),), (200,100), (100,100)) == ((0,.25,1,.75),)
    assert map_regions(((.1,.2,.3,.4),), (100,200), (100,200)) == ((.1,.2,.3,.4),)


def test_popup_confirm_cancel_and_no_face_state(monkeypatch, tmp_path):
    from signprint_ai import app_v2
    src = tmp_path/'portrait.png'
    Image.new('RGB', (20,20)).save(src)
    key = app_v2.App._face_key(src)
    enabled = []
    statuses = []
    scheduled = []
    app = SimpleNamespace(files=[src], _face_scanning={key}, _face_reviews={},
                          _resume_after_faces=True, _completed_indices=set(),
                          _face_key=app_v2.App._face_key, face_enabled_var=SimpleNamespace(set=enabled.append),
                          _set_status=statuses.append, after=lambda delay, callback: scheduled.append(callback),
                          start_processing=lambda: None)
    regions = ((.1,.1,.5,.5),)
    monkeypatch.setattr(app_v2, 'choose_faces', lambda *args: None)
    app_v2.App._face_scan_done(app, key, regions, None)
    assert key not in app._face_reviews and not scheduled
    app._resume_after_faces = True
    monkeypatch.setattr(app_v2, 'choose_faces', lambda *args: regions)
    app_v2.App._face_scan_done(app, key, regions, None)
    assert app._face_reviews[key] == regions and enabled == [True] and len(scheduled) == 1
    app._resume_after_faces = True
    app_v2.App._face_scan_done(app, key, (), None)
    assert app._face_reviews[key] == ()


def test_error_does_not_mark_file_reviewed(monkeypatch, tmp_path):
    from signprint_ai import app_v2
    src = tmp_path/'portrait.png'
    Image.new('RGB', (20,20)).save(src)
    key = app_v2.App._face_key(src)
    errors = []
    monkeypatch.setattr(app_v2.messagebox, 'showerror', lambda *args: errors.append(args))
    app = SimpleNamespace(files=[src], _face_scanning={key}, _face_reviews={}, _resume_after_faces=True,
                          _face_key=app_v2.App._face_key, _set_status=lambda message: None)
    app_v2.App._face_scan_done(app, key, (), 'missing detector')
    assert errors and key not in app._face_reviews and not app._resume_after_faces
