from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


SAVED_RESULTS_VERSION = 1
MAX_SAVED_RESULTS_PER_BUNDLE = 500
MAX_SAVED_RECORD_BYTES = 128 * 1024
SUPPORTED_SECTIONS = {
    "clinical_findings",
    "pharmacogenomics",
    "polygenic_scores",
    "trait_variants",
    "genes",
    "variants",
    "gwas",
}
BUNDLE_EXPORT_FIELDS = (
    "nickname",
    "schema_version",
    "genome_build",
    "generated_at",
)


def _clean_json_value(value: Any, depth: int = 0) -> Any:
    if depth > 8:
        raise ValueError("saved record is too deeply nested")
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError("saved record contains an unsupported number")
        if value.is_integer():
            return int(value)
        return value
    if isinstance(value, list):
        return [_clean_json_value(item, depth + 1) for item in value]
    if isinstance(value, dict):
        return {
            key: _clean_json_value(item, depth + 1)
            for key, item in value.items()
            if isinstance(key, str) and not key.startswith("_")
        }
    raise ValueError("saved record contains an unsupported value")


def _clean_record(record: Dict[str, Any]) -> Dict[str, Any]:
    cleaned = _clean_json_value(record)
    if not isinstance(cleaned, dict):
        raise ValueError("saved record must be an object")
    section = cleaned.get("section")
    if section not in SUPPORTED_SECTIONS:
        raise ValueError("unsupported record section")
    serialized = json.dumps(
        cleaned,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    if len(serialized) > MAX_SAVED_RECORD_BYTES:
        raise ValueError("saved record is too large")
    return cleaned


def _saved_id(record: Dict[str, Any]) -> str:
    canonical = json.dumps(
        record,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]


def saved_result_id(record: Dict[str, Any]) -> str:
    return _saved_id(_clean_record(record))


def _export_file_stem(nickname: Any) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", str(nickname or "genome")).strip("-")
    return (cleaned or "genome").lower() + "-saved-results"


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (list, dict)):
        text = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    else:
        text = str(value)
    if text.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


class SavedResultsStore:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()

    def _load(self) -> Dict[str, List[Dict[str, Any]]]:
        if not self.path.is_file():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return {}
        if not isinstance(payload, dict):
            return {}
        if payload.get("version") != SAVED_RESULTS_VERSION:
            return {}
        bundles = payload.get("bundles")
        if not isinstance(bundles, dict):
            return {}
        return {
            bundle_id: [entry for entry in entries if isinstance(entry, dict)]
            for bundle_id, entries in bundles.items()
            if isinstance(bundle_id, str) and isinstance(entries, list)
        }

    def _save(self, bundles: Dict[str, List[Dict[str, Any]]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + ".tmp")
        temporary.write_text(
            json.dumps(
                {"version": SAVED_RESULTS_VERSION, "bundles": bundles},
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n",
            encoding="utf-8",
        )
        os.chmod(temporary, 0o600)
        temporary.replace(self.path)

    def entries(self, bundle_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            entries = self._load().get(bundle_id, [])
            return sorted(
                entries,
                key=lambda entry: (str(entry.get("saved_at", "")), str(entry.get("saved_id", ""))),
                reverse=True,
            )

    def add(
        self,
        bundle_id: str,
        query: str,
        record: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not bundle_id:
            raise ValueError("bundle is not selected")
        cleaned_query = query.strip()
        if not cleaned_query or len(cleaned_query) > 200:
            raise ValueError("saved search query is invalid")
        cleaned_record = _clean_record(record)
        saved_id = saved_result_id(cleaned_record)
        with self._lock:
            bundles = self._load()
            entries = bundles.setdefault(bundle_id, [])
            existing = next(
                (entry for entry in entries if entry.get("saved_id") == saved_id),
                None,
            )
            if existing is not None:
                return existing
            if len(entries) >= MAX_SAVED_RESULTS_PER_BUNDLE:
                raise ValueError("saved results limit reached for this bundle")
            entry = {
                "saved_id": saved_id,
                "saved_at": datetime.now(timezone.utc).isoformat(),
                "query": cleaned_query,
                "section": cleaned_record["section"],
                "record": cleaned_record,
            }
            entries.append(entry)
            self._save(bundles)
            return entry

    def remove(self, bundle_id: str, saved_id: str) -> bool:
        with self._lock:
            bundles = self._load()
            entries = bundles.get(bundle_id, [])
            retained = [entry for entry in entries if entry.get("saved_id") != saved_id]
            if len(retained) == len(entries):
                return False
            if retained:
                bundles[bundle_id] = retained
            else:
                bundles.pop(bundle_id, None)
            self._save(bundles)
            return True

    def export(
        self,
        bundle_id: str,
        bundle: Dict[str, Any],
        format_name: str,
    ) -> Dict[str, str]:
        if format_name not in {"json", "csv"}:
            raise ValueError("unsupported export format")
        entries = self.entries(bundle_id)
        exported_bundle = {
            field: bundle.get(field)
            for field in BUNDLE_EXPORT_FIELDS
        }
        exported_results = [
            {
                "saved_at": entry.get("saved_at"),
                "search": entry.get("query"),
                "result_type": entry.get("section"),
                "record": {
                    key: value
                    for key, value in entry.get("record", {}).items()
                    if key != "section"
                },
            }
            for entry in entries
        ]
        stem = _export_file_stem(exported_bundle.get("nickname"))
        if format_name == "json":
            content = json.dumps(
                {
                    "bundle": exported_bundle,
                    "results": exported_results,
                },
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
                allow_nan=False,
            ) + "\n"
            return {
                "file_name": stem + ".json",
                "content_type": "application/json",
                "content": content,
            }

        record_fields = sorted(
            {
                key
                for result in exported_results
                for key in result["record"].keys()
            }
        )
        fields = [
            "bundle_nickname",
            "schema_version",
            "genome_build",
            "bundle_generated_at",
            "saved_at",
            "search",
            "result_type",
        ] + record_fields
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for result in exported_results:
            record = result["record"]
            row = {
                "bundle_nickname": _csv_value(exported_bundle.get("nickname")),
                "schema_version": _csv_value(exported_bundle.get("schema_version")),
                "genome_build": _csv_value(exported_bundle.get("genome_build")),
                "bundle_generated_at": _csv_value(exported_bundle.get("generated_at")),
                "saved_at": _csv_value(result["saved_at"]),
                "search": _csv_value(result["search"]),
                "result_type": _csv_value(result["result_type"]),
            }
            row.update(
                {
                    field: _csv_value(record.get(field))
                    for field in record_fields
                }
            )
            writer.writerow(row)
        return {
            "file_name": stem + ".csv",
            "content_type": "text/csv",
            "content": output.getvalue(),
        }
