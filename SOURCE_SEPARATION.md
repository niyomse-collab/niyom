# Independent Core audit — 2026-10-10

Base commit: a8e606b5f946bcf488f6411099f46dad349b1940.

The base application separated its GUI but still imported the ARM-derived
DeviceManager, EngineManager and RealESRGANEngine from `app/`. Earlier statements
that the whole processing core was independent were therefore incomplete.

This change removes those three modules and implements device discovery, model
initialization, inference orchestration, progress and cancellation in the newly
written `signprint_ai/independent_core.py`. The existing adapter now imports that
module. The initial core replacement left the GUI unchanged. The follow-up UI fix wires
the existing zoom buttons and mouse drag/wheel events to a shared viewport and
replaces the display-only AUTO label with a device selector in the same section.
Historical ARM labels and all existing buttons remain.

Compatibility parameters: RealESRGAN_x4plus, RRDBNet 64 features / 23 blocks /
32 growth channels, FP32, CUDA tile 256, CPU and DirectML tile 128, tile padding
10, pre-padding 0. The adapter keeps 8x as a 4x pass followed by a 2x pass, final
size containment, optional face processing and RGB/CMYK/ICC export. No new
image filters or channel conversions were introduced.

New orchestration source is written for NiyomSilp Design. This does not turn
Real-ESRGAN, BasicSR, PyTorch, optional face libraries or model weights into
shop-owned code. Their terms and attribution remain applicable. Provenance of
other pre-existing files has not been independently established by this audit.

Verification uses mocked inference for routing, pixels, progress, cancellation,
cleanup and export; it does not establish perceptual or GPU numerical parity.
Before release, compare baseline and new RGB PNG outputs with Face Protection
OFF on the same Windows machine, model hash and pinned runtime, including Thai
text, portraits, RGB/RGBA inputs and 2x/4x/8x jobs. Then inspect CMYK/ICC exports
and exercise all existing UI controls. This change does not resolve the known
portrait-restoration quality issue.

Follow-up validation: 15 local tests passed, including viewport fit/zoom/1:1,
normalized pan, bounded crop rendering and explicit device routing. Windows
GUI interaction and hardware inference still require validation on Windows.

User acceptance (2026-10-10): the shop reports that quality is equally good
on its comparison images. This is user-reported acceptance, not an independent
full-image or all-hardware equivalence claim. V2.1.3 packages the preview/device
fixes while keeping inference parameters unchanged.
