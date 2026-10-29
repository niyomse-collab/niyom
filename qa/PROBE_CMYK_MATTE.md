# Bounded CMYK white-matte probe for NiyomSilp V2.1

After exporting a **new** CMYK TIFF from a source PNG with transparency,
run this on the same local machine (no upload to GitHub):

    python qa/probe_cmyk_matte.py source.png exported.tif --report cmyk-check.json

Large source PNG/TIFF or output TIFF requires pyvips in the **Python
environment running this standalone QA script**. A frozen V2.1 installer does not necessarily expose
its bundled pyvips to your system Python. If unavailable, the script reports
NOT_TESTED rather than decoding all pixels. For large source images it reads
only bounded 5x5 alpha patches; it never expands the full source alpha plane.
The script probes only positions that were fully transparent in the source,
with a 5x5 zero-alpha neighbourhood. On CMYK output, its strict corruption
threshold is summed ink >80 (0..1020) or black channel >40 (0..255).

- PASS: sampled zero-alpha areas have a white output matte.
- FAIL: some sampled zero-alpha areas contain unexpectedly heavy CMYK ink.
- NOT_TESTED: not enough valid samples, changed aspect ratio, missing alpha,
  or bounded decoding cannot be performed.

A PASS does **not** certify colour accuracy, anti-aliased edge quality,
correct Thai lettering, matching RIP ICC or physical print quality.
Use Photoshop and the actual printer/ink/media combination for sign-off.
This tool does not change V1, V2 or V2.1 image-processing algorithms.
