> Independent Core update (2026-10-10): runtime now uses `signprint_ai/independent_core.py`; ARM application modules have been removed. UI and model settings remain unchanged. See [audit and validation limits](SOURCE_SEPARATION.md). The following describes the historical compatibility workflow.

# Niyomsil Design AI Enhancer — V2.1 Face Protect Build

V2.1 preserves the proven V2.0.2 ARM V2.2.8 / RealESRGAN_x4plus processing path and adds an isolated optional face-protection layer.

Compatibility rule:
- Face Protection defaults OFF.
- OFF means the existing ARM output path is used unchanged.
- GFPGAN/FaceXLib are loaded only when the option is enabled.
- A Face Protect failure falls back to the already-produced ARM result.

Stable pre-face snapshot:
`v2.0.2-arm-stable-before-face-module`

Optional path:
ARM Core → RetinaFace detection → GFPGAN restoration → conservative blend → export.

Modes:
- Protect: conservative identity-preserving blend for signage.
- Recover: stronger restoration for damaged/blurred faces.

Build artifact:
`Niyomsil-Design-AI-Enhancer-V2.1-Face-Protect-Windows`

Installer:
`Niyomsil-Design-AI-Enhancer-Setup-v2.1.0.exe`
