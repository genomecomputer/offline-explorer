from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tarfile
from pathlib import Path

import duckdb


def file_metadata(path: Path) -> dict[str, object]:
    content = path.read_bytes()
    return {"sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}


def directory_metadata(path: Path) -> dict[str, object]:
    hasher = hashlib.sha256()
    total = 0
    for member in sorted(path.rglob("*")):
        if not member.is_file():
            continue
        content = member.read_bytes()
        hasher.update(member.relative_to(path).as_posix().encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(content)
        total += len(content)
    return {"sha256": hasher.hexdigest(), "bytes": total}


def write_parquet(connection: duckdb.DuckDBPyConnection, query: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection.execute("COPY (%s) TO ? (FORMAT PARQUET)" % query, [str(path)])


def generate_bundle(output_directory: Path) -> Path:
    bundle_root = output_directory / "synthetic-review.genome"
    if bundle_root.exists():
        shutil.rmtree(bundle_root)
    bundle_root.mkdir(parents=True)
    (bundle_root / "schema.json").write_text(
        json.dumps({"title": "Synthetic Offline Explorer E2E schema"}) + "\n"
    )

    connection = duckdb.connect()
    try:
        write_parquet(
            connection,
            """
            SELECT variant_id, rsid, chrom, pos, ref, alt,
                   struct_pack(gt := [0, 1]::INTEGER[], zygosity := 'het') AS genotype,
                   struct_pack(call_confidence := 'high') AS quality,
                   struct_pack(symbol := gene_symbol) AS gene,
                   struct_pack(hgvsp := NULL::VARCHAR) AS consequence,
                   struct_pack(
                       clinvar_significance := CASE
                           WHEN variant_id = 'chr1:100:A:G' THEN 'Likely_pathogenic'
                           ELSE NULL
                       END,
                       clinvar_has_conflicts := false,
                       clinvar_conflict_summary := NULL::VARCHAR,
                       clinvar_review_stars := CASE
                           WHEN variant_id = 'chr1:100:A:G' THEN 3
                           ELSE NULL
                       END,
                       clinvar_submitters_count := 1,
                       clinvar_id := CASE
                           WHEN variant_id = 'chr1:100:A:G' THEN 'VCV000000001'
                           ELSE NULL
                       END
                   ) AS pathogenicity,
                   struct_pack(
                       is_gwas_hit := variant_id = 'chr6:26092913:G:A',
                       traits := CASE
                           WHEN variant_id = 'chr6:26092913:G:A'
                               THEN ['Hemoglobin']::VARCHAR[]
                           ELSE []::VARCHAR[]
                       END,
                       study_pmids := CASE
                           WHEN variant_id = 'chr6:26092913:G:A'
                               THEN ['32888494']::VARCHAR[]
                           ELSE []::VARCHAR[]
                       END
                   ) AS trait_associations,
                   struct_pack(is_pgx := gene_symbol = 'CYP2C19') AS pharmacogenomics,
                   variant_id = 'chr1:100:A:G' AS clinical_grade
            FROM (
                VALUES
                    ('chr1:100:A:G', 'rs100', 'chr1', 100::BIGINT, 'A', 'G', 'GENE1'),
                    ('chr6:26092913:G:A', 'rs1800562', '6', 26092913::BIGINT, 'G', 'A', 'HFE'),
                    ('chr10:94781859:G:A', 'rs4244285', 'chr10', 94781859::BIGINT, 'G', 'A', 'CYP2C19')
            ) AS source(variant_id, rsid, chrom, pos, ref, alt, gene_symbol)
            """,
            bundle_root / "variants.parquet" / "part-0000.parquet",
        )
        write_parquet(
            connection,
            """
            SELECT * FROM (
                VALUES
                    ('GENE1', 'chr1', 50::BIGINT, 250::BIGINT, 1::BIGINT, 1::BIGINT),
                    ('HFE', 'chr6', 26092000::BIGINT, 26094000::BIGINT, 1::BIGINT, 0::BIGINT),
                    ('CYP2C19', 'chr10', 94780000::BIGINT, 94784000::BIGINT, 1::BIGINT, 0::BIGINT)
            ) AS source(gene_symbol, chrom, start_pos, end_pos, variant_count, actionable_count)
            """,
            bundle_root / "gene_index.parquet",
        )
        write_parquet(
            connection,
            """
            SELECT 'CYP2C19'::VARCHAR AS gene_symbol,
                   '*1/*2'::VARCHAR AS diplotype,
                   'Intermediate metabolizer'::VARCHAR AS phenotype,
                   ['synthetic-drug']::VARCHAR[] AS affected_drugs
            """,
            bundle_root / "pharmacogenomics.parquet",
        )
        write_parquet(
            connection,
            """
            SELECT 'Synthetic trait'::VARCHAR AS trait,
                   0.25::DECIMAL(8, 3) AS score_value,
                   72.0::DOUBLE AS percentile,
                   'Synthetic reference'::VARCHAR AS reference_population,
                   DATE '2026-08-14' AS training_date
            """,
            bundle_root / "prs.parquet",
        )
        write_parquet(
            connection,
            """
            SELECT 'finding-1'::VARCHAR AS finding_id,
                   'chr1:100:A:G'::VARCHAR AS variant_id,
                   'GENE1'::VARCHAR AS gene_symbol,
                   'Synthetic condition'::VARCHAR AS condition,
                   'variant_classification'::VARCHAR AS claim_type,
                   'Likely_pathogenic'::VARCHAR AS classification,
                   true AS clinical_grade,
                   ['evidence-1']::VARCHAR[] AS evidence_ids
            """,
            bundle_root / "clinical_findings.parquet",
        )
        write_parquet(
            connection,
            """
            SELECT 'evidence-1'::VARCHAR AS evidence_id,
                   'finding-1'::VARCHAR AS finding_id,
                   'chr1:100:A:G'::VARCHAR AS variant_id,
                   'ClinVar'::VARCHAR AS source,
                   'VCV000000001'::VARCHAR AS source_record_id,
                   'synthetic-1'::VARCHAR AS source_version,
                   'Likely pathogenic'::VARCHAR AS assertion,
                   'reviewed by expert panel'::VARCHAR AS review_status,
                   TIMESTAMP '2026-08-14 00:00:00' AS retrieved_at
            """,
            bundle_root / "clinical_evidence.parquet",
        )
        write_parquet(
            connection,
            """
            SELECT * FROM (
                VALUES
                    ('call-1', 'chr1', 200::BIGINT, true, false, 'high'),
                    ('call-2', '1', 300::BIGINT, false, false, 'low')
            ) AS source(
                callability_id, chrom, pos, callable, reference_observed, call_confidence
            )
            """,
            bundle_root / "callability.parquet",
        )
    finally:
        connection.close()

    files: dict[str, dict[str, object]] = {}
    for path in sorted(bundle_root.iterdir()):
        if path.name == "manifest.json":
            continue
        files[path.name] = (
            directory_metadata(path) if path.is_dir() else file_metadata(path)
        )
    manifest = {
        "schema_version": "1.1.0",
        "genome_build": "GRCh38",
        "generated_at": "2026-08-14T00:00:00+00:00",
        "files": files,
    }
    (bundle_root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )

    archive = output_directory / "synthetic-review.genome.tar"
    with tarfile.open(archive, "w:") as bundle:
        bundle.add(bundle_root, arcname=bundle_root.name)
    return archive


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: generate-e2e-bundle.py OUTPUT_DIRECTORY")
    output_directory = Path(sys.argv[1]).resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    print(generate_bundle(output_directory))
