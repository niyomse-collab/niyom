# NiyomSilp Design v1.0.1 — Stable Windows Release

Official user-accepted **NiyomSilp Design v1** release, with an English application name and Windows installer identity.

## Included

- Windows 64-bit GUI installer; Python is not required on the user's PC.
- Shop-branded interface and installer: **NiyomSilp Design v1**.
- AI super-resolution and vinyl-sign print-sizing workflow preserved from the tested V1.0.7 baseline.
- Portrait modes: **Protect**, **Recover**, **Studio AI**, with a face-selection confirmation dialog.
- Lock-proportion mode and independent full-frame stretch without program-added white borders.
- Existing RGB/CMYK/ICC export, zoom/pan, job queue and progress features.

## Official model attribution

The original third-party **Real-ESRGAN**, **GFPGAN** and **RetinaFace/facexlib** model files and pinned checksums are retained. Those third-party libraries and weights are not claimed as originally developed by NiyomSilp Design. See `THIRD_PARTY_NOTICES.md` bundled with the Windows program.

## Download and install (important)

GitHub Releases limits individual assets to 2 GiB. Because the complete Windows setup exceeds that limit, the installer is distributed as **multiple binary parts**, all of which are required:

1. Download **every** `NiyomSilp-Design-v1-Setup.exe.partXX` file, plus `NiyomSilp-Design-v1-Setup.exe.sha256.txt` and `Restore-NiyomSilp-Installer.ps1`, into the **same folder**.
2. Inspect the restore script, then run it in Windows PowerShell to combine the parts and verify SHA-256. Example: `powershell -NoProfile -File .\Restore-NiyomSilp-Installer.ps1` (depending on Windows execution policy you may need to allow this trusted local script).
3. Run the resulting `NiyomSilp-Design-v1-Setup.exe`. Do not attempt to run any single `.partXX` file.
4. Keep a copy of the setup and checksum for future recovery.

For an easier initial download while GitHub keeps CI artifacts, the same intact installer is also in [the approved Windows workflow's Artifacts](https://github.com/niyomse-collab/niyom/actions/runs/38155216671), listed as `NiyomSilp-Design-v1-Windows`. CI artifacts expire; the split release assets are the lasting copy.

**Version note:** The software remains the **v1** product family. Its final English-branding installer uses Windows version **1.0.1**. The AI model processing settings were not changed for the English name update.

## Baseline and next major release

The user's approved source snapshot is protected in the Git branch `archive/niyomsil-design-v1-approved`. New experimental models and training are explicitly out of scope for v1; those are tracked separately for v2.
