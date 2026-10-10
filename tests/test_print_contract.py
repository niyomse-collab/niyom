"""RGB print geometry and export gates. Real CMYK ICC remains unverified."""
import tempfile
import unittest
from pathlib import Path
import numpy as np
from PIL import Image, ImageOps
from independent_core.print_output import PrintSpec, export_print_image, fit_rgb_to_print


class PrintTests(unittest.TestCase):
    def test_known_real_size_pixels_match_existing_app(self):
        from signprint_ai.processing import print_pixels
        for w, h, unit, dpi in [
            (100, 50, "cm", 150), (200, 100, "cm", 300),
            (600, 300, "mm", 300), (1.5, .9, "m", 150),
            (10, 5, "inch", 600),
        ]:
            with self.subTest(w=w, dpi=dpi):
                self.assertEqual(PrintSpec(dpi, w, h, unit).target_pixels(),
                                 print_pixels(w, h, unit, dpi))

    def test_aspect_ratio_protected_with_white_letterboxing(self):
        original = Image.new("RGB", (13, 7), (10, 40, 210))
        for dim in [(22, 22), (30, 12), (13, 7)]:
            with self.subTest(dim=dim):
                image = fit_rgb_to_print(original, dim)
                internal = ImageOps.contain(original, dim, Image.Resampling.LANCZOS)
                expected = Image.new("RGB", dim, "white")
                expected.paste(internal, ((dim[0]-internal.width)//2, (dim[1]-internal.height)//2))
                np.testing.assert_array_equal(np.asarray(image), np.asarray(expected))

    def test_png_tiff_rgb_and_dpi(self):
        with tempfile.TemporaryDirectory() as tmp:
            pixels = np.zeros((21, 37, 3), dtype=np.uint8)
            pixels[:, :19] = (14, 33, 211)
            pixels[:, 19:] = (233, 41, 23)
            for ext in (".png", ".tif"):
                with self.subTest(ext=ext):
                    dest = Path(tmp) / ("export" + ext)
                    info = export_print_image(pixels, dest, PrintSpec(dpi=300))
                    self.assertEqual(info["mode"], "RGB")
                    with Image.open(dest) as image:
                        np.testing.assert_array_equal(np.asarray(image), pixels)
                        self.assertAlmostEqual(image.info["dpi"][0], 300, delta=1.1)

    def test_rgb_pixels_match_existing_export(self):
        from signprint_ai.processing import save_image
        with tempfile.TemporaryDirectory() as tmp:
            image = np.arange(240, dtype=np.uint8).reshape(8, 10, 3)
            prev, proposed = Path(tmp)/"prev.png", Path(tmp)/"new.png"
            save_image(image, prev, dpi=150)
            export_print_image(image, proposed, PrintSpec(dpi=150))
            with Image.open(prev) as a, Image.open(proposed) as b:
                np.testing.assert_array_equal(np.asarray(a), np.asarray(b))

    def test_jpeg_pdf_files_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            for suffix in (".jpg", ".pdf"):
                dest = Path(tmp) / ("art" + suffix)
                report = export_print_image(Image.new("RGB", (17, 12), "red"), dest)
                self.assertEqual(report["pixels"], (17, 12))
                self.assertGreater(dest.stat().st_size, 200)

    def test_cmyk_validation_requires_real_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            im = Image.new("RGB", (8, 8), "red")
            with self.assertRaisesRegex(ValueError, "CMYK"):
                export_print_image(im, Path(tmp)/"bad.png", PrintSpec(color_mode="CMYK"))
            with self.assertRaisesRegex(ValueError, "ICC"):
                export_print_image(im, Path(tmp)/"bad.tif", PrintSpec(color_mode="CMYK"))
            with self.assertRaisesRegex(ValueError, "ICC"):
                export_print_image(im, Path(tmp)/"bad.pdf", PrintSpec(color_mode="CMYK",
                                                                     icc_profile="nonexistent.icc"))

    def test_bad_dimensions_rejected_without_allocating_large_canvas(self):
        with self.assertRaises(ValueError):
            PrintSpec(width=300, height=50, dpi=300).target_pixels()
        with self.assertRaises(ValueError):
            PrintSpec(width=0, height=10).target_pixels()
        with self.assertRaises(ValueError):
            PrintSpec(width=10, height=None).target_pixels()


if __name__ == "__main__":
    unittest.main()
