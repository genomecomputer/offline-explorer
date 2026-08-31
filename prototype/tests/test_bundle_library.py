import unittest

from prototype.selective_reader.bundle_library import default_nickname


class BundleLibraryTest(unittest.TestCase):
    def test_default_nickname_strips_supported_archive_suffixes(self):
        self.assertEqual(default_nickname("sample.genome.tar.gz"), "sample")
        self.assertEqual(default_nickname("sample.genome.tar"), "sample")


if __name__ == "__main__":
    unittest.main()
