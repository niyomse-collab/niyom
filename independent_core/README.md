# NiyomSilp Independent Core: acceptance gates

Status: independent **experimental** adapter only. The installed Windows program and all original UI buttons still use the legacy engine. None of these files are imported by the current desktop app.

## Model-quality checks completed
Official RealESRGAN_x4plus SHA-256 4fa0d38905f75ac06eb49a7951b426670021be3018265fd191d2125df9d682f1, CPU FP32, 2x/4x/8x tiny synthetic fixtures: exactly identical to the unchanged ARM reference engine. Larger Thai lettering (crossing two Tile boundaries), gradient, and illustrated portrait fixtures also match ARM exactly. This does not prove physical print quality or an absence of inherited ARM seams.

## New, separate print-output module
- independent_core/print_output.py: own print unit/DPI calculations and ratio-preserving white-letterbox final size. Exports RGB PNG/TIFF/JPEG/PDF and requires an explicit CMYK ICC profile for CMYK TIFF/JPEG/PDF.
- tests/test_print_contract.py: confirms dimensional parity with existing print conversion for sizes including 200x100 cm at 300 DPI, RGB PNG/TIFF pixels and DPI, legacy PNG pixels, PDF/JPEG file generation, explicit invalid CMYK-profile error.
- To avoid enormous CI allocations, 200x100 cm is calculation-only in this stage. No full-size 300-DPI job has been completed.
- Real printer ICC and PDF output need color-managed output validation, not only syntax tests.

## GPU parity remains a separate release gate
GitHub-hosted CPU checks cannot certify NVIDIA CUDA behavior. With a CUDA-capable Windows machine, a compatible development environment, the same official checkpoint and a sample photo owned/approved by the user, run:

    python tools/run_gpu_parity.py --source "C:\your\photo.png" --scale 2

The script fails if CUDA is missing and saves arm.png, niyomsil.png and gpu_report.json. It does not modify the installed application. Evaluate quality, seams and memory with real large image datasets before switching.

## Release blockers
- Real CUDA/GPU parity and out-of-memory recovery on the target Windows PCs
- CMYK output against a real print-shop ICC profile and physical RIP/print check
- Full-sized print actual output, text correctness and visually inspected tile seams
- End-to-end Windows GUI interaction tests for ALL existing buttons, previews, queue, stop/resume, export, and Photoshop integration where available
- License and redistribution assessment for each official library, model checkpoint and external asset
- No change to main / production until user explicitly approves a validated separate installer
