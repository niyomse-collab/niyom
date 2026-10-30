# NiyomSilp Design V2.1 — Max-Quality, Hardware-Agnostic AI Plan
Date: 2026-10-30. Owner scope: fix/v21-real-quality / PR #17. **Draft; no production approval.**
This document records the user's acceptance requirements and research candidates. It does NOT claim the third-party models are installed, integrated or tested in the Windows installer.

## Non-negotiable acceptance criteria

- Judge by restored output, not how quickly it executes or compatibility with the shop's current GTX 1660 Ti.
- Support workstation-class GPUs, scalable VRAM, and tile/offload processing on print-sized masters. Do not silently skip a requested quality stage because an older GPU cannot handle it. Fail explicitly with an actionable reason if the selected model cannot run.
- Portraits: deblur, reduce noise/compression damage, improve eyes/nose/lips/hair while preserving recognizable identity and natural skin. Preserve face geometry, but do not preserve original blur. If a candidate invents a different identity, reject that candidate (not the whole face-improvement workflow). Offer alternate restorers for comparison.
- Signage: Thai consonants, diacritics, numbers, outlines, straight/curved geometry, solid-ink speckles and gradients. Textual content must not be hallucinated. Compare against the **same source and same final pixel dimensions** processed with V2; judge at 100% and print scale.
- Exactly preserve exported dimensions, DPI metadata and transparency; no alpha fringes, gradients flattened by model or seams between tiles.
- All actual model stages must log **selected**, **executed**, **accepted/rejected**, **reason**, **model/checksum**, and **final-export-applied**. A skipped face or graphics stage is a QA failure for a job where it was requested, not a silent success.
- No edits to V1, existing V2 stable branch or their installers/releases. Keep PR #17 draft until real artwork, human portrait, Photoshop/MainTop and physical-print acceptance.

## Pipeline design for high-quality hardware (proposal, not yet integrated)

1. Inspect content and degradation, retain source RGBA and color profile, map face ROIs plus text/graphic ROIs.
2. Dedicated restoration/deartifact/deblur prior to upscale, chosen independently for photographs and hard-edged graphics.
3. High-quality spatial super-resolution (e.g., HAT) on photograph and graphic branches; allocate tiles/overlap or workstation memory according to actual device, not a fixed low-VRAM quality preset.
4. Dedicated **face comparison ensemble**: existing GFPGAN baseline alongside RestoreFormer++; optionally test DiffBIR face branch. Select with visual/landmark/identity consistency checks and user control, not just automatic no-op protection. Never force a generated face if its identity drifts.
5. Stroke and fill finishing: preserve text topology, diacritics, clean borders and gradients; avoid changing glyph semantics. A conventional non-generative path must be available if generative output alters a character.
6. Safe region compositing, full-size alpha/ICC export, compare source/V2/V2.1 at identical size. Track explicit stage statuses in the job result.
7. Quality profiles: V2 baseline (reproducibility), V2.1 Max Quality (not time/VRAM limited by policy; hardware-dependent execution plan). Reduced hardware must not silently downgrade Max Quality.

## Candidate matrix (research stage only)

| Candidate | Role | Upstream | Repository license status / restrictions |
|---|---|---|---|
| HAT, incl. Real-HAT-GAN | strong image super-resolution / details | https://github.com/XPixelGroup/HAT | upstream LICENSE is Apache-2.0 (not MIT); setup.py has conflicting `license='MIT License'` metadata; verify exact checkpoint/weights and dependency terms before commercial redistribution |
| DiffBIR | heavily degraded photographs and blind image restoration; face candidate | https://github.com/XPixelGroup/DiffBIR | repository Apache-2.0, audit all weight licenses |
| RestoreFormer++ | portrait face-restoration comparison against GFPGAN | https://github.com/wzhouxiff/RestoreFormerPlusPlus | upstream reports Apache-2.0; audit checkpoints/dependencies |
| NAFNet | photograph noise/artifact reduction prior to SR | https://github.com/megvii-research/NAFNet | repository MIT; weight provenance to verify |
| SeedVR2 | high-compute restoration research candidate; image adaptation must be validated | https://github.com/IceClear/SeedVR2 | repository Apache-2.0; video-first, no claim that it improves signage |
| SUPIR | large diffusion-based photographic restoration benchmark only | https://github.com/Fanghua-Yu/SUPIR | **non-commercial without written permission**; do not ship for paid shop work |
| HYPIR | diffusion-based restoration research benchmark only | https://github.com/XPixelGroup/HYPIR | **non-commercial without written permission**; do not ship for paid shop work |
| CodeFormer | portrait quality/fidelity research comparison only | https://github.com/sczhou/CodeFormer | **NTU S-Lab license; commercial permission required** |

Use upstream repository licensing plus exact downloadable weight terms, not aggregator listings. Commercial deployment needs legal review of all weights, base models and dependencies.

HAT licensing audit (2026-10-30): upstream [LICENSE](https://github.com/XPixelGroup/HAT/blob/main/LICENSE) contains Apache License 2.0, while [setup.py](https://github.com/XPixelGroup/HAT/blob/main/setup.py) contains a conflicting MIT license field. Treat repository code and any downloaded weights as **separate clearance items**; do not ship HAT checkpoints until the checkpoint provenance, applicable license, and transitive components are documented. This is a documentation correction only; HAT has not been integrated or packaged.

## Engineering and test gates

- First restore V2.1 regression green after Recover-default UI test updates. No release on a red CI.
- Prove that Recover mode actually executes accepted face-restoration passes; report rejection reasons, not only a green install smoke test.
- Add A/B crops of the user's blurred portrait and sign lettering, same source/image size: V2 baseline, V2.1 current, face-restoration alternatives, graphics alternatives. Quantify edge width, text topology change, oversharpening/halos, flat-fill variance, landmark displacement and human visual review.
- Validate alpha, multi-tile seams, color, DPI, file-size limits, cancellation, full Windows packaged GPU inference and output in Photoshop/MainTop. Keep proprietary artwork outside repository.
- A larger model is not assumed superior: explicitly require perceptible improvement without changing letters, faces or intended graphics.

## Current verified code observation

- In PR #17 before 2026-10-30 edits, app V2.1 initialized face mode to Protect. With selected face regions, Protect explicitly copies source-face detail back and **does not execute the GFPGAN restoration path**. Recover is the appropriate default for this user's blurred portrait task; Protect remains available for identity-preserving source replacement.
- V2.1's optional graphic-detail model was gated off while the V2-quality baseline flag was on. The 2026-10-30 branch change allows user-requested opt-in blending without disabling the V2 baseline; it does not establish superior graphic output.
- Heavyweight external candidates above **have not been integrated**, and no verified A/B-quality win has been established.
