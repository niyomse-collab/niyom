# NiyomSilp Independent Core — NVIDIA and shop CMYK verification

This branch adds independently authored experimental tools only. The original installed app, GUI, buttons and ARM processing source remain untouched. This is not an EXE installer and does not replace the stable engine.

## Existing CI results
- RealESRGAN_x4plus, CPU-FP32: pixel-identical to ARM for synthetic samples at 2x, 4x and 8x.
- Thai sign spanning four tiles, color gradient across tiles, and illustrated face matched ARM pixels on CPU.
- RGB output and dimensions matched existing app in unit tests; existing GUI smoke worked on Windows.

## Requirements for a real-hardware result
- NVIDIA GPU with working CUDA PyTorch and compatible BasicSR/Real-ESRGAN packages.
- Official model RealESRGAN_x4plus.pth with SHA256 4fa0d38905f75ac06eb49a7951b426670021be3018265fd191d2125df9d682f1.
- User-authorized local image ideally containing Thai text, photo and flat backgrounds.
- Actual shop printer/RIP CMYK output ICC/ICM profile; monitor/RGB profiles are invalid.
- Local development Python environment. The .exe or stable app is never overwritten.

## Run locally on Windows in the experimental source repository
Use PowerShell, changing paths as needed:

    .\tools\RUN_LOCAL_GPU_ICC_TEST.ps1 -SampleImage "C:\PrintQA\sample.png" -ICCProfile "C:\PrintQA\printer.icc" -ModelFile ".\models\RealESRGAN_x4plus.pth" -Scale 2 -DPI 150

Or use separate commands:

    python tools/run_gpu_parity.py --source "C:\PrintQA\sample.png" --scale 2
    python tools/run_shop_icc.py --source "C:\PrintQA\sample.png" --icc "C:\PrintQA\printer.icc" --dpi 150

Run a CUDA smoke beforehand: python -c "import torch; print(torch.cuda.is_available())". False means GPU parity NOT passed.

## Evidence produced locally only
- local-qa-results/gpu: arm-reference.png, niyomsil-candidate.png, gpu_report.json
- local-qa-results/icc: reference-arm-cmyk.tif, candidate-niyomsil-cmyk.tif, icc_report.json
- local-qa-results is excluded from Git. Do not commit customer photographs or privately licensed ICC files to a public repository.

## Remaining limits
- Parity against ARM does not establish the absence of ARM's existing tile seams or prove better picture quality.
- ICC pixel parity against ARM does not replace RIP soft-proof, actual vinyl-media profile testing or printer calibration.
- Real CUDA and shop ICC results require a working shop PC and actual approved files; GitHub hosted jobs are CPU or non-CUDA.
- GPU out-of-memory recovery, large-format benchmarks, real face fidelity, full button click-through, PDF color proof and a legal license assessment still need validation before installing a new core.
