import tempfile
import unittest
from pathlib import Path

import duckdb

from prototype.selective_reader.core import (
    _supports_schema_version,
    search_workspace,
)


class BundleCompatibilityTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary_directory.name)
        variants = self.workspace / "variants.parquet" / "chrom=chr6"
        variants.mkdir(parents=True)
        connection = duckdb.connect()
        connection.execute(
            """
            COPY (
                SELECT 'chr6:26092913:G:A'::VARCHAR AS variant_id,
                       'rs1800562'::VARCHAR AS rsid,
                       'chr6'::VARCHAR AS chrom,
                       26092913::INTEGER AS pos,
                       'G'::VARCHAR AS ref,
                       'A'::VARCHAR AS alt,
                       struct_pack(gt := [0, 1]::INTEGER[], zygosity := 'het') AS genotype,
                       struct_pack(call_confidence := 'high') AS quality,
                       struct_pack(symbol := 'HFE') AS gene,
                       struct_pack(hgvsp := 'p.Cys282Tyr') AS consequence,
                       struct_pack(
                           clinvar_significance := 'Conflicting_interpretations',
                           clinvar_has_conflicts := true,
                           clinvar_conflict_summary := 'Conflicting classifications',
                           clinvar_review_stars := 1,
                           clinvar_submitters_count := 2,
                           clinvar_id := '15048'
                       ) AS pathogenicity,
                       struct_pack(
                           is_gwas_hit := true,
                           traits := ['Hemoglobin']::VARCHAR[],
                           study_pmids := ['32888494']::VARCHAR[]
                       ) AS trait_associations,
                       false AS clinical_grade
            ) TO ? (FORMAT PARQUET)
            """,
            [str(variants / "part-0000.parquet")],
        )
        connection.close()

    def tearDown(self):
        self.temporary_directory.cleanup()

    def _write_gwas(self, query):
        connection = duckdb.connect()
        connection.execute(
            "COPY (%s) TO ? (FORMAT PARQUET)" % query,
            [str(self.workspace / "gwas_associations.parquet")],
        )
        connection.close()

    def test_accepts_every_stable_v1_schema_version(self):
        self.assertTrue(_supports_schema_version("1.0.0"))
        self.assertTrue(_supports_schema_version("1.1.0"))
        self.assertTrue(_supports_schema_version("1.8.27"))
        self.assertFalse(_supports_schema_version("1.1"))
        self.assertFalse(_supports_schema_version("1.1.0-beta"))
        self.assertFalse(_supports_schema_version("2.0.0"))
        self.assertFalse(_supports_schema_version(None))

    def test_normalizes_legacy_gwas_columns(self):
        self._write_gwas(
            """
            SELECT 'chr6:26092913:G:A'::VARCHAR AS variant_id,
                   'rs1800562'::VARCHAR AS rsid,
                   'chr6'::VARCHAR AS chrom,
                   26092913::BIGINT AS pos,
                   'G'::VARCHAR AS ref,
                   'A'::VARCHAR AS alt,
                   'HFE'::VARCHAR AS gene,
                   'Hemoglobin'::VARCHAR AS trait,
                   'A'::VARCHAR AS effect_allele,
                   0.2::DOUBLE AS effect_size,
                   'reported_effect'::VARCHAR AS effect_type,
                   1e-12::DOUBLE AS p_value,
                   'GWAS Catalog'::VARCHAR AS source,
                   '32888494'::VARCHAR AS pubmed_id,
                   'GCST123456'::VARCHAR AS study_accession,
                   '2025-06'::VARCHAR AS catalog_version,
                   'Hemoglobin'::VARCHAR AS mapped_trait,
                   'Hemoglobin'::VARCHAR AS reported_trait
            """
        )

        hit = self._gwas_hit()

        self.assertEqual(hit["gene"], "HFE")
        self.assertEqual(hit["study_pmids"], ["32888494"])
        self.assertEqual(hit["source_version"], "2025-06")
        self.assertIsNone(hit["effect_allele_in_call"])

    def test_normalizes_spec_gwas_columns_and_uses_person_variant_context(self):
        self._write_gwas(
            """
            SELECT 'association-1'::VARCHAR AS association_id,
                   'chr6:26092913:G:A'::VARCHAR AS variant_id,
                   'Hemoglobin'::VARCHAR AS trait,
                   'A'::VARCHAR AS effect_allele,
                   0.2::DOUBLE AS effect_size,
                   'beta'::VARCHAR AS effect_type,
                   1e-12::DOUBLE AS p_value,
                   408112::BIGINT AS sample_size,
                   ['32888494']::VARCHAR[] AS study_pmids,
                   '2026-06'::VARCHAR AS source_version
            """
        )

        hit = self._gwas_hit()

        self.assertEqual(hit["rsid"], "rs1800562")
        self.assertEqual(hit["gene"], "HFE")
        self.assertEqual(hit["chrom"], "chr6")
        self.assertEqual(hit["pos"], 26092913)
        self.assertEqual(hit["study_pmids"], ["32888494"])
        self.assertIsNone(hit["source"])
        self.assertEqual(hit["source_version"], "2026-06")

    def test_normalizes_current_producer_gwas_columns(self):
        self._write_gwas(
            """
            SELECT 'association-1'::VARCHAR AS association_id,
                   'chr6:26092913:G:A'::VARCHAR AS variant_id,
                   'rs1800562'::VARCHAR AS rsid,
                   '6'::VARCHAR AS variant_chrom,
                   26092913::BIGINT AS variant_pos,
                   'HFE'::VARCHAR AS gene_symbol,
                   'Hemoglobin'::VARCHAR AS trait,
                   'A'::VARCHAR AS effect_allele,
                   true AS effect_allele_in_call,
                   0.2::DOUBLE AS effect_size,
                   'reported_effect'::VARCHAR AS effect_type,
                   1e-12::DOUBLE AS p_value,
                   ['32888494']::VARCHAR[] AS study_pmids,
                   'GWAS Catalog'::VARCHAR AS source,
                   'Hemoglobin'::VARCHAR AS mapped_trait,
                   'Hemoglobin'::VARCHAR AS reported_trait,
                   '2026-06'::VARCHAR AS source_version
            """
        )

        hit = self._gwas_hit()

        self.assertEqual(hit["gene"], "HFE")
        self.assertEqual(hit["chrom"], "6")
        self.assertEqual(hit["study_pmids"], ["32888494"])
        self.assertEqual(hit["source"], "GWAS Catalog")
        self.assertEqual(hit["source_version"], "2026-06")
        self.assertTrue(hit["effect_allele_in_call"])

    def _gwas_hit(self):
        result = search_workspace(str(self.workspace), "Hemoglobin")
        hits = [hit for hit in result.hits if hit["section"] == "gwas"]
        self.assertEqual(len(hits), 1)
        return hits[0]


if __name__ == "__main__":
    unittest.main()
