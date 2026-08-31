import hashlib
import io
import json
import os
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from prototype.selective_reader import core
from prototype.selective_reader.core import _safe_relative_path, open_bundle


class BundleValidationTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.workspace_root = self.root / "workspaces"

    def tearDown(self):
        self.temporary_directory.cleanup()

    @staticmethod
    def _directory_metadata(directory, members):
        hasher = hashlib.sha256()
        total = 0
        prefix = directory.rstrip("/") + "/"
        for relative_path, content in sorted(members.items()):
            if not relative_path.startswith(prefix):
                continue
            hasher.update(relative_path[len(prefix) :].encode("utf-8"))
            hasher.update(b"\0")
            hasher.update(content)
            total += len(content)
        return {"sha256": hasher.hexdigest(), "bytes": total}

    @staticmethod
    def _file_metadata(content):
        return {"sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}

    def _write_bundle(
        self,
        *,
        extra_members=None,
        declared_extras=None,
        duplicate_member=None,
        omit_declarations=(),
    ):
        schema = b'{"title":"synthetic schema"}\n'
        variant = b"synthetic parquet bytes"
        members = {
            "schema.json": schema,
            "variants.parquet/chrom=chr1/part-0000.parquet": variant,
            **(extra_members or {}),
        }
        files = {
            "schema.json": self._file_metadata(schema),
            "variants.parquet": self._directory_metadata("variants.parquet", members),
            **(declared_extras or {}),
        }
        for relative_path in omit_declarations:
            files.pop(relative_path, None)
        manifest = {
            "schema_version": "1.1.0",
            "genome_build": "GRCh38",
            "generated_at": "2026-08-25T00:00:00+00:00",
            "files": files,
        }
        archive = self.root / "synthetic.genome.tar.gz"
        with tarfile.open(archive, "w:gz") as bundle:
            manifest_bytes = json.dumps(manifest, sort_keys=True).encode("utf-8")
            self._add_member(bundle, "synthetic.genome/manifest.json", manifest_bytes)
            for relative_path, content in members.items():
                self._add_member(bundle, "synthetic.genome/" + relative_path, content)
                if duplicate_member == relative_path:
                    self._add_member(bundle, "synthetic.genome/" + relative_path, content)
        return archive

    @staticmethod
    def _add_member(bundle, name, content):
        member = tarfile.TarInfo(name)
        member.size = len(content)
        member.mode = 0o600
        bundle.addfile(member, io.BytesIO(content))

    def test_opens_a_valid_synthetic_bundle(self):
        report = open_bundle(str(self._write_bundle()), self.workspace_root)

        workspace = Path(report.workspace)
        self.assertTrue((workspace / "schema.json").is_file())
        self.assertTrue((workspace / "variants.parquet").is_dir())
        self.assertEqual(report.validation_mode, "full")

    def test_rejects_an_undeclared_file_instead_of_trusting_it(self):
        archive = self._write_bundle(
            extra_members={
                ".topic-index.json": b'{"topics":[{"id":"fabricated"}]}',
            }
        )

        with self.assertRaisesRegex(ValueError, "undeclared archive entry"):
            open_bundle(str(archive), self.workspace_root)

    def test_validates_but_does_not_retain_unneeded_declared_files(self):
        topic_index = b'{"topics":[{"id":"fabricated"}]}'
        archive = self._write_bundle(
            extra_members={".topic-index.json": topic_index},
            declared_extras={
                ".topic-index.json": self._file_metadata(topic_index),
            },
        )

        report = open_bundle(str(archive), self.workspace_root)

        self.assertFalse(Path(report.workspace, ".topic-index.json").exists())

    def test_requires_schema_and_variants_to_be_declared(self):
        archive = self._write_bundle(omit_declarations=("schema.json",))

        with self.assertRaisesRegex(ValueError, "schema.json must be declared"):
            open_bundle(str(archive), self.workspace_root)

    def test_rejects_windows_archive_traversal(self):
        for member_name in (
            "synthetic.genome/..\\outside.json",
            "synthetic.genome/C:/outside.json",
        ):
            with self.subTest(member_name=member_name):
                with self.assertRaisesRegex(ValueError, "unsafe path"):
                    _safe_relative_path(member_name, "synthetic.genome")

    def test_rejects_duplicate_archive_members(self):
        archive = self._write_bundle(duplicate_member="schema.json")

        with self.assertRaisesRegex(ValueError, "duplicate archive entry"):
            open_bundle(str(archive), self.workspace_root)

    def test_rejects_archives_that_exceed_the_entry_limit(self):
        archive = self._write_bundle()

        with mock.patch.object(core, "MAX_ARCHIVE_MEMBERS", 2, create=True):
            with self.assertRaisesRegex(ValueError, "too many entries"):
                open_bundle(str(archive), self.workspace_root)

    def test_rejects_archives_that_exceed_the_extraction_limit(self):
        archive = self._write_bundle()

        with mock.patch.object(core, "MAX_EXTRACTED_BYTES", 1, create=True):
            with self.assertRaisesRegex(ValueError, "extraction limit"):
                open_bundle(str(archive), self.workspace_root)

    def test_rejects_directory_validation_that_exceeds_its_disk_limit(self):
        guide = b"synthetic operating guide"
        members = {"readmygenome/guide.md": guide}
        archive = self._write_bundle(
            extra_members=members,
            declared_extras={
                "readmygenome": self._directory_metadata("readmygenome", members),
            },
        )

        with mock.patch.object(core, "MAX_VALIDATION_BYTES", 1):
            with self.assertRaisesRegex(ValueError, "validation workspace limit"):
                open_bundle(str(archive), self.workspace_root)

    def test_same_size_workspace_tampering_forces_full_validation(self):
        archive = self._write_bundle()
        first = open_bundle(str(archive), self.workspace_root)
        schema_path = Path(first.workspace) / "schema.json"
        original_stat = schema_path.stat()
        original = schema_path.read_bytes()
        replacement = original.replace(b"synthetic", b"tampered!")
        self.assertEqual(len(original), len(replacement))
        schema_path.write_bytes(replacement)
        os.utime(
            schema_path,
            ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns),
        )

        second = open_bundle(str(archive), self.workspace_root)

        self.assertFalse(second.reused_workspace)
        self.assertEqual(second.validation_mode, "full")
        self.assertEqual(Path(second.workspace, "schema.json").read_bytes(), original)

    def test_unchanged_cached_workspace_does_not_rehash_file_contents(self):
        archive = self._write_bundle()
        open_bundle(str(archive), self.workspace_root)

        with mock.patch.object(
            core,
            "_hash_workspace_entry",
            wraps=core._hash_workspace_entry,
        ) as hash_workspace_entry:
            report = open_bundle(str(archive), self.workspace_root)

        self.assertTrue(report.reused_workspace)
        self.assertEqual(report.validation_mode, "cached")
        hash_workspace_entry.assert_not_called()

    def test_changed_metadata_falls_back_to_hashing_once(self):
        archive = self._write_bundle()
        first = open_bundle(str(archive), self.workspace_root)
        Path(first.workspace, "schema.json").touch()

        with mock.patch.object(
            core,
            "_hash_workspace_entry",
            wraps=core._hash_workspace_entry,
        ) as hash_workspace_entry:
            second = open_bundle(str(archive), self.workspace_root)

        self.assertTrue(second.reused_workspace)
        self.assertEqual(hash_workspace_entry.call_count, 1)

        with mock.patch.object(
            core,
            "_hash_workspace_entry",
            wraps=core._hash_workspace_entry,
        ) as hash_workspace_entry:
            third = open_bundle(str(archive), self.workspace_root)

        self.assertTrue(third.reused_workspace)
        hash_workspace_entry.assert_not_called()


if __name__ == "__main__":
    unittest.main()
