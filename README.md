# Niyomsil Design AI Enhancer — V2.1.1 Auto Face Select

V2.1.1 preserves the proven ARM V2.2.8 / RealESRGAN_x4plus core and makes face handling automatic without adding a permanent toolbar.

- Upload-time RetinaFace scan runs automatically.
- No face detected: the file follows the unchanged ARM path.
- Face detected: a full-image dialog appears with clickable face boxes.
- GFPGAN is applied only to faces explicitly selected by the user.
- Skip/no selection: unchanged ARM output path.
- Face-module failure: keep the ARM result.
- Upload-time face detection uses a separate CPU helper so it does not compete with the ARM CUDA render worker.

Stable snapshots:
- `v2.1-face-protect-before-auto-select`
- `v2.0.2-arm-stable-before-face-module`

Artifact:
`Niyomsil-Design-AI-Enhancer-V2.1.1-Auto-Face-Select-Windows`

Installer:
`Niyomsil-Design-AI-Enhancer-Setup-v2.1.1.exe`
