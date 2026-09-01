from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import duckdb

from .core import _canonical_chrom_sql, _variant_projection, variants_for_region
from .genome_map import GRCH38_CHROMOSOMES


TRACK_BIN_COUNT = 80
DEFAULT_RADIUS_BASES = 100_000
MAX_REGION_BASES = 25_000_000
REGION_PATTERN = re.compile(
    r"^(?:chr)?(?P<chrom>[0-9]+|X|Y|M|MT):(?P<start>[0-9]+)"
    r"(?:-(?P<end>[0-9]+))?(?::[ACGT]+:[ACGT]+)?$",
    re.IGNORECASE,
)
RSID_PATTERN = re.compile(r"^rs[0-9]+$", re.IGNORECASE)
GENE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,39}$")
CHROMOSOME_LENGTHS = {
    chrom: length for chrom, _label, length in GRCH38_CHROMOSOMES
}


def _sql_path(path: Path) -> str:
    return str(path).replace("'", "''")


def _canonical_chromosome(value: Any) -> str:
    normalized = str(value or "").strip().upper()
    if normalized.startswith("CHR"):
        normalized = normalized[3:]
    if normalized == "MT":
        normalized = "M"
    return "chr" + normalized if normalized else ""


def _rows(cursor: Any) -> List[Dict[str, Any]]:
    columns = [description[0] for description in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _has_expression(
    connection: duckdb.DuckDBPyConnection,
    expression: str,
) -> bool:
    try:
        connection.execute("SELECT %s FROM variants LIMIT 0" % expression)
    except duckdb.Error:
        return False
    return True


def _bounded_region(chrom: str, start: int, end: int) -> Tuple[int, int]:
    chromosome_length = CHROMOSOME_LENGTHS.get(chrom)
    if chromosome_length is None:
        raise ValueError("chromosome is not covered by this region browser")
    bounded_start = max(1, int(start))
    bounded_end = min(chromosome_length, int(end))
    if bounded_end < bounded_start:
        raise ValueError("genomic region is invalid")
    if bounded_end - bounded_start + 1 > MAX_REGION_BASES:
        raise ValueError("region browser supports windows up to 25 Mb")
    return bounded_start, bounded_end


def _centered_region(chrom: str, position: int) -> Tuple[int, int]:
    return _bounded_region(
        chrom,
        position - DEFAULT_RADIUS_BASES,
        position + DEFAULT_RADIUS_BASES,
    )


def _gene_region(chrom: str, start: int, end: int) -> Tuple[int, int]:
    span = end - start + 1
    padding = max(10_000, math.ceil(span * 0.15))
    proposed_start = max(1, start - padding)
    chromosome_length = CHROMOSOME_LENGTHS[chrom]
    proposed_end = min(chromosome_length, end + padding)
    if proposed_end - proposed_start + 1 <= MAX_REGION_BASES:
        return proposed_start, proposed_end
    midpoint = start + span // 2
    half_window = MAX_REGION_BASES // 2
    return _bounded_region(chrom, midpoint - half_window, midpoint + half_window - 1)


def _resolve_query(
    connection: duckdb.DuckDBPyConnection,
    workspace: Path,
    query: str,
) -> Dict[str, Any]:
    normalized = query.strip().replace(",", "")
    if not normalized:
        raise ValueError("enter a gene, rsID, or genomic coordinate")

    coordinate = REGION_PATTERN.fullmatch(normalized)
    if coordinate is not None:
        chrom = _canonical_chromosome(coordinate.group("chrom"))
        start = int(coordinate.group("start"))
        explicit_end = coordinate.group("end")
        if explicit_end is not None:
            end = int(explicit_end)
            start, end = _bounded_region(chrom, start, end)
        else:
            start, end = _centered_region(chrom, start)
        return {
            "kind": "coordinate",
            "label": normalized,
            "chrom": chrom,
            "start": start,
            "end": end,
        }

    if RSID_PATTERN.fullmatch(normalized):
        row = connection.execute(
            """
            SELECT chrom, pos, rsid, variant_id
            FROM variants
            WHERE lower(rsid) = lower(?)
            ORDER BY pos, variant_id
            LIMIT 1
            """,
            [normalized],
        ).fetchone()
        if row is None:
            raise ValueError("this rsID is not recorded in the selected bundle")
        chrom = _canonical_chromosome(row[0])
        start, end = _centered_region(chrom, int(row[1]))
        return {
            "kind": "rsid",
            "label": str(row[2] or normalized),
            "variant_id": row[3],
            "position": int(row[1]),
            "chrom": chrom,
            "start": start,
            "end": end,
        }

    if not GENE_PATTERN.fullmatch(normalized):
        raise ValueError("enter a gene, rsID, or genomic coordinate")

    gene_index = workspace / "gene_index.parquet"
    row = None
    if gene_index.is_file():
        try:
            row = connection.execute(
                """
                SELECT gene_symbol, chrom,
                       min(start_pos)::BIGINT AS start_pos,
                       max(end_pos)::BIGINT AS end_pos
                FROM read_parquet(?)
                WHERE upper(gene_symbol) = upper(?)
                GROUP BY gene_symbol, chrom
                ORDER BY max(end_pos) - min(start_pos) DESC
                LIMIT 1
                """,
                [str(gene_index), normalized],
            ).fetchone()
        except duckdb.Error:
            row = None
    if row is None:
        row = connection.execute(
            """
            SELECT min(gene.symbol), chrom,
                   min(pos)::BIGINT AS start_pos,
                   max(pos)::BIGINT AS end_pos
            FROM variants
            WHERE upper(gene.symbol) = upper(?)
            GROUP BY chrom
            ORDER BY max(pos) - min(pos) DESC
            LIMIT 1
            """,
            [normalized],
        ).fetchone()
    if row is None:
        raise ValueError("this gene is not recorded in the selected bundle")
    chrom = _canonical_chromosome(row[1])
    gene_start = int(row[2])
    gene_end = int(row[3])
    start, end = _gene_region(chrom, gene_start, gene_end)
    return {
        "kind": "gene",
        "label": str(row[0] or normalized).upper(),
        "chrom": chrom,
        "start": start,
        "end": end,
        "gene_start": gene_start,
        "gene_end": gene_end,
    }


def _track_bins(start: int, end: int) -> List[Dict[str, Any]]:
    region_length = end - start + 1
    bin_count = min(TRACK_BIN_COUNT, region_length)
    bins = []
    for index in range(bin_count):
        bin_start = start + math.floor(region_length * index / bin_count)
        bin_end = start + math.floor(region_length * (index + 1) / bin_count) - 1
        bins.append(
            {
                "index": index,
                "start": bin_start,
                "end": max(bin_start, bin_end),
                "variant_count": 0,
                "callable_bases": 0,
                "callability_percent": None,
                "callable_site_count": 0,
                "site_record_count": 0,
            }
        )
    return bins


def _variant_track(
    connection: duckdb.DuckDBPyConnection,
    chrom: str,
    start: int,
    end: int,
    bins: List[Dict[str, Any]],
) -> Dict[str, Any]:
    region_length = end - start + 1
    rows = connection.execute(
        """
        SELECT least(?, greatest(0, cast(floor(
                   (pos - ?) * ?::DOUBLE / ?
               ) AS INTEGER))) AS bin_index,
               count(*)::BIGINT AS variant_count
        FROM variants
        WHERE %s = %s
          AND pos BETWEEN ? AND ?
        GROUP BY bin_index
        """ % (_canonical_chrom_sql("chrom"), _canonical_chrom_sql("?")),
        [
            len(bins) - 1,
            start,
            len(bins),
            region_length,
            chrom,
            start,
            end,
        ],
    ).fetchall()
    total = 0
    for index, count in rows:
        value = int(count)
        bins[int(index)]["variant_count"] = value
        total += value
    return {"total": total, "bins": bins}


def _gene_track(
    connection: duckdb.DuckDBPyConnection,
    workspace: Path,
    chrom: str,
    start: int,
    end: int,
) -> Dict[str, Any]:
    path = workspace / "gene_index.parquet"
    if not path.is_file():
        return {"state": "not_included", "source": None, "genes": []}
    try:
        cursor = connection.execute(
            """
            SELECT gene_symbol, chrom, start_pos, end_pos,
                   variant_count, actionable_count
            FROM read_parquet(?)
            WHERE %s = %s
              AND start_pos <= ? AND end_pos >= ?
            ORDER BY start_pos, end_pos, gene_symbol
            LIMIT 200
            """ % (_canonical_chrom_sql("chrom"), _canonical_chrom_sql("?")),
            [str(path), chrom, end, start],
        )
        return {
            "state": "available",
            "source": path.name,
            "genes": _rows(cursor),
        }
    except duckdb.Error:
        return {"state": "unavailable", "source": path.name, "genes": []}


def _annotation_track(
    connection: duckdb.DuckDBPyConnection,
    chrom: str,
    start: int,
    end: int,
) -> Dict[str, Any]:
    expressions = {
        "clinical_grade": ("clinical_grade", "CAST(NULL AS BOOLEAN)"),
        "clinvar_significance": (
            "pathogenicity.clinvar_significance",
            "CAST(NULL AS VARCHAR)",
        ),
        "is_gwas_hit": (
            "trait_associations.is_gwas_hit",
            "CAST(NULL AS BOOLEAN)",
        ),
        "is_pgx": (
            "pharmacogenomics.is_pgx",
            "CAST(NULL AS BOOLEAN)",
        ),
        "gene": ("gene.symbol", "CAST(NULL AS VARCHAR)"),
    }
    available = {
        name: _has_expression(connection, expression)
        for name, (expression, _fallback) in expressions.items()
    }
    conditions = []
    if available["clinical_grade"]:
        conditions.append("clinical_grade IS TRUE")
    if available["clinvar_significance"]:
        conditions.append("pathogenicity.clinvar_significance IS NOT NULL")
    if available["is_gwas_hit"]:
        conditions.append("trait_associations.is_gwas_hit IS TRUE")
    if available["is_pgx"]:
        conditions.append("pharmacogenomics.is_pgx IS TRUE")
    if not conditions:
        return {"state": "not_included", "total": 0, "points": []}

    selected = {
        name: expression if available[name] else fallback
        for name, (expression, fallback) in expressions.items()
    }
    predicate = " OR ".join("(%s)" % condition for condition in conditions)
    parameters: List[Any] = [chrom, start, end]
    total = int(
        connection.execute(
            """
            SELECT count(*)::BIGINT
            FROM variants
            WHERE %s = %s
              AND pos BETWEEN ? AND ?
              AND (%s)
            """
            % (
                _canonical_chrom_sql("chrom"),
                _canonical_chrom_sql("?"),
                predicate,
            ),
            parameters,
        ).fetchone()[0]
    )
    cursor = connection.execute(
        """
        SELECT variant_id, rsid, pos,
               %s AS gene,
               %s AS clinical_grade,
               %s AS clinvar_significance,
               %s AS is_gwas_hit,
               %s AS is_pgx
        FROM variants
        WHERE %s = %s
          AND pos BETWEEN ? AND ?
          AND (%s)
        ORDER BY pos, variant_id
        LIMIT 200
        """
        % (
            selected["gene"],
            selected["clinical_grade"],
            selected["clinvar_significance"],
            selected["is_gwas_hit"],
            selected["is_pgx"],
            _canonical_chrom_sql("chrom"),
            _canonical_chrom_sql("?"),
            predicate,
        ),
        parameters,
    )
    points = _rows(cursor)
    for point in points:
        labels = []
        if point.get("clinical_grade"):
            labels.append("Bundle clinical flag")
        if point.get("clinvar_significance"):
            labels.append("ClinVar: %s" % point["clinvar_significance"])
        if point.get("is_gwas_hit"):
            labels.append("Research association")
        if point.get("is_pgx"):
            labels.append("Pharmacogenomic annotation")
        point["labels"] = labels
    return {
        "state": "available",
        "total": total,
        "truncated": total > len(points),
        "points": points,
    }


def _callability_track(
    connection: duckdb.DuckDBPyConnection,
    workspace: Path,
    chrom: str,
    start: int,
    end: int,
    bins: List[Dict[str, Any]],
) -> Dict[str, Any]:
    candidates = (
        (workspace / "callable_regions.parquet", "interval_records"),
        (workspace / "callability.parquet", "site_records"),
    )
    selected = next(
        ((path, kind) for path, kind in candidates if path.is_file()),
        None,
    )
    if selected is None:
        return {"state": "not_included", "kind": None, "bins": bins}
    path, kind = selected
    try:
        columns = {
            str(row[0])
            for row in connection.execute(
                "DESCRIBE SELECT * FROM read_parquet(?)", [str(path)]
            ).fetchall()
        }
    except duckdb.Error:
        return {
            "state": "unavailable",
            "kind": kind,
            "source": path.name,
            "bins": bins,
        }
    required = {"chrom", "callable"}
    if kind == "interval_records":
        required.update({"start_pos", "end_pos"})
    else:
        required.add("pos")
    if not required.issubset(columns):
        return {
            "state": "unavailable",
            "kind": kind,
            "source": path.name,
            "bins": bins,
        }

    connection.execute(
        "CREATE TEMP TABLE region_bins "
        "(bin_index INTEGER, start_pos BIGINT, end_pos BIGINT)"
    )
    connection.executemany(
        "INSERT INTO region_bins VALUES (?, ?, ?)",
        [(row["index"], row["start"], row["end"]) for row in bins],
    )
    if kind == "interval_records":
        rows = connection.execute(
            """
            WITH normalized AS (
                SELECT greatest(cast(start_pos AS BIGINT), ?) AS start_pos,
                       least(cast(end_pos AS BIGINT), ?) AS end_pos
                FROM read_parquet(?)
                WHERE %s = %s
                  AND callable IS TRUE
                  AND start_pos IS NOT NULL AND end_pos IS NOT NULL
                  AND start_pos <= end_pos
                  AND start_pos <= ? AND end_pos >= ?
            ), running AS (
                SELECT *,
                       max(end_pos) OVER (
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
                           ORDER BY start_pos, end_pos
                           ROWS UNBOUNDED PRECEDING
                       ) AS interval_group
                FROM running
            ), merged AS (
                SELECT min(start_pos)::BIGINT AS start_pos,
                       max(end_pos)::BIGINT AS end_pos
                FROM grouped
                GROUP BY interval_group
            )
            SELECT bins.bin_index,
                   sum(
                       least(merged.end_pos, bins.end_pos)
                       - greatest(merged.start_pos, bins.start_pos)
                       + 1
                   )::BIGINT AS callable_bases
            FROM merged
            JOIN region_bins AS bins
              ON merged.start_pos <= bins.end_pos
             AND merged.end_pos >= bins.start_pos
            GROUP BY bins.bin_index
            ORDER BY bins.bin_index
            """ % (_canonical_chrom_sql("chrom"), _canonical_chrom_sql("?")),
            [start, end, str(path), chrom, end, start],
        ).fetchall()
        total_callable_bases = 0
        for index, callable_bases in rows:
            bin_row = bins[int(index)]
            covered = int(callable_bases)
            bin_length = bin_row["end"] - bin_row["start"] + 1
            bin_row["callable_bases"] = covered
            bin_row["callability_percent"] = round(covered / bin_length * 100, 2)
            total_callable_bases += covered
        region_length = end - start + 1
        return {
            "state": "available",
            "kind": kind,
            "source": path.name,
            "callable_bases": total_callable_bases,
            "coverage_percent": round(total_callable_bases / region_length * 100, 2),
            "bins": bins,
        }

    rows = connection.execute(
        """
        SELECT bins.bin_index,
               count(*)::BIGINT AS site_record_count,
               count(*) FILTER (WHERE sites.callable IS TRUE)::BIGINT
                   AS callable_site_count
        FROM read_parquet(?) AS sites
        JOIN region_bins AS bins
          ON sites.pos BETWEEN bins.start_pos AND bins.end_pos
        WHERE %s = %s
          AND sites.pos BETWEEN ? AND ?
        GROUP BY bins.bin_index
        ORDER BY bins.bin_index
        """ % (
            _canonical_chrom_sql("sites.chrom"),
            _canonical_chrom_sql("?"),
        ),
        [str(path), chrom, start, end],
    ).fetchall()
    total_records = 0
    total_sites = 0
    for index, record_count, callable_count in rows:
        bin_row = bins[int(index)]
        bin_row["site_record_count"] = int(record_count)
        bin_row["callable_site_count"] = int(callable_count)
        total_records += int(record_count)
        total_sites += int(callable_count)
    return {
        "state": "available" if total_records else "included_empty",
        "kind": kind,
        "source": path.name,
        "record_count": total_records,
        "site_count": total_sites,
        "coverage_percent": None,
        "bins": bins,
    }


def region_browser_for_workspace(
    workspace_path: str,
    genome_build: str,
    *,
    query: Optional[str] = None,
    chrom: Optional[str] = None,
    start: Optional[int] = None,
    end: Optional[int] = None,
    page: int = 1,
) -> Dict[str, Any]:
    if genome_build != "GRCh38":
        raise ValueError("this genome build is not covered by the region browser")
    workspace = Path(workspace_path).resolve()
    variants = workspace / "variants.parquet"
    if not variants.is_dir():
        raise ValueError("workspace does not contain variants.parquet")

    connection = duckdb.connect()
    try:
        connection.execute("PRAGMA threads=2")
        connection.execute(
            "CREATE VIEW variants AS SELECT * FROM read_parquet("
            "'%s/**/*.parquet', hive_partitioning=true)" % _sql_path(variants)
        )
        if query is not None:
            target = _resolve_query(connection, workspace, query)
            selected_chrom = target["chrom"]
            selected_start = target["start"]
            selected_end = target["end"]
        else:
            if chrom is None or start is None or end is None:
                raise ValueError("region browser request is incomplete")
            selected_chrom = _canonical_chromosome(chrom)
            selected_start, selected_end = _bounded_region(
                selected_chrom, start, end
            )
            target = {
                "kind": "region",
                "label": "%s:%d-%d"
                % (selected_chrom, selected_start, selected_end),
                "chrom": selected_chrom,
                "start": selected_start,
                "end": selected_end,
            }

        variant_bins = _track_bins(selected_start, selected_end)
        callability_bins = _track_bins(selected_start, selected_end)
        variant_track = _variant_track(
            connection,
            selected_chrom,
            selected_start,
            selected_end,
            variant_bins,
        )
        genes = _gene_track(
            connection,
            workspace,
            selected_chrom,
            selected_start,
            selected_end,
        )
        annotations = _annotation_track(
            connection,
            selected_chrom,
            selected_start,
            selected_end,
        )
        callability = _callability_track(
            connection,
            workspace,
            selected_chrom,
            selected_start,
            selected_end,
            callability_bins,
        )
    finally:
        connection.close()

    records = variants_for_region(
        str(workspace),
        selected_chrom,
        selected_start,
        selected_end,
        page=page,
    )
    return {
        "genome_build": genome_build,
        "target": target,
        "region": {
            "chrom": selected_chrom,
            "start": selected_start,
            "end": selected_end,
            "length": selected_end - selected_start + 1,
            "chromosome_length": CHROMOSOME_LENGTHS[selected_chrom],
        },
        "genes": genes,
        "annotations": annotations,
        "variants": variant_track,
        "callability": callability,
        "records": records,
    }
