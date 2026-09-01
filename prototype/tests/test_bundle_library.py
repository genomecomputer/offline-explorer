import tempfile
import unittest
from pathlib import Path

from prototype.selective_reader.bundle_library import BundleLibrary, default_nickname
from prototype.selective_reader.core import WorkspaceReport


class BundleLibraryTest(unittest.TestCase):
    def test_default_nickname_strips_supported_archive_suffixes(self):
        self.assertEqual(default_nickname("sample.genome.tar.gz"), "sample")
        self.assertEqual(default_nickname("sample.genome.tar"), "sample")

    def test_refuses_to_overwrite_a_corrupt_library(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bundle-library.json"
            path.write_text("[]", encoding="utf-8")
            original = path.read_bytes()
            library = BundleLibrary(path)
            report = WorkspaceReport(
                archive=str(Path(directory) / "sample.genome.tar"),
                workspace=str(Path(directory) / "workspace"),
                schema_version="1.1.0",
                genome_build="GRCh38",
                generated_at="2026-08-14T10:27:30+00:00",
                extracted_files=2,
                extracted_bytes=100,
                skipped_files=0,
                skipped_bytes=0,
                validated_entries=2,
                elapsed_seconds=0.1,
                reused_workspace=False,
                validation_mode="full",
                validated_at="2026-08-14T10:27:31+00:00",
            )

            with self.assertRaisesRegex(ValueError, "bundle library file is invalid"):
                library.register(report)

            self.assertEqual(path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
