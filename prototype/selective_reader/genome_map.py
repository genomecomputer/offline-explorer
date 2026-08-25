from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import duckdb


BIN_SIZE_BASES = 10_000_000
MAP_CACHE_FILENAME = ".offline-explorer-map-v2.json"
MAP_CACHE_VERSION = 2
GRCH38_CHROMOSOMES: Tuple[Tuple[str, str, int], ...] = (
    ("chr1", "1", 248956422),
    ("chr2", "2", 242193529),
    ("chr3", "3", 198295559),
    ("chr4", "4", 190214555),
    ("chr5", "5", 181538259),
    ("chr6", "6", 170805979),
    ("chr7", "7", 159345973),
    ("chr8", "8", 145138636),
    ("chr9", "9", 138394717),
    ("chr10", "10", 133797422),
    ("chr11", "11", 135086622),
    ("chr12", "12", 133275309),
    ("chr13", "13", 114364328),
    ("chr14", "14", 107043718),
    ("chr15", "15", 101991189),
    ("chr16", "16", 90338345),
    ("chr17", "17", 83257441),
    ("chr18", "18", 80373285),
    ("chr19", "19", 58617616),
    ("chr20", "20", 64444167),
    ("chr21", "21", 46709983),
    ("chr22", "22", 50818468),
    ("chrX", "X", 156040895),
    ("chrY", "Y", 57227415),
    ("chrM", "MT", 16569),
)


def _load_map_cache(workspace: Path, genome_build: str) -> Optional[Dict[str, Any]]:
    path = workspace / MAP_CACHE_FILENAME
    try:
        stored = json.loads(path.read_text())
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return None
    payload = stored.get("payload")
    if (
        stored.get("version") != MAP_CACHE_VERSION
        or stored.get("genome_build") != genome_build
        or not isinstance(payload, dict)
        or payload.get("bin_size_bases") != BIN_SIZE_BASES
        or not isinstance(payload.get("chromosomes"), list)
    ):
        return None
    return payload


def _store_map_cache(
    workspace: Path,
    genome_build: str,
    payload: Dict[str, Any],
) -> None:
    path = workspace / MAP_CACHE_FILENAME
    temporary_path = workspace / (MAP_CACHE_FILENAME + ".tmp")
    stored = {
        "version": MAP_CACHE_VERSION,
        "genome_build": genome_build,
        "payload": payload,
    }
    try:
        temporary_path.write_text(json.dumps(stored, separators=(",", ":")) + "\n")
        temporary_path.replace(path)
    except OSError:
        temporary_path.unlink(missing_ok=True)


def _canonical_chromosome(value: Any) -> str:
    normalized = str(value or "").strip().upper()
    if normalized.startswith("CHR"):
        normalized = normalized[3:]
    if normalized == "MT":
        normalized = "M"
    return "chr" + normalized if normalized else ""


def _chromosome_rows() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for chrom, label, length in GRCH38_CHROMOSOMES:
        bins = []
        bin_count = math.ceil(length / BIN_SIZE_BASES)
        for index in range(bin_count):
            start = index * BIN_SIZE_BASES + 1
            end = min(length, (index + 1) * BIN_SIZE_BASES)
            bins.append(
                {
                    "index": index,
                    "start": start,
                    "end": end,
                    "variant_count": 0,
                    "callable_bases": 0,
                    "callability_percent": None,
                }
            )
        rows.append(
            {
                "chrom": chrom,
                "label": label,
                "length": length,
                "variant_count": 0,
                "callability_records": 0,
                "callable_bases": 0,
                "callability_percent": None,
                "bins": bins,
            }
        )
    return rows


