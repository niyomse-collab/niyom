# NiyomSilp Design V2.1 — candidate, not print-certified

This candidate continues from beta.23 and the QA criteria in PR #16. V1 application,
release workflow, installer identity and approved branch are not changed.

## Reproduced causes

1. With explicit print dimensions, beta.23 ignores the selected AI scale. For a
   682 px source and 3543 px output, selecting 4x still invokes 4x then 2x inference,
   then resizes down. V2.1 respects the selected AI scale while retaining exact print pixels.
2. The beta.23 text finish uses a short tangent filter, luminance-only direction
   and a +/-15 channel clamp. Wider contour excursions survive; equal-luminance
   colour edges can be missed. The V2.1 experiment uses an RGB structure tensor,
   tangential median, local extrema bounds and a separate bounded contour correction.
3. Single-pass photo-model output plus final enlargement was still visibly soft in
   customer title/phone crops. Merely changing sliders or switching to 4x did not meet
   the quality target. Direct use of the graphic model flattened gradients and was rejected.

## Candidate change

A separately checksummed RealESRGAN_x4plus_anime_6B model supplies only bounded
high-frequency detail differences near smooth dark/coloured lettering on a light
background. The photo model retains low-frequency colour and shading. The feature
is visible as an independent V2.1 checkbox and is **OFF by default** to preserve
the previously preferred photo-model output. It must be explicitly enabled;
the text slider at zero disables it even when checked. Packaged smoke tests
explicitly enable this optional mode to verify its model is present.
Selected face rectangles are excluded. This is a conservative heuristic, not OCR
or guaranteed classification of text. Text on arbitrary dark or textured backgrounds
is not covered by this blend rule. No claims of exact reconstruction of missing details.

Both processing routes carry alpha guards. Bounded tile halos cover the longer
filters; crop-after-finishing avoids introducing independent seam edges.

## Evidence so far

- Real CPU inference on private customer title and phone crops, with both the old
  double-pass path and the selected-4x candidate at identical final dimensions.
- Integrated V2.1 processing tested in memory and disk-tile routes; no mocked AI
  in these two crop runs. Outputs: 831x623 and 987x364 at 150 PPI.
- Local Linux regression: 243 tests passed with installed PyTorch; compileall passed.
- Synthetic geometry checks measure contour jitter, mean position, component/hole
  survival, isoluminant colour edges, zero controls, protected faces and tile consistency.
- Customer artwork is private and deliberately excluded from this repository.

Windows installer, real GPU, full customer-image output, Photoshop and physical
print acceptance must be recorded separately. This file is not a production
certification. The candidate workflow builds and installs a V2.1 test package,
then runs real CPU models; it does not publish or replace a stable release.
