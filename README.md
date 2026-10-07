# Niyomsil Design AI Enhancer — V2.0 UI Build

V2 is a UI/status/branding redesign only. The proven V1.1 image-processing core is intentionally preserved.

## Preserved processing
- Real-ESRGAN backend and AI upscale behavior
- V1 Baseline
- Advanced enhancement logic
- Print size and DPI handling
- RGB / CMYK / ICC export pipeline
- PNG / TIFF / PDF / JPG output

The V2 work does not change `processing.py`, `pipeline.py`, or `realesrgan_ncnn.py`.

Stable pre-V2 snapshot:
`v1.1-color-stable`

## V2 UI
Black/red NIYOMSIL DESIGN dashboard, transparent brand logo, GPU/VRAM/engine status, Before/After preview, queue progress, export/color/ICC strip, and bottom runtime status bar.

## Build
GitHub Actions → **Build Windows Installer** → **Run workflow**

Installer:
`Niyomsil-Design-AI-Enhancer-Setup-v2.0.0.exe`

Artifact:
`Niyomsil-Design-AI-Enhancer-V2-Windows`
