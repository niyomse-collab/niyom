# Niyomsil Design AI Enhancer — V2.0 ARM Core Build

V2 keeps the black/red Niyomsil Design interface and switches the AI engine to the tested ARM V2.2.8 PyTorch/CUDA processing path.

Processing path:
V2 UI → ARMCoreAdapter → EngineManager → RealESRGANEngine → RealESRGAN_x4plus.pth

The imported ARM core files match the proven `v1-arm-core` branch by Git blob SHA.

Core behavior:
- PyTorch CUDA
- RealESRGAN_x4plus
- CUDA tile 256, tile pad 10, pre-pad 0
- FP32 tested path
- 8x uses a 4x AI pass followed by a 2x AI pass
- no NCNN backend in this build
- no post-AI denoise/contrast/sharpen filters
- RGB PNG preserves final ARM-core pixels
- CMYK/ICC is export-only

Model SHA256:
`4fa0d38905f75ac06eb49a7951b426670021be3018265fd191d2125df9d682f1`

The Windows application and installer icons use the user's Niyomsil Design logo with edge-connected white background removed to alpha transparency while preserving intentional internal white artwork.

Pre-ARM V2 snapshot:
`v2-ncnn-stable`

Build:
GitHub Actions → Build Windows Installer → Run workflow

Artifact:
`Niyomsil-Design-AI-Enhancer-V2-ARM-Core-Windows`

Installer:
`Niyomsil-Design-AI-Enhancer-Setup-v2.0.0.exe`
