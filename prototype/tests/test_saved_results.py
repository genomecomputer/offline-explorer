import csv
from datetime import date, datetime, timezone
from decimal import Decimal
import io
import json
import tempfile
import unittest
from pathlib import Path

from prototype.selective_reader.saved_results import SavedResultsStore, saved_result_id


class SavedResultsStoreTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary_directory.name) / "saved-results.json"
        self.store = SavedResultsStore(self.path)
        self.bundle = {
            "bundle_id": "bundle-1",
            "nickname": "Synthetic sample",
            "schema_version": "1.1.0",
            "genome_build": "GRCh38",
            "generated_at": "2026-08-14T10:27:30+00:00",
        }
        self.record = {
            "section": "pharmacogenomics",
            "gene_symbol": "CYP2C19",
            "diplotype": "*1/*17",
            "phenotype": "Rapid Metabolizer",
            "affected_drugs": ["clopidogrel", "omeprazole"],
            "_record_key": "application-only",
        }

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_saves_deduplicates_removes_and_separates_bundles(self):
        first = self.store.add("bundle-1", "clopidogrel", self.record)
        duplicate = self.store.add("bundle-1", "CYP2C19", self.record)

        self.assertEqual(first["saved_id"], duplicate["saved_id"])
        self.assertEqual(len(self.store.entries("bundle-1")), 1)
        self.assertNotIn("_record_key", first["record"])
        self.assertEqual(self.store.entries("bundle-2"), [])

        reloaded = SavedResultsStore(self.path)
        self.assertEqual(reloaded.entries("bundle-1")[0]["record"], first["record"])
        self.assertTrue(reloaded.remove("bundle-1", first["saved_id"]))
        self.assertEqual(reloaded.entries("bundle-1"), [])
        self.assertFalse(reloaded.remove("bundle-1", first["saved_id"]))

    def test_removes_only_results_owned_by_the_removed_bundle(self):
        self.store.add("bundle-1", "clopidogrel", self.record)
        self.store.add("bundle-2", "clopidogrel", self.record)

        self.assertTrue(self.store.remove_bundle("bundle-1"))

        self.assertEqual(self.store.entries("bundle-1"), [])
        self.assertEqual(len(self.store.entries("bundle-2")), 1)
        self.assertFalse(self.store.remove_bundle("bundle-1"))

    def test_exports_stable_json_and_csv_from_recorded_fields(self):
        self.store.add("bundle-1", "clopidogrel", self.record)

        json_export = self.store.export("bundle-1", self.bundle, "json")
        self.assertEqual(json_export["file_name"], "synthetic-sample-saved-results.json")
        payload = json.loads(json_export["content"])
        self.assertEqual(payload["bundle"]["schema_version"], "1.1.0")
        self.assertEqual(payload["results"][0]["result_type"], "pharmacogenomics")
        self.assertEqual(payload["results"][0]["record"]["gene_symbol"], "CYP2C19")
        self.assertNotIn("bundle_id", payload["bundle"])
        self.assertNotIn("format", payload)
        self.assertNotIn("version", payload)
        self.assertNotIn("saved_id", payload["results"][0])
        self.assertNotIn("section", payload["results"][0]["record"])
        self.assertEqual(
            json_export["content"],
            self.store.export("bundle-1", self.bundle, "json")["content"],
        )

        csv_export = self.store.export("bundle-1", self.bundle, "csv")
        self.assertEqual(csv_export["file_name"], "synthetic-sample-saved-results.csv")
        rows = list(csv.DictReader(io.StringIO(csv_export["content"])))
        self.assertEqual(rows[0]["result_type"], "pharmacogenomics")
        self.assertEqual(rows[0]["gene_symbol"], "CYP2C19")
        self.assertEqual(
            rows[0]["affected_drugs"],
            '["clopidogrel","omeprazole"]',
        )
        self.assertNotIn("bundle_id", rows[0])
        self.assertNotIn("saved_id", rows[0])
        self.assertNotIn("section", rows[0])

    def test_rejects_unsupported_sections(self):
        with self.assertRaisesRegex(ValueError, "unsupported record section"):
            self.store.add(
                "bundle-1",
                "anything",
                {"section": "generated_interpretation", "text": "not from bundle"},
            )

    def test_csv_export_neutralizes_spreadsheet_formulas(self):
        record = dict(
            self.record,
            phenotype='=HYPERLINK("https://example.test","open")',
        )
        bundle = dict(self.bundle, nickname="@synthetic")
        self.store.add("bundle-1", "+lookup", record)

        exported = self.store.export("bundle-1", bundle, "csv")
        row = next(csv.DictReader(io.StringIO(exported["content"])))

        self.assertEqual(row["bundle_nickname"], "'@synthetic")
        self.assertEqual(row["search"], "'+lookup")
        self.assertEqual(
            row["phenotype"],
            "'=HYPERLINK(\"https://example.test\",\"open\")",
        )

    def test_refuses_to_overwrite_a_corrupt_local_store(self):
        self.path.write_text("[]", encoding="utf-8")
        original = self.path.read_bytes()

        with self.assertRaisesRegex(ValueError, "saved results file is invalid"):
            self.store.add("bundle-1", "clopidogrel", self.record)

        self.assertEqual(self.path.read_bytes(), original)

    def test_normalizes_duckdb_scalar_values_for_record_identity(self):
        record = dict(
            self.record,
            score_value=Decimal("1.25"),
            training_date=date(2026, 8, 14),
            generated_at=datetime(2026, 8, 14, 10, 27, tzinfo=timezone.utc),
        )

        identifier = saved_result_id(record)

        self.assertEqual(len(identifier), 24)

    def test_record_identity_survives_a_json_number_round_trip(self):
        record = dict(self.record, activity_score=2.0)
        round_tripped = json.loads(json.dumps(record))

        self.assertEqual(saved_result_id(record), saved_result_id(round_tripped))


if __name__ == "__main__":
    unittest.main()
