from __future__ import annotations

from typing import Optional, Set


def _text_expression(
    columns: Set[str], *candidates: str, fallback: str = "CAST(NULL AS VARCHAR)"
) -> str:
    expressions = [
        "CAST(source.%s AS VARCHAR)" % candidate
        for candidate in candidates
        if candidate in columns
    ]
    if not expressions:
        return fallback
    if len(expressions) == 1:
        return expressions[0]
    return "COALESCE(%s)" % ", ".join(expressions + [fallback])


def clinical_findings_projection(columns: Set[str]) -> Optional[str]:
    if "clinical_grade" not in columns:
        return None
    if not {"finding_id", "variant_id"}.intersection(columns):
        return None
    if not {"condition", "clinvar_disease_names"}.intersection(columns):
        return None
    if not {"classification", "clinvar_significance"}.intersection(columns):
        return None

    finding_id = _text_expression(columns, "finding_id", "variant_id")
    condition = _text_expression(columns, "condition", "clinvar_disease_names")
    claim_type = _text_expression(
        columns,
        "claim_type",
        "finding_category",
        fallback="'variant_classification'",
    )
    classification = _text_expression(
        columns, "classification", "clinvar_significance"
    )
    variant_id = _text_expression(columns, "variant_id")
    gene_symbol = _text_expression(columns, "gene_symbol")

    if "evidence_ids" in columns:
        evidence_ids = "COALESCE(source.evidence_ids, []::VARCHAR[])"
    elif "clinvar_id" in columns:
        evidence_ids = """
            CASE
                WHEN source.clinvar_id IS NOT NULL
                    THEN [CAST(source.clinvar_id AS VARCHAR)]
                WHEN source.variant_id IS NOT NULL
                    THEN [CAST(source.variant_id AS VARCHAR)]
                ELSE []::VARCHAR[]
            END
        """
    else:
        evidence_ids = """
            CASE
                WHEN source.variant_id IS NOT NULL
                    THEN [CAST(source.variant_id AS VARCHAR)]
                ELSE []::VARCHAR[]
            END
        """

    return """
        %s AS finding_id,
        %s AS condition,
        %s AS claim_type,
        %s AS classification,
        CAST(source.clinical_grade AS BOOLEAN) AS clinical_grade,
        %s AS variant_id,
        %s AS gene_symbol,
        %s AS evidence_ids,
        %s AS call_confidence,
        %s AS clinvar_significance,
        %s AS clinvar_has_conflicts,
        %s AS clinvar_conflict_summary,
        %s AS clinvar_review_stars,
        %s AS clinvar_submitters_count,
        %s AS clinvar_id
    """ % (
        finding_id,
        condition,
        claim_type,
        classification,
        variant_id,
        gene_symbol,
        evidence_ids,
        _text_expression(columns, "call_confidence"),
        _text_expression(columns, "clinvar_significance"),
        "CAST(source.clinvar_has_conflicts AS BOOLEAN)"
        if "clinvar_has_conflicts" in columns
        else "CAST(NULL AS BOOLEAN)",
        _text_expression(columns, "clinvar_conflict_summary"),
        "CAST(source.clinvar_review_stars AS BIGINT)"
        if "clinvar_review_stars" in columns
        else "CAST(NULL AS BIGINT)",
        "CAST(source.clinvar_submitters_count AS BIGINT)"
        if "clinvar_submitters_count" in columns
        else "CAST(NULL AS BIGINT)",
        _text_expression(columns, "clinvar_id"),
    )


def clinical_evidence_projection(columns: Set[str]) -> Optional[str]:
    if "evidence_id" in columns:
        evidence_id = "CAST(source.evidence_id AS VARCHAR)"
    elif {"clinvar_id", "variant_id"}.intersection(columns):
        evidence_id = _text_expression(columns, "clinvar_id", "variant_id")
    else:
        return None

    source_name = _text_expression(
        columns,
        "source",
        fallback="'ClinVar'" if "clinvar_id" in columns else "CAST(NULL AS VARCHAR)",
    )
    return """
        %s AS evidence_id,
        %s AS source,
        %s AS source_record_id,
        %s AS source_version,
        %s AS assertion,
        %s AS review_status,
        %s AS retrieved_at
    """ % (
        evidence_id,
        source_name,
        _text_expression(columns, "source_record_id", "clinvar_id"),
        _text_expression(columns, "source_version"),
        _text_expression(columns, "assertion", "clinvar_significance"),
        _text_expression(columns, "review_status", "clinvar_review_status"),
        "source.retrieved_at"
        if "retrieved_at" in columns
        else "CAST(NULL AS TIMESTAMP)",
    )
