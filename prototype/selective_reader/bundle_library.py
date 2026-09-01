from __future__ import annotations

import json
import os
import re
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .core import WorkspaceReport


# Prototype question: can a validated workspace become a reusable, named local
# bundle library without copying the source archive or duplicating extracted data?
LIBRARY_VERSION = 1
MAX_NICKNAME_LENGTH = 80


@dataclass(frozen=True)
class BundleEntry:
    bundle_id: str
    nickname: str
    archive: str
    file_name: str
    schema_version: str
    genome_build: str
    generated_at: str
    validated_at: str
    stored_bytes: int
    last_opened_at: str


def bundle_id_for_report(report: WorkspaceReport) -> str:
    return Path(report.workspace).name


def default_nickname(archive: str) -> str:
    name = Path(archive).name
    for suffix in (".genome.tar.gz", ".genome.tar", ".tar.gz", ".tar", ".genome"):
        if name.lower().endswith(suffix):
            name = name[: -len(suffix)]
            break
    name = re.sub(r"[_-]+", " ", name).strip()
    return name or "Genome bundle"


def _unique_nickname(entries: List[BundleEntry], requested: str) -> str:
    existing = {entry.nickname.casefold() for entry in entries}
    if requested.casefold() not in existing:
        return requested
    index = 2
    while ("%s %d" % (requested, index)).casefold() in existing:
        index += 1
    return "%s %d" % (requested, index)


def register_report(
    entries: List[BundleEntry], report: WorkspaceReport, opened_at: str
) -> List[BundleEntry]:
    bundle_id = bundle_id_for_report(report)
    existing = next(
        (entry for entry in entries if entry.bundle_id == bundle_id), None
    )
    nickname = (
        existing.nickname
        if existing is not None
        else _unique_nickname(entries, default_nickname(report.archive))
    )
    updated = BundleEntry(
        bundle_id=bundle_id,
        nickname=nickname,
        archive=report.archive,
        file_name=Path(report.archive).name,
        schema_version=report.schema_version,
        genome_build=report.genome_build,
        generated_at=report.generated_at,
        validated_at=report.validated_at,
        stored_bytes=report.extracted_bytes,
        last_opened_at=opened_at,
    )
    return [updated] + [entry for entry in entries if entry.bundle_id != bundle_id]


def rename_bundle(
    entries: List[BundleEntry], bundle_id: str, nickname: str
) -> List[BundleEntry]:
    cleaned = nickname.strip()
    if not cleaned:
        raise ValueError("nickname cannot be empty")
    if len(cleaned) > MAX_NICKNAME_LENGTH:
        raise ValueError("nickname is too long")
    if any(ord(character) < 32 for character in cleaned):
        raise ValueError("nickname contains unsupported characters")
    if any(
        entry.bundle_id != bundle_id and entry.nickname.casefold() == cleaned.casefold()
        for entry in entries
    ):
        raise ValueError("another bundle already uses that nickname")

    found = False
    renamed: List[BundleEntry] = []
    for entry in entries:
        if entry.bundle_id == bundle_id:
            renamed.append(BundleEntry(**{**asdict(entry), "nickname": cleaned}))
            found = True
        else:
            renamed.append(entry)
    if not found:
        raise ValueError("bundle was not found")
    return renamed


class BundleLibrary:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()

    def _load(self) -> List[BundleEntry]:
        if not self.path.is_file():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise ValueError("bundle library file is invalid") from error
        if not isinstance(payload, dict):
            raise ValueError("bundle library file is invalid")
        if payload.get("version") != LIBRARY_VERSION:
            raise ValueError("bundle library file uses an unsupported version")
        entries = payload.get("bundles")
        if not isinstance(entries, list) or not all(
            isinstance(entry, dict) for entry in entries
        ):
            raise ValueError("bundle library file is invalid")
        try:
            return [BundleEntry(**entry) for entry in entries]
        except (TypeError, ValueError) as error:
            raise ValueError("bundle library file is invalid") from error

    def _save(self, entries: List[BundleEntry]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + ".tmp")
        payload = {
            "version": LIBRARY_VERSION,
            "bundles": [asdict(entry) for entry in entries],
        }
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.chmod(temporary, 0o600)
        temporary.replace(self.path)

    def entries(self) -> List[BundleEntry]:
        with self._lock:
            return self._load()

    def find(self, bundle_id: str) -> Optional[BundleEntry]:
        return next(
            (entry for entry in self.entries() if entry.bundle_id == bundle_id),
            None,
        )

    def register(self, report: WorkspaceReport) -> BundleEntry:
        with self._lock:
            opened_at = datetime.now(timezone.utc).isoformat()
            entries = register_report(self._load(), report, opened_at)
            self._save(entries)
            return entries[0]

    def rename(self, bundle_id: str, nickname: str) -> BundleEntry:
        with self._lock:
            entries = rename_bundle(self._load(), bundle_id, nickname)
            self._save(entries)
            return next(entry for entry in entries if entry.bundle_id == bundle_id)

    def remove(self, bundle_id: str) -> BundleEntry:
        with self._lock:
            entries = self._load()
            removed = next(
                (entry for entry in entries if entry.bundle_id == bundle_id),
                None,
            )
            if removed is None:
                raise ValueError("bundle was not found")
            self._save(
                [entry for entry in entries if entry.bundle_id != bundle_id]
            )
            return removed

    def public_entries(self) -> List[Dict[str, Any]]:
        return [
            {
                "bundle_id": entry.bundle_id,
                "nickname": entry.nickname,
                "file_name": entry.file_name,
                "schema_version": entry.schema_version,
                "genome_build": entry.genome_build,
                "generated_at": entry.generated_at,
                "validated_at": entry.validated_at,
                "stored_bytes": entry.stored_bytes,
                "last_opened_at": entry.last_opened_at,
                "available": Path(entry.archive).is_file(),
            }
            for entry in self.entries()
        ]
