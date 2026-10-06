# Niyomsil Design AI Enhancer — V1.1 Color Management Build

Independent large-format print image enhancer for **NIYOMSIL DESIGN / นิยมศิลป์ดีไซน์**.

## V1 processing is preserved
The proven V1 Baseline processing path is intentionally unchanged. Color management is applied only at export time.

A frozen snapshot of the pre-CMYK version is kept on:
`v1-stable-snapshot`

## New in V1.1
- RGB / CMYK output selection
- Windows-installed CMYK ICC/ICM discovery
- Custom ICC/ICM profile selection
- ICC-managed RGB → CMYK conversion at export
- TIFF / JPG / PDF CMYK output
- PNG remains RGB only
- Niyomsil Design logo used for the application and installer icons
- Restrained black/red branded header while keeping the V1 workflow/layout

For production printing, TIFF + the printer/RIP-specific ICC profile is recommended.

## Build
GitHub Actions → **Build Windows Installer** → **Run workflow**

Installer:
`Niyomsil-Design-AI-Enhancer-Setup-v1.1.0.exe`
