# V2.1.1 four-engine evidence gate (3 Nov 2026)

Scope: `feature/v2.1.1-super-ai` / Draft PR #18 only. This is a **blocking checklist**, not proof of inference.

## Required evidence for EACH engine
- [ ] Official upstream repository and exact release/tag/asset URL recorded; verify publisher and redistribution terms for binary AND weights separately.
- [ ] SHA-256 obtained from an independently trusted upstream source or owner-approved lock; never treat a digest calculated after an untrusted download as upstream authenticity proof.
- [ ] Platform compatibility demonstrated on authorized Windows runner (CPU/GPU/Vulkan dependencies, command-line flags, model format and architecture).
- [ ] Reproducible provisioning from approved, SHA-256-pinned assets into an isolated directory; fail closed on missing assets, mismatched digest, unexpected archive paths, or existing target.
- [ ] Actual inference executed with the executable AND model files; capture executable path, version, input/output hashes, exit code, stderr/stdout, duration and model digest.
- [ ] PNG RGBA pixel alpha, ICC profile, DPI, Thai/Latin/Chinese glyph contours, flat graphics and natural face/photo fidelity checked against approved V2 using identical input and settings.

| Engine | Official source candidate (verify tag/license/assets before use) | Actual inference certified |
| --- | --- | --- |
| Real-ESRGAN | https://github.com/xinntao/Real-ESRGAN | NO |
| Waifu2x | https://github.com/nihui/waifu2x-ncnn-vulkan | NO |
| Real-CUGAN | https://github.com/nihui/realcugan-ncnn-vulkan | NO |
| Anime4K | https://github.com/TianZerL/Anime4KCPP (implementation choice must be reviewed) | NO |

## Blocking rules
1. Never claim four-engine success from mocks, unit tests, manifests or file existence alone.
2. Never upload customer images, model weights, or large executable archives into public source control or unrestricted CI artifacts.
3. Keep V2's approved Real-ESRGAN and GFPGAN face path as the baseline; reject face failures rather than silently bypassing recovery.
4. HAT removal is incomplete until code imports, UI, CLI, dependencies, docs, workflow and tests are audited and updated on this experimental branch. Historical references in PR descriptions are not execution evidence.
5. Do not merge, publish, or distribute V2.1.1 without explicit owner approval and Windows/print A/B acceptance.

Next action: verify upstream license and asset digests, then run a manual, explicitly authorized Windows workflow with locked assets. Until then report **NOT VERIFIED**.
