# Third-party notices

Niyomsil Design AI Enhancer is an independent application.

The V2.1 build can include these third-party components:

- **Real-ESRGAN / BasicSR** — image super-resolution and supporting model architecture. Upstream projects by Xintao Wang and contributors; subject to their upstream licenses and model terms.
- **PyTorch / TorchVision** — neural inference runtime; subject to their upstream licenses.
- **GFPGAN 1.3.8** — optional face-restoration module. Upstream TencentARC/GFPGAN project, Apache-2.0 project license.
- **facexlib 0.3.0** — optional face detection/alignment helpers, including the RetinaFace integration; subject to its upstream license.
- **GFPGANv1.4.pth** — optional face-restoration checkpoint distributed from the official GFPGAN release.
- **detection_Resnet50_Final.pth** — RetinaFace ResNet50 detector checkpoint distributed through the facexlib release.
- **OpenCV** — image conversion/blending utilities.
- **Pillow** — image I/O, previews, and color-management integration.
- **NumPy** — numerical array processing.
- **libvips / pyvips / pyvips-binary** — V2 streaming image decode, resize and export. libvips is LGPL-2.1-or-later; pyvips is MIT. Binary dependency licenses are retained with the packaged runtime. Sources: https://github.com/libvips/libvips, https://github.com/libvips/pyvips, https://github.com/kleisauke/pyvips-binary.
- **tifffile** — bounded TIFF tile writing for V2 intermediate masters; BSD-3-Clause. Source: https://github.com/cgohlke/tifffile.
- **PyInstaller** — Windows application freezing.
- **windnd** — optional Windows drag-and-drop helper.

Face Protection is an optional post-ARM layer and defaults OFF. The independent orchestration core invokes this optional layer through the existing adapter; upstream inference libraries and model terms remain applicable.

The Niyomsil Design logo and branding are user-provided assets.
