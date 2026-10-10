"""External ZIP ICC selection security and usability, no proprietary files."""
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from PIL import Image, ImageCms
from independent_core.icc_library import list_external_profiles, read_cmyk_profile_by_sha
from independent_core.icc_external_export import export_selected_cmyk


class ZipCMYKTests(unittest.TestCase):
    def test_rgb_zip_fails_as_cmyk_without_writing_image(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "rgb.zip"
            raw = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
            with ZipFile(path, "w") as z:
                z.writestr("color/Adobe-like-rgb.icc", raw)
            choice = list_external_profiles(path)[0]
            with self.assertRaisesRegex(ValueError, "not a CMYK"):
                read_cmyk_profile_by_sha(path, choice.sha256)
            output = Path(folder) / "cmyk.tif"
            with self.assertRaises(ValueError):
                export_selected_cmyk(Image.new("RGB",(5,5)), output, path, choice.sha256)
            self.assertFalse(output.exists())

    def test_duplicate_profile_digest_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "duplicate.zip"
            raw = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
            with ZipFile(path, "w") as z:
                z.writestr("a.icc", raw)
                z.writestr("b.icc", raw)
            sha = list_external_profiles(path)[0].sha256
            with self.assertRaisesRegex(ValueError, "unique"):
                read_cmyk_profile_by_sha(path, sha)

    def test_invalid_sha_rejected(self):
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            read_cmyk_profile_by_sha("missing.zip", "NOT-A-SHA")

    def test_cmyk_output_rejects_png(self):
        with tempfile.TemporaryDirectory() as folder:
            raw = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
            zip_path = Path(folder) / "rgb.zip"
            with ZipFile(zip_path,"w") as z: z.writestr("r.icc",raw)
            with self.assertRaisesRegex(ValueError, "not a CMYK"):
                export_selected_cmyk(Image.new("RGB",(5,5)), Path(folder)/"out.png",
                                     zip_path, list_external_profiles(zip_path)[0].sha256)


if __name__ == "__main__":
    unittest.main()
