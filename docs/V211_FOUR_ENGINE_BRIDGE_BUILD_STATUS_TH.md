# NiyomSilp V2.1.1 — V2-first four-engine bridge (3 November 2026)

Scope: work/v211-four-engine-v2-bridge-20261103, branched from feature/v2.1.1-super-ai.
**Do not merge or publish an installer as an accepted V2.1.1 release without shop testing.**

## Implemented in this candidate
- The existing V2 main processing path and its face restoration remain the default.
- After a V2 image has been exported, the optional research hook can invoke installed Real-ESRGAN, Waifu2x, Real-CUGAN and Anime4K engines with an approved, locally installed SHA256-checked manifest.
- The four engines are run sequentially against the original source at one output size. They never stack four enlargement passes.
- A candidate cannot overwrite the shop-approved V2 print output. Failing/missing engines do not break a successful V2 export.
- All existing V2 UI controls remain unchanged; this adds no new customer-facing buttons.
- CI unit tests exercise the opt-in gate, non-AI bypass, missing manifest, colour/format bounds and baseline preservation.

## How to enable in a controlled Windows QA session
Set `NIYOMSIL_V211_FOUR_AI=1`, `NIYOMSIL_V211_FOUR_AI_MANIFEST=<absolute manifest JSON>`, and optionally `NIYOMSIL_V211_FOUR_AI_EVIDENCE_DIR=<private local path>`. The manifest must point to independently licensed, installed binaries and model weights and contain approved hashes. Without these settings, accepted V2 behaviour is unchanged. Local evidence-dir candidates may contain customer images and must not be uploaded publicly.

## NOT yet verified/completed
- Automatic four-model fusion into the deliverable is **NOT implemented**; the present hook collects candidate evidence only.
- Model binaries and weights are **NOT bundled** in the Windows installer.
- Actual four-model inference, all four on one real signage image in the packaged Windows app, remains **UNVERIFIED**.
- 5× quality/weight has not been established; numeric multiplier on model outputs is not proof of improved lettering or gradients.
- Must verify Thai text/gradients/green flat backgrounds, faces, transparent PNG, ICC/DPI, and 6 GB GTX 1660 Ti GPU in the shop.
- Auxiliary engines only process PNG RGB/RGBA candidates up to a conservative memory budget; this does not limit V2's existing print sizes or TIFF/PDF export.
- Cancellation during external engine subprocesses and asynchronous scheduling are future integration work.

## Build acceptance
The experimental GitHub Actions workflow first compiles/tests the bridge, then attempts a Windows V2-based candidate package with the existing build system. A green unit test or installer build does **not** certify that the four external AI engines have been bundled or that output quality has improved.
