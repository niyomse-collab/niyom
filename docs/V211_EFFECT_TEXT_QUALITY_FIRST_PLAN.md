# V2.1.1 Super AI — quality-first hardware and styled-text requirements
Status: **design / acceptance contract, NOT implemented or quality-certified**. Owner direction recorded 31 Oct 2026. Applies only to Draft PR #18 (`feature/v2.1.1-super-ai`). **Do not modify the accepted V1 or V2 binaries/files/settings.**

## 1. Quality is the priority; GTX 1660 Ti is a compatibility target, not a model-selection ceiling
- Choose candidate models/pipelines on measured image quality, preservation of source content, rights and repeatability **before** judging runtime speed. Do not discard a stronger model only because inference is slow on the operator's NVIDIA GTX 1660 Ti 6 GB.
- A selectable **Highest Quality** profile may use sequential multi-pass inference, overlapping tiles with seam validation, mixed/FP32 precision where necessary to avoid artifacts, disk-backed intermediate buffers, CPU/RAM offload and model unload/reload. Keep **V2 Baseline** as a separately accessible reference/fallback. Expose realistic progress, resource usage and cancellation; avoid claiming unrestricted performance.
- Do not promise that every candidate can run locally: checkpoint, license, CUDA compatibility, RAM/disk needs and OOM recovery must be verified. On resource failure, never silently output partial/corrupt work, overwrite files, or downgrade to a different result without informing the operator.
- Keep full-resolution print export (requested pixel dimensions, DPI, ICC, PNG/TIFF alpha, Photoshop/MainTop compatibility). Tiling must not introduce halos or seams. Original V1/V2 remain untouched.

## 2. Sign text is not one flat-colour class
Explicitly distinguish:
1. **Plain editable exact text** — user-confirmed Unicode + installed font + ROI, where Verified Text can render sharp glyphs on an optional transparent overlay.
2. **Styled editable text** — known text/font **and** known effect parameters/layers; rerender at final resolution with the complete original look and exact Thai shaping. Text re-rendering alone is insufficient.
3. **Styled raster/flattened text** — no editable effect parameters; protect the existing appearance while improving resolution non-destructively. Never hallucinate or silently replace the text with plain fill.
4. **Graphic art/photography/portraits** — separate region-aware pipeline; guard faces and logos and preserve compositing at interfaces.

### Styled text effects to preserve
- Smooth single- and multicolour gradients, metallic/gold/chrome highlights and texture *inside glyphs*; no blotches, invented black/blue speckles, banding or flat-fill replacement.
- Sharp correct **outer** strokes, including multiple coloured contours; do not create the stroke inward and make the original lettering thinner. Preserve edge antialiasing, curves, corners, holes and the original text metrics.
- Drop shadows, inset/emboss/bevel, 3D/extrusion, highlight, outline and semi-transparent soft glows at their intended radius, opacity, falloff and offset. **Do not indiscriminately sharpen soft effects**.
- Thai vowels/tone marks and spacing, exact English numerals/price, face/logo overlays, RGBA compositing and halos/fringes on both light and dark backgrounds.

### Proposed processing contract (future implementation)
A. Analyse source and candidate V2 results; route by *text subclass* and confidence. Mark uncertain styled regions as protected rather than converting to `replace_flat`.
B. For editable layered art: render geometry/text at target size, then reconstruct effects **as separate masks/layers** (fill/gradient, outer stroke, glow, shadow, emboss) and composite with correct premultiplied-alpha handling and ICC-aware output.
C. For flattened raster art: retain source chroma/gradient and halo profiles; use content-aware high-res geometry/detail recovery with constrained blending. Estimate separate hard-edge vs intentionally soft-effect masks; avoid cross-colour contamination and reduce speckles only where safely supported by evidence. Never claim exact reconstruction from missing pixels.
D. Gate every candidate at same final pixel size against **Approved V2**. Preserve V2 in unchanged regions and make an explicit, visible fallback when improvement cannot be proven. Existing `VerifiedTextRegion` flat/transparent modes remain opt-in and are **not** evidence of styled-text support.
E. Prevent a flat ROI replacement from becoming the default for effect text: require explicit operator confirmation for destructive edits and warn that plain Verified Text does not carry gradients/shadows/strokes.

## 3. Acceptance samples and tests (required before release)
- At minimum: large gradient gold headline with two external strokes and soft shadow; red-black pricing title; glowing neon letters on transparent PNG; embossed/3D text; textured letters; small Thai words with multiple vowel/tone mark combinations; thin curved lettering; logo mixed with portrait; smooth gradient background.
- True-high-resolution reference **where available** + source + Approved V2 + experimental V2.1.1, all at equal physical pixels, same ICC/DPI. Review 100% crops and intended print size; include user-visible A/B. Measure edge shape/width, tone-mark survival, perceptual colour error (including delta-E where reliable), colour smoothness/banding, effect profile, halo/fringe, alpha, seams and damaged-neighbour pixels; do not substitute PSNR alone for visual approval.
- Hard fail on distorted letters, changed meaning/price, newly dark/blue speckles in red text, replaced gradients, lost shadow/glow, inward-shifted outer outline, corrupted transparency, face identity damage or any silent file overwrite.
- Verify using **actual** local models and Windows packaging, GPU 1660 Ti 6 GB with disk/CPU fallback when feasible, several file sizes including large-format tiled PNG/TIFF, Photoshop and MainTop. Declare model checkpoint/license and hardware support honestly. Add a separate regression proving OFF leaves the approved V2 path unchanged.
- Do not merge/release a new installer until the user approves representative real-design A/B and the print/quality checks pass.

## 4. Milestone order
1. Gather representative **styled** typography source samples; publish reference crops with private customer files kept off public GitHub.
2. Add region/type routing and effect-preservation guard; prevent Verified Text from flattening styled regions by default.
3. Prototype editable-style reconstruction and separate raster-style restoration, evaluate against V2; ship neither on score alone.
4. Add QA, format and tile tests; verify quality-first resource management and Windows print workflow.
5. Only then propose an opt-in tester. No changes to accepted V1/V2.

**Current truth (31 Oct 2026):** Verified Text has demonstrated benefit only when exact source text and font are provided. Automatic text-effect recovery and general superiority over V2 are **NOT verified**.
