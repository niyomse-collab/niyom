# Controlled V2 vs V2.1 lettering and flat-fill QA

Shop QA reports rough speckled letter interiors, soft/uneven edges, and weak
response from finishing sliders on V2.1. To compare outputs objectively:

1. Process the **same original** with accepted V2 and candidate V2.1, using
   identical output dimensions, RGB/CMYK mode, ICC and format. Record all
   six slider values and AI passes. Reprocess after changing sliders.
2. In Photoshop note output-pixel coordinates (x,y,width,height) for one
   *uniform solid ink* region well inside a letter, and one text-edge region.
3. Run on the private shop machine:

       python qa/compare_v2_v21.py v2.png v21.png --flat-roi 100,200,250,100 --edge-roi 100,300,250,100 --report compare.json

4. Interpret POSSIBLE_REGRESSION as a QA blocker requiring visual investigation,
   NO_AUTOMATED_REGRESSION_DETECTED only as a two-crop screen, and NOT_TESTED
   as an incomplete comparison. **None certifies print quality.**
5. For huge output TIFF/PNG, install pyvips in the Python environment running
   the QA script. It reads bounded crops; without it, report NOT_TESTED.
6. Inspect small Thai text, vowel/tone marks, gradients and halo artifacts at
   100%, 200% and 400% in Photoshop and compare printed vinyl on actual ink/media.

The grain indicator is a 3x3 median residual (not suitable for intentional
texture); edge response is the 99th percentile of neighbour-luminance differences.
No user artwork is uploaded to GitHub. V1 and accepted V2 code stay unchanged.
