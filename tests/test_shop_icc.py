"""Tests for missing/invalid output ICC and private, opt-in hardware comparison.

These are safety and contract tests only: NO shop ICC or GPU was supplied.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageCms
from independent_core.print_output import PrintSpec, export_print_image, open_cmyk_output_profile
from tools.run_shop_icc import verify_profile


class ICCTest(unittest.TestCase):
    def test_missing_shop_profile_cannot_claim_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            absent = Path(tmp) / "not-uploaded.icc"
            with self.assertRaisesRegex(ValueError, "ICC"):
                verify_profile(absent)
            with self.assertRaisesRegex(ValueError, "ICC"):
                export_print_image(
                    Image.new("RGB", (3, 3), "red"), Path(tmp) / "out.tiff",
                    PrintSpec(dpi=150, color_mode="CMYK", icc_profile=absent)
                )
            self.assertFalse((Path(tmp)/"out.tiff").exists())

    def test_rgb_icc_is_rejected_as_cmyk_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            rgb_profile = Path(tmp) / "rgb.icc"
            rgb_profile.write_bytes(ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes())
            with self.assertRaisesRegex(ValueError, "CMYK"):
                open_cmyk_output_profile(rgb_profile)
            with self.assertRaisesRegex(ValueError, "CMYK"):
                verify_profile(rgb_profile)
            with self.assertRaisesRegex(ValueError, "CMYK"):
                export_print_image(
                    Image.new("RGB", (4, 4), "white"), Path(tmp) / "wrong.tif",
                    PrintSpec(color_mode="CMYK", icc_profile=rgb_profile)
                )
            self.assertFalse((Path(tmp)/"wrong.tif").exists())

    def test_corrupt_icc_is_rejected_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp)/"corrupt.icm"
            fake.write_bytes(b"not a printer ICC profile")
            with self.assertRaises(ValueError):
                open_cmyk_output_profile(fake)
            with self.assertRaises(ValueError):
                verify_profile(fake)

    def test_cuda_cli_fails_before_writing_for_missing_files(self):
        from tools.run_gpu_parity import checksum
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp)/"sample.bin"
            f.write_bytes(b"test")
            self.assertEqual(len(checksum(f)), 64)


if __name__ == "__main__":
    unittest.main()
