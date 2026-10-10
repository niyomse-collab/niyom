# NiyomSilp Independent Core — isolated prototype

This new NiyomSilp adapter uses published Real-ESRGAN and BasicSR library APIs; it does **not** import or copy the ARM application engine. Its code is experimental and NOT wired to the current app.

## User-facing invariants
- Main application, layout, original buttons, settings, previews and print/export pipeline are untouched.
- Existing ARM pipeline is still production; adding these files changes no user-facing behavior.
- A CI test locks the existing UI and engine files by their git blob hashes, and checks static button-to-handler wiring. This does **not** prove end-to-end button behavior.
- Newly implemented inference parameters match the working ARM baseline: RealESRGAN_x4plus (RRDBNet), FP32, tile 256, pad 10, pre-pad 0, 2×/4×, and 8× in two passes (4× followed by 2×).
- Preserve the legacy PIL RGB array passing convention for now even though upstream RealESRGAN uses BGR semantics. Changing this may change colors; it requires a separate controlled regression.
- No denoise, sharpen or color transformations are added in this prototype.

## Run isolated experiment (not the production app)
Requires compatible `torch`, `basicsr`, `realesrgan`, `numpy` and `Pillow` and an available, permitted RealESRGAN_x4plus model checkpoint.

```python
from independent_core import CoreConfig, IndependentCore
core = IndependentCore(CoreConfig(model_path="models/RealESRGAN_x4plus.pth"))
core.enhance("sample.png", "candidate.png", scale=4)
```

To compare with a trusted baseline PNG from the old installed application:

```bash
python -m independent_core.compare old-baseline.png candidate.png
```

The comparator reports same/different dimensions, exact pixel match, changed pixel count, max/mean differences, and PSNR. Pixel equality requires equivalent checkpoint bytes, library versions, inference device and output formatting. **Static tests and fake-model tests do not establish real image-quality parity.**

## Next gates before switching backends
1. Record legal status and SHA256 of model checkpoints, libraries, fonts/assets, and build-time dependencies.
2. Run actual same-image baseline tests on Thai letters, portraits, food textures, gradients and tile seam stress inputs. Require user approval after visual review.
3. Replicate currently exposed queueing/progress, stop, print sizing, RGB/CMYK ICC export, preview and GUI handlers without altering the screen layout.
4. Build a separately installable Windows test package, never overwrite the stable release.

**Rights:** The new adapter is independently authored, but its dependencies and downloaded weights are NOT owned by the shop merely because our glue code is original. Follow their license and notice requirements; consult qualified legal review before declaring unrestricted ownership or perpetual distribution rights.
