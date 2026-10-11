"""Release v1 branding, packaging and model-preservation contract."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative):
    return (ROOT / relative).read_text("utf-8")


def test_v1_has_shop_brand_and_original_portrait_choices():
    app = read("signprint_ai/app_v2.py")
    assert 'APP_NAME = "นิยมศิลป์ดีไซน์"' in app
    assert 'APP_VERSION = "v1"' in app
    assert 'values=("Protect", "Recover", "Studio AI")' in app
    assert 'resize_mode="fit" if self.lock_ratio.get() else "stretch"' in app


def test_installer_is_shop_v1_and_keeps_existing_ai_files():
    script = read("installer.iss")
    workflow = read(".github/workflows/build-windows.yml")
    build = read("build_windows.ps1")
    assert '#define MyAppName "นิยมศิลป์ดีไซน์ v1"' in script
    assert '#define MyAppVersion "1.0.0"' in script
    assert "OutputBaseFilename=NiyomSilp-Design-v1-Setup" in script
    assert "NiyomSilp-Design-v1-Setup.exe" in workflow
    assert "NiyomSilp-Design-v1-Windows" in workflow
    assert "release/niyomsil-design-v1" in workflow
    assert "NiyomSilp-Design-v1-Setup.exe" in build
    # Existing, pinned third-party models remain exactly the approved ones.
    assert "RealESRGAN_x4plus.pth" in build
    assert "GFPGANv1.4.pth" in build
    assert "detection_Resnet50_Final.pth" in build
    assert "4fa0d38905f75ac06eb49a7951b426670021be3018265fd191d2125df9d682f1" in build
    assert "e2cd4703ab14f4d01fd1383a8a8b266f9a5833dacee8e6a79d3bf21a1b6be5ad" in build
    assert "6d1de9c2944f2ccddca5f5e010ea5ae64a39845a86311af6fdf30841b0a5a16d" in build


def test_offline_installer_preserves_dependency_credits():
    notices = read("THIRD_PARTY_NOTICES.md")
    for component in ("Real-ESRGAN", "GFPGAN", "RetinaFace", "PyTorch"):
        assert component in notices
    spec = read("NiyomsilV2ArmCore.spec")
    assert 'str(ROOT / "THIRD_PARTY_NOTICES.md")' in spec
    assert 'str(ROOT / "models"), "models"' in spec
