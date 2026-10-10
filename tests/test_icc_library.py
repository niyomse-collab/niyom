"""External ICC catalog tests do not require proprietary Adobe profile files."""
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile
from PIL import ImageCms

from independent_core.icc_library import list_external_profiles, read_cmyk_profile


class CatalogTests(unittest.TestCase):
    def test_read_external_zip_without_extracting(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample-profiles.zip"
            rgb = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
            with ZipFile(path, "w") as z:
                z.writestr("some-folder/custom.icc", rgb)
                z.writestr("__MACOSX/foo/._custom.icc", b"not an ICC")
            before = sorted(p.name for p in Path(tmp).iterdir())
            entries = list_external_profiles(path)
            after = sorted(p.name for p in Path(tmp).iterdir())
            self.assertEqual(before, after)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0].color_space, "RGB")
            self.assertEqual(entries[0].source_member, "some-folder/custom.icc")
            self.assertEqual(len(entries[0].sha256), 64)
            with self.assertRaisesRegex(ValueError, "not a CMYK"):
                read_cmyk_profile(path, entries[0].description)

    def test_corrupt_icc_must_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.icc"
            bad.write_bytes(b"not icc")
            with self.assertRaisesRegex(ValueError, "Invalid ICC"):
                list_external_profiles(bad)

    def test_source_missing_must_fail(self):
        with self.assertRaises(FileNotFoundError):
            list_external_profiles("never-uploaded-shop-profile-12345.zip")

    def test_reject_path_traversal_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "untrusted.zip"
            rgb = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
            with ZipFile(path, "w") as z:
                z.writestr("../escape.icc", rgb)
                z.writestr("normal.icc", rgb)
            entries = list_external_profiles(path)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0].source_member, "normal.icc")


if __name__ == "__main__":
    unittest.main()