def _callability_summary(
    connection: duckdb.DuckDBPyConnection,
    workspace: Path,
) -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]]]:
    candidates = (
        (workspace / "callable_regions.parquet", "interval_records"),
        (workspace / "callability.parquet", "site_records"),
    )
    selected = next(
        ((path, kind) for path, kind in candidates if path.is_file()),
        None,
    )
    if selected is None:
        return (
            {
                "state": "not_included",
                "kind": None,
                "source": None,
                "record_count": 0,
                "callable_bases": 0,
            },
            {},
        )

    path, kind = selected
    columns = {
        str(row[0])
        for row in connection.execute(
            "DESCRIBE SELECT * FROM read_parquet(?)",
            [str(path)],
        ).fetchall()
    }
    required = {"chrom", "callable"}
    if kind == "interval_records":
        required.update({"start_pos", "end_pos"})
    if not required.issubset(columns):
        return (
            {
                "state": "summary_unavailable",
                "kind": kind,
                "source": path.name,
                "record_count": 0,
                "callable_bases": 0,
            },
            {},
        )

    try:
        if kind == "interval_records":
            rows = connection.execute(
                """
                WITH normalized AS (
                    SELECT chromosomes.chrom,
                           greatest(1, cast(regions.start_pos AS BIGINT)) AS start_pos,
                           least(chromosomes.length, cast(regions.end_pos AS BIGINT)) AS end_pos,
                           count(*) OVER () AS source_record_count,
                           count(*) OVER (PARTITION BY chromosomes.chrom) AS chromosome_record_count
                    FROM read_parquet(?) AS regions
                    JOIN genome_chromosomes AS chromosomes
                      ON CASE
                           WHEN replace(lower(regions.chrom), 'chr', '') = 'mt' THEN 'm'
                           ELSE replace(lower(regions.chrom), 'chr', '')
                         END = replace(lower(chromosomes.chrom), 'chr', '')
                    WHERE regions.callable IS TRUE
                      AND regions.start_pos IS NOT NULL
                      AND regions.end_pos IS NOT NULL
                      AND regions.start_pos <= regions.end_pos
                      AND regions.end_pos >= 1
                      AND regions.start_pos <= chromosomes.length
                ), running AS (
                    SELECT *,
                           max(end_pos) OVER (
                               PARTITION BY chrom
                               ORDER BY start_pos, end_pos
                               ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                           ) AS previous_end
                    FROM normalized
                ), grouped AS (
                    SELECT *,
                           sum(
                               CASE
                                   WHEN previous_end IS NULL OR start_pos > previous_end + 1
                                   THEN 1 ELSE 0
                               END
                           ) OVER (
                               PARTITION BY chrom
                               ORDER BY start_pos, end_pos
                               ROWS UNBOUNDED PRECEDING
                           ) AS interval_group
                    FROM running
                ), merged AS (
                    SELECT chrom,
                           min(start_pos)::BIGINT AS start_pos,
                           max(end_pos)::BIGINT AS end_pos,
                           max(source_record_count)::BIGINT AS source_record_count,
                           max(chromosome_record_count)::BIGINT AS chromosome_record_count
                    FROM grouped
                    GROUP BY chrom, interval_group
                )
                SELECT merged.chrom,
                       bins.bin_index::INTEGER AS bin_index,
                       sum(
                           least(merged.end_pos, (bins.bin_index + 1) * ?)
                           - greatest(merged.start_pos, bins.bin_index * ? + 1)
                           + 1
                       )::BIGINT AS callable_bases,
                       max(merged.source_record_count)::BIGINT AS source_record_count,
                       max(merged.chromosome_record_count)::BIGINT AS chromosome_record_count
                FROM merged
                CROSS JOIN LATERAL generate_series(
                    floor((merged.start_pos - 1) / ?::DOUBLE)::BIGINT,
                    floor((merged.end_pos - 1) / ?::DOUBLE)::BIGINT
                ) AS bins(bin_index)
                GROUP BY merged.chrom, bins.bin_index
                ORDER BY merged.chrom, bins.bin_index
                """,
                [
                    str(path),
                    BIN_SIZE_BASES,
                    BIN_SIZE_BASES,
                    BIN_SIZE_BASES,
                    BIN_SIZE_BASES,
                ],
            ).fetchall()
            coverage: Dict[str, Dict[str, Any]] = {}
            source_record_count = 0
            callable_bases = 0
            for chrom, index, bin_callable_bases, source_count, chromosome_count in rows:
                canonical = _canonical_chromosome(chrom)
                chromosome = coverage.setdefault(
                    canonical,
                    {
                        "record_count": int(chromosome_count),
                        "callable_bases": 0,
                        "bins": {},
                    },
                )
                source_record_count = max(source_record_count, int(source_count))
                covered = int(bin_callable_bases)
                chromosome["callable_bases"] += covered
                callable_bases += covered
                chromosome["bins"][int(index)] = covered
            return (
                {
                    "state": "available" if source_record_count else "included_empty",
                    "kind": kind,
                    "source": path.name,
                    "record_count": source_record_count,
                    "callable_bases": callable_bases,
                },
                coverage,
            )

        rows = connection.execute(
            """
            SELECT chrom, count(*)::BIGINT AS record_count
            FROM read_parquet(?)
            WHERE chrom IS NOT NULL AND callable IS TRUE
            GROUP BY chrom
            """,
            [str(path)],
        ).fetchall()
    except duckdb.Error:
        return (
            {
                "state": "summary_unavailable",
                "kind": kind,
                "source": path.name,
                "record_count": 0,
                "callable_bases": 0,
            },
            {},
        )

    counts = {
        _canonical_chromosome(chrom): {
            "record_count": int(record_count),
            "callable_bases": 0,
            "bins": {},
        }
        for chrom, record_count in rows
        if _canonical_chromosome(chrom)
    }
    total = sum(value["record_count"] for value in counts.values())
    return (
        {
            "state": "available" if total else "included_empty",
            "kind": kind,
            "source": path.name,
            "record_count": total,
            "callable_bases": 0,
        },
        counts,
    )


