# NiyomSilp V2.1 — four-engine integration contract (draft)

Owner request (2026-11-02): enhance the accepted V2 using Waifu2x, Real-ESRGAN, Real-CUGAN and Anime4K; label target product V2.1. This is an implementation contract, **not** evidence of integration or quality.

## Safety and rights
- Preserve V2 release, installer and default Real-ESRGAN/GFPGAN behavior unchanged. Work only in the experimental branch until verified.
- Source each engine independently from its upstream project; do not copy Waifu2x-Extension-GUI binaries or code.
- Maintain per-engine license, dependency, checkpoint provenance, SHA256 and redistribution/use approval. A permissive runner license does not automatically license third-party model weights. Do not bundle an unverified checkpoint.

## Proposed pipeline
- `v2_baseline`: existing Real-ESRGAN + optional GFPGAN face restoration; mandatory reference and fallback.
- `waifu2x`: optional denoise/upscale candidate for graphics and lines, with verified weights.
- `real_cugan`: optional graphics candidate only after exact checkpoint rights are verified.
- `anime4k`: optional edge/line enhancement candidate; inspect implementation/dependencies and prevent halos.
- Compare candidates separately on identical input, dimensions and settings. Never automatically cascade all four or replace V2 based only on unit tests.
- Preserve original text and logos (no OCR/retyping), face likeness, alpha cutout, ICC/DPI and flat-colour fidelity. Reject silent RGB/CMYK or RGBA flattening.

## Release gates
1. Each selected binary/model passes license and SHA256 checks.
2. A/B image outputs exist for Thai/Chinese/Latin tiny type, faces, animals, products, Thai ornamental lines, gradients and transparent PNG; V2 is included.
3. Inspect edge halos, ringing, flat-colour noise, likeness, alpha fringes, ICC/DPI and full-size tiling; document objective metrics and human visual review.
4. Windows GTX 1660 Ti GPU/CPU, Photoshop, MainTop and vinyl print verification; installer install/uninstall and regression tests.
5. Only after approval, release as V2.1; existing PR #18 retains its experimental identity until naming and code migration are explicitly completed.

Current status: integration not yet implemented; this document specifies the work and release gates.
