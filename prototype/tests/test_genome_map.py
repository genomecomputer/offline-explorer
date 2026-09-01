import tempfile
import unittest
from pathlib import Path

import duckdb

from prototype.selective_reader.core import variants_for_region
from prototype.selective_reader.genome_map import genome_map_for_workspace


class GenomeMapTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary_directory.name)
        chromosome_one = self.workspace / "variants.parquet" / "chrom=chr1"
        chromosome_two = self.workspace / "variants.parquet" / "chrom=chr2"
        chromosome_one.mkdir(parents=True)
        chromosome_two.mkdir(parents=True)
        connection = duckdb.connect()
        connection.execute(
            """
            COPY (
                SELECT variant_id, rsid, chrom, pos, ref, alt,
                       struct_pack(gt := [0, 1]::INTEGER[], zygosity := 'het') AS genotype,
                       struct_pack(call_confidence := 'high') AS quality,
                       struct_pack(symbol := 'MAP1') AS gene,
                       struct_pack(hgvsp := NULL::VARCHAR) AS consequence,
                       struct_pack(
                           clinvar_significance := NULL::VARCHAR,
                           clinvar_has_conflicts := false,
                           clinvar_conflict_summary := NULL::VARCHAR,
                           clinvar_review_stars := NULL::INTEGER,
                           clinvar_submitters_count := NULL::INTEGER,
                           clinvar_id := NULL::VARCHAR
                       ) AS pathogenicity,
                       false AS clinical_grade
                FROM (
                    VALUES
                        ('chr1:1:A:G', 'rs1', 'chr1', 1, 'A', 'G'),
                        ('chr1:2:C:T', 'rs1b', 'chr1', 2, 'C', 'T'),
                        ('chr1:248956422:C:T', 'rs2', 'chr1', 248956422, 'C', 'T')
                ) AS records(variant_id, rsid, chrom, pos, ref, alt)
            ) TO ? (FORMAT PARQUET)
            """,
            [str(chromosome_one / "part-0000.parquet")],
        )
        connection.execute(
            """
            COPY (
                SELECT 'chr2:10:G:A'::VARCHAR AS variant_id,
                       NULL::VARCHAR AS rsid,
                       'chr2'::VARCHAR AS chrom,
                       10::BIGINT AS pos,
                       'G'::VARCHAR AS ref,
                       'A'::VARCHAR AS alt,
                       struct_pack(gt := [0, 1]::INTEGER[], zygosity := 'het') AS genotype,
                       struct_pack(call_confidence := 'high') AS quality,
                       struct_pack(symbol := NULL::VARCHAR) AS gene,
                       struct_pack(hgvsp := NULL::VARCHAR) AS consequence,
                       struct_pack(
                           clinvar_significance := NULL::VARCHAR,
                           clinvar_has_conflicts := false,
                           clinvar_conflict_summary := NULL::VARCHAR,
                           clinvar_review_stars := NULL::INTEGER,
                           clinvar_submitters_count := NULL::INTEGER,
                           clinvar_id := NULL::VARCHAR
                       ) AS pathogenicity,
                       false AS clinical_grade
            ) TO ? (FORMAT PARQUET)
            """,
            [str(chromosome_two / "part-0000.parquet")],
        )
        connection.close()

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_builds_consistent_ten_megabase_variant_density_windows(self):
        result = genome_map_for_workspace(str(self.workspace), "GRCh38")

        self.assertTrue(result["supported"])
        self.assertEqual(result["bin_size_bases"], 10_000_000)
        self.assertEqual(result["total_variant_records"], 4)
        self.assertEqual(len(result["chromosomes"]), 25)
        chromosome_one = result["chromosomes"][0]
        self.assertEqual(chromosome_one["chrom"], "chr1")
        self.assertEqual(chromosome_one["variant_count"], 3)
        self.assertEqual(len(chromosome_one["bins"]), 25)
        self.assertEqual(chromosome_one["bins"][0]["variant_count"], 2)
        self.assertEqual(chromosome_one["bins"][0]["start"], 1)
        self.assertEqual(chromosome_one["bins"][0]["end"], 10_000_000)
        self.assertEqual(chromosome_one["bins"][-1]["variant_count"], 1)
        self.assertEqual(chromosome_one["bins"][-1]["end"], 248_956_422)
        chromosome_two = result["chromosomes"][1]
        self.assertEqual(chromosome_two["bins"][0]["variant_count"], 1)
        self.assertEqual(result["callability"]["state"], "not_included")

    def test_returns_complete_stable_region_pages(self):
        first_page = variants_for_region(
            str(self.workspace), "chr1", 1, 10_000_000, page=1, page_size=1
        )
        second_page = variants_for_region(
            str(self.workspace), "chr1", 1, 10_000_000, page=2, page_size=1
        )

        self.assertEqual(first_page["total"], 2)
        self.assertEqual(first_page["page_count"], 2)
        self.assertEqual(first_page["hits"][0]["rsid"], "rs1")
        self.assertEqual(second_page["hits"][0]["rsid"], "rs1b")

    def test_reports_site_callability_records_without_treating_them_as_coverage(self):
        connection = duckdb.connect()
        connection.execute(
            """
            COPY (
                SELECT 'chr1'::VARCHAR AS chrom, 10::BIGINT AS pos, true AS callable
                UNION ALL SELECT 'chr1', 11, false
                UNION ALL SELECT 'chr2', 12, true
            ) TO ? (FORMAT PARQUET)
            """,
            [str(self.workspace / "callability.parquet")],
        )
        connection.close()

        result = genome_map_for_workspace(str(self.workspace), "GRCh38")

        self.assertEqual(result["callability"]["state"], "available")
        self.assertEqual(result["callability"]["kind"], "site_records")
        self.assertEqual(result["callability"]["record_count"], 3)
        self.assertEqual(result["callability"]["callable_record_count"], 2)
        self.assertEqual(result["chromosomes"][0]["callability_records"], 2)
        self.assertEqual(result["chromosomes"][1]["callability_records"], 1)

    def test_reports_non_callable_site_records_as_included(self):
        connection = duckdb.connect()
        connection.execute(
            """
            COPY (
                SELECT 'chr1'::VARCHAR AS chrom, 10::BIGINT AS pos, false AS callable
            ) TO ? (FORMAT PARQUET)
            """,
            [str(self.workspace / "callability.parquet")],
        )
        connection.close()

        result = genome_map_for_workspace(str(self.workspace), "GRCh38")

        self.assertEqual(result["callability"]["state"], "available")
        self.assertEqual(result["callability"]["record_count"], 1)
        self.assertEqual(result["callability"]["callable_record_count"], 0)

    def test_sums_chromosome_aliases_in_site_callability(self):
        connection = duckdb.connect()
        connection.execute(
            """
            COPY (
                SELECT '1'::VARCHAR AS chrom, 10::BIGINT AS pos, true AS callable
                UNION ALL SELECT 'chr1', 11, true
            ) TO ? (FORMAT PARQUET)
            """,
            [str(self.workspace / "callability.parquet")],
        )
        connection.close()

        result = genome_map_for_workspace(str(self.workspace), "GRCh38")

        self.assertEqual(result["callability"]["record_count"], 2)
        self.assertEqual(result["chromosomes"][0]["callability_records"], 2)

    def test_reports_an_included_but_empty_callability_table(self):
        connection = duckdb.connect()
        connection.execute(
            """
            COPY (
                SELECT NULL::VARCHAR AS chrom, NULL::BIGINT AS pos,
                       NULL::BOOLEAN AS callable
                WHERE false
            ) TO ? (FORMAT PARQUET)
            """,
            [str(self.workspace / "callability.parquet")],
        )
        connection.close()

        result = genome_map_for_workspace(str(self.workspace), "GRCh38")

        self.assertEqual(result["callability"]["state"], "included_empty")
        self.assertEqual(result["callability"]["kind"], "site_records")
        self.assertEqual(result["callability"]["record_count"], 0)

    def test_site_callability_without_positions_is_unavailable(self):
        connection = duckdb.connect()
        connection.execute(
            """
            COPY (
                SELECT 'chr1'::VARCHAR AS chrom, true AS callable
            ) TO ? (FORMAT PARQUET)
            """,
            [str(self.workspace / "callability.parquet")],
        )
        connection.close()

        result = genome_map_for_workspace(str(self.workspace), "GRCh38")

        self.assertEqual(result["callability"]["state"], "summary_unavailable")

    def test_prefers_interval_callability_when_both_sources_exist(self):
        connection = duckdb.connect()
        connection.execute(
            """
            COPY (
                SELECT 'chr1'::VARCHAR AS chrom, 10::BIGINT AS pos, true AS callable
            ) TO ? (FORMAT PARQUET)
            """,
            [str(self.workspace / "callability.parquet")],
        )
        connection.execute(
            """
            COPY (
                SELECT 'chr1'::VARCHAR AS chrom, 1::BIGINT AS start_pos,
                       100::BIGINT AS end_pos, true AS callable
                UNION ALL SELECT 'chr1', 51, 150, true
                UNION ALL SELECT 'chr1', 500, 600, false
                UNION ALL SELECT 'chr2', 1, 50, true
            ) TO ? (FORMAT PARQUET)
            """,
            [str(self.workspace / "callable_regions.parquet")],
        )
        connection.close()

        result = genome_map_for_workspace(str(self.workspace), "GRCh38")

        self.assertEqual(result["callability"]["state"], "available")
        self.assertEqual(result["callability"]["kind"], "interval_records")
        self.assertEqual(result["callability"]["source"], "callable_regions.parquet")
        self.assertEqual(result["callability"]["record_count"], 3)
        self.assertEqual(result["callability"]["callable_bases"], 200)
        self.assertEqual(result["chromosomes"][0]["callable_bases"], 150)
        self.assertEqual(result["chromosomes"][1]["callable_bases"], 50)
        self.assertEqual(result["chromosomes"][0]["bins"][0]["callable_bases"], 150)
        self.assertEqual(result["chromosomes"][0]["callability_percent"], 0.0)

    def test_does_not_infer_a_map_for_an_unsupported_genome_build(self):
        result = genome_map_for_workspace(str(self.workspace), "GRCh37")

        self.assertFalse(result["supported"])
        self.assertEqual(result["reason"], "genome_build_not_supported")
        self.assertEqual(result["chromosomes"], [])


if __name__ == "__main__":
    unittest.main()
