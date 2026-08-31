import tempfile
import unittest
from pathlib import Path

import duckdb

from prototype.selective_reader.core import search_workspace


class ClinicalSearchTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary_directory.name)
        variants = self.workspace / "variants.parquet" / "chrom=chr17"
        variants.mkdir(parents=True)
        connection = duckdb.connect()
        connection.execute(
            """
            COPY (
                SELECT 'chr17:43071077:A:G'::VARCHAR AS variant_id,
                       'rs12345'::VARCHAR AS rsid,
                       'chr17'::VARCHAR AS chrom,
                       43071077::INTEGER AS pos,
                       'A'::VARCHAR AS ref,
                       'G'::VARCHAR AS alt,
                       struct_pack(gt := [0, 1]::INTEGER[], zygosity := 'het') AS genotype,
                       struct_pack(call_confidence := 'high') AS quality,
                       struct_pack(symbol := 'BRCA1') AS gene,
                       struct_pack(hgvsp := 'p.Ser1Gly') AS consequence,
                       struct_pack(
                           clinvar_significance := 'Likely_pathogenic',
                           clinvar_has_conflicts := false,
                           clinvar_conflict_summary := NULL::VARCHAR,
                           clinvar_review_stars := 3,
                           clinvar_submitters_count := 4,
                           clinvar_id := 'VCV000012345'
                       ) AS pathogenicity,
                       struct_pack(
                           is_gwas_hit := false,
                           traits := []::VARCHAR[],
                           study_pmids := []::VARCHAR[]
                       ) AS trait_associations,
                       true AS clinical_grade
            ) TO ? (FORMAT PARQUET)
            """,
            [str(variants / "part-0000.parquet")],
        )
        connection.execute(
            """
            COPY (
                SELECT 'finding-1'::VARCHAR AS finding_id,
                       'chr17:43071077:A:G'::VARCHAR AS variant_id,
                       'BRCA1'::VARCHAR AS gene_symbol,
                       'Breast cancer'::VARCHAR AS condition,
                       'variant_classification'::VARCHAR AS claim_type,
                       'Likely_pathogenic'::VARCHAR AS classification,
                       true AS clinical_grade,
                       ['evidence-1']::VARCHAR[] AS evidence_ids
                UNION ALL
                SELECT 'finding-2', NULL, NULL, 'Asthma',
                       'variant_classification', 'Uncertain_significance',
                       false, []::VARCHAR[]
            ) TO ? (FORMAT PARQUET)
            """,
            [str(self.workspace / "clinical_findings.parquet")],
        )
        connection.execute(
            """
            COPY (
                SELECT 'evidence-1'::VARCHAR AS evidence_id,
                       'finding-1'::VARCHAR AS finding_id,
                       'chr17:43071077:A:G'::VARCHAR AS variant_id,
                       'ClinVar'::VARCHAR AS source,
                       'VCV000012345'::VARCHAR AS source_record_id,
                       '2026-04'::VARCHAR AS source_version,
                       'Likely pathogenic'::VARCHAR AS assertion,
                       'reviewed by expert panel'::VARCHAR AS review_status,
                       TIMESTAMP '2026-04-10 00:00:00' AS retrieved_at
            ) TO ? (FORMAT PARQUET)
            """,
            [str(self.workspace / "clinical_evidence.parquet")],
        )
        connection.close()

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_clinical_search_joins_person_call_and_recorded_evidence(self):
        result = search_workspace(str(self.workspace), "clinical findings")
        clinical_hits = [
            hit for hit in result.hits if hit["section"] == "clinical_findings"
        ]

        self.assertEqual(len(clinical_hits), 1)
        finding = clinical_hits[0]
        self.assertEqual(finding["condition"], "Breast cancer")
        self.assertEqual(finding["classification"], "Likely_pathogenic")
        self.assertEqual(finding["called_alleles"], ["A", "G"])
        self.assertEqual(finding["call_confidence"], "high")
        self.assertEqual(finding["clinvar_review_stars"], 3)
        self.assertEqual(finding["evidence"][0]["source"], "ClinVar")
        self.assertEqual(
            finding["evidence"][0]["source_record_id"], "VCV000012345"
        )
        self.assertEqual(
            finding["evidence"][0]["review_status"],
            "reviewed by expert panel",
        )

    def test_non_clinical_grade_rows_are_not_returned(self):
        result = search_workspace(str(self.workspace), "Asthma")
        self.assertFalse(
            any(hit["section"] == "clinical_findings" for hit in result.hits)
        )

    def test_source_name_search_uses_recorded_evidence(self):
        result = search_workspace(str(self.workspace), "ClinVar")
        clinical_hits = [
            hit for hit in result.hits if hit["section"] == "clinical_findings"
        ]
        self.assertEqual([hit["finding_id"] for hit in clinical_hits], ["finding-1"])

    def test_flattened_clinical_schema_is_normalized_for_search(self):
        (self.workspace / "clinical_findings.parquet").unlink()
        (self.workspace / "clinical_evidence.parquet").unlink()
        connection = duckdb.connect()
        connection.execute(
            """
            COPY (
                SELECT 'chr17:43071077:A:G'::VARCHAR AS variant_id,
                       'BRCA1'::VARCHAR AS gene_symbol,
                       'Likely_pathogenic'::VARCHAR AS clinvar_significance,
                       'VCV000012345'::VARCHAR AS clinvar_id,
                       'Breast cancer'::VARCHAR AS clinvar_disease_names,
                       'reviewed by expert panel'::VARCHAR AS clinvar_review_status,
                       3::BIGINT AS clinvar_review_stars,
                       false AS clinvar_has_conflicts,
                       NULL::VARCHAR AS clinvar_conflict_summary,
                       true AS clinical_grade,
                       'clinvar'::VARCHAR AS finding_category
            ) TO ? (FORMAT PARQUET)
            """,
            [str(self.workspace / "clinical_findings.parquet")],
        )
        connection.execute(
            """
            COPY (
                SELECT 'chr17:43071077:A:G'::VARCHAR AS variant_id,
                       'BRCA1'::VARCHAR AS gene_symbol,
                       'Likely_pathogenic'::VARCHAR AS clinvar_significance,
                       'VCV000012345'::VARCHAR AS clinvar_id,
                       'reviewed by expert panel'::VARCHAR AS clinvar_review_status,
                       3::BIGINT AS clinvar_review_stars,
                       false AS clinvar_has_conflicts,
                       NULL::VARCHAR AS clinvar_conflict_summary,
                       true AS clinical_grade
            ) TO ? (FORMAT PARQUET)
            """,
            [str(self.workspace / "clinical_evidence.parquet")],
        )
        connection.close()

        result = search_workspace(str(self.workspace), "BRCA1")
        clinical_hits = [
            hit for hit in result.hits if hit["section"] == "clinical_findings"
        ]

        self.assertEqual(len(clinical_hits), 1)
        finding = clinical_hits[0]
        self.assertEqual(finding["finding_id"], "chr17:43071077:A:G")
        self.assertEqual(finding["condition"], "Breast cancer")
        self.assertEqual(finding["classification"], "Likely_pathogenic")
        self.assertEqual(finding["evidence"][0]["source"], "ClinVar")
        self.assertEqual(
            finding["evidence"][0]["review_status"],
            "reviewed by expert panel",
        )


if __name__ == "__main__":
    unittest.main()