def genome_map_for_workspace(workspace_path: str, genome_build: str) -> Dict[str, Any]:
    if genome_build != "GRCh38":
        return {
            "supported": False,
            "reason": "genome_build_not_supported",
            "genome_build": genome_build,
            "bin_size_bases": BIN_SIZE_BASES,
            "total_variant_records": 0,
            "callability": {
                "state": "not_evaluated",
                "kind": None,
                "source": None,
                "record_count": 0,
                "callable_bases": 0,
            },
            "chromosomes": [],
        }

    workspace = Path(workspace_path).resolve()
    variants = workspace / "variants.parquet"
    if not variants.is_dir():
        raise ValueError("workspace does not contain variants.parquet")
    cached = _load_map_cache(workspace, genome_build)
    if cached is not None:
        return cached

    chromosome_rows = _chromosome_rows()
    by_chromosome = {row["chrom"]: row for row in chromosome_rows}
    connection = duckdb.connect()
    try:
        connection.execute("PRAGMA threads=2")
        connection.execute(
            "CREATE TEMP TABLE genome_chromosomes "
            "(chrom VARCHAR, sort_order INTEGER, length BIGINT)"
        )
        connection.executemany(
            "INSERT INTO genome_chromosomes VALUES (?, ?, ?)",
            [
                (chrom, index, length)
                for index, (chrom, _label, length) in enumerate(GRCH38_CHROMOSOMES)
            ],
        )
        variant_rows = connection.execute(
            """
            SELECT chromosomes.chrom,
                   greatest(0, cast(floor(
                       (variants.pos - 1) / ?::DOUBLE
                   ) AS INTEGER)) AS bin_index,
                   count(*)::BIGINT AS variant_count
            FROM read_parquet(?, hive_partitioning=true) AS variants
            JOIN genome_chromosomes AS chromosomes
              ON CASE
                   WHEN replace(lower(variants.chrom), 'chr', '') = 'mt' THEN 'm'
                   ELSE replace(lower(variants.chrom), 'chr', '')
                 END = replace(lower(chromosomes.chrom), 'chr', '')
            WHERE variants.pos BETWEEN 1 AND chromosomes.length
            GROUP BY chromosomes.chrom, bin_index
            """,
            [
                BIN_SIZE_BASES,
                str(variants / "**" / "*.parquet"),
            ],
        ).fetchall()

        for chrom, bin_index, variant_count in variant_rows:
            row = by_chromosome.get(_canonical_chromosome(chrom))
            if row is None:
                continue
            index = int(bin_index)
            count = int(variant_count)
            row["variant_count"] += count
            row["bins"][index]["variant_count"] = count

        callability, callability_counts = _callability_summary(connection, workspace)
        for chrom, details in callability_counts.items():
            row = by_chromosome.get(chrom)
            if row is not None:
                row["callability_records"] = details["record_count"]
                row["callable_bases"] = details["callable_bases"]
                if callability["kind"] == "interval_records":
                    row["callability_percent"] = round(
                        details["callable_bases"] / row["length"] * 100,
                        2,
                    )
                    for index, callable_bases in details["bins"].items():
                        if index >= len(row["bins"]):
                            continue
                        bin_row = row["bins"][index]
                        bin_length = bin_row["end"] - bin_row["start"] + 1
                        bin_row["callable_bases"] = callable_bases
                        bin_row["callability_percent"] = round(
                            callable_bases / bin_length * 100,
                            2,
                        )
    finally:
        connection.close()

    payload = {
        "supported": True,
        "reason": None,
        "genome_build": genome_build,
        "bin_size_bases": BIN_SIZE_BASES,
        "total_variant_records": sum(
            row["variant_count"] for row in chromosome_rows
        ),
        "callability": callability,
        "chromosomes": chromosome_rows,
    }
    _store_map_cache(workspace, genome_build, payload)
    return payload
