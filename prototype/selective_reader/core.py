from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import tarfile
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, List, Optional, Tuple

import duckdb

from .clinical_schema import (
    clinical_evidence_projection,
    clinical_findings_projection,
)

SUPPORTED_SCHEMA_MAJOR = 1
SUPPORTED_BUNDLE_SUFFIXES = (".genome.tar.gz", ".genome.tar")
GZIP_MAGIC = b"\x1f\x8b"
CHUNK_SIZE = 1024 * 1024
MAX_MANIFEST_BYTES = 5 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 100_000
MAX_ARCHIVE_MEMBER_BYTES = 128 * 1024 * 1024 * 1024
MAX_ARCHIVE_EXPANDED_BYTES = 256 * 1024 * 1024 * 1024
MAX_EXTRACTED_BYTES = 16 * 1024 * 1024 * 1024
MAX_VALIDATION_BYTES = 2 * 1024 * 1024 * 1024
MAX_ARCHIVE_COMPRESSION_RATIO = 200
MIN_COMPRESSION_RATIO_BYTES = 1024 * 1024 * 1024
RECEIPT_FILENAME = ".validation-receipt.json"
RECEIPT_VERSION = 2
RETAINED_FILES = frozenset(
    {
        "schema.json",
        "omissions.json",
        "clinical_findings.parquet",
        "clinical_evidence.parquet",
        "pharmacogenomics.parquet",
        "prs.parquet",
        "gwas_associations.parquet",
        "gene_index.parquet",
        "callability.parquet",
        "callable_regions.parquet",
    }
)
RETAINED_DIRECTORIES = frozenset({"variants.parquet"})
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
SCHEMA_VERSION_PATTERN = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$"
)
COORDINATE_PATTERN = re.compile(
    r"^(?:chr)?(?P<chrom>[0-9]+|X|Y|M):(?P<pos>[0-9]+)"
    r"(?::(?P<ref>[ACGT]+):(?P<alt>[ACGT]+))?$",
    re.IGNORECASE,
)
RSID_PATTERN = re.compile(r"^rs[0-9]+$", re.IGNORECASE)


@dataclass
class WorkspaceReport:
    archive: str
    workspace: str
    schema_version: str
    genome_build: str
    generated_at: str
    extracted_files: int
    extracted_bytes: int
    skipped_files: int
    skipped_bytes: int
    validated_entries: int
    elapsed_seconds: float
    reused_workspace: bool
    validation_mode: str
    validated_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SearchResult:
    query: str
    query_kind: str
    answerability: Dict[str, Any]
    hits: List[Dict[str, Any]]
    elapsed_seconds: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _safe_relative_path(name: str, root_name: str) -> Optional[str]:
    if not isinstance(name, str) or not name or "\\" in name:
        raise ValueError("archive contains an unsafe path: %s" % name)
    if any(ord(character) < 32 for character in name):
        raise ValueError("archive contains an unsafe path: %s" % name)
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("archive contains an unsafe path: %s" % name)
    if not path.parts:
        return None
    if path.parts[0] != root_name:
        raise ValueError("archive contains more than one top-level directory")
    if len(path.parts) == 1:
        return None
    relative = PurePosixPath(*path.parts[1:])
    for part in relative.parts:
        if ":" in part or part.rstrip(" .") != part:
            raise ValueError("archive contains an unsafe path: %s" % name)
        windows_name = part.split(".", 1)[0].casefold()
        if windows_name in {"con", "prn", "aux", "nul"} or re.fullmatch(
            r"(?:com|lpt)[1-9]", windows_name
        ):
            raise ValueError("archive contains an unsafe path: %s" % name)
    return relative.as_posix()


def is_supported_bundle_path(path: str) -> bool:
    normalized = path.casefold()
    return any(normalized.endswith(suffix) for suffix in SUPPORTED_BUNDLE_SUFFIXES)


def _archive_read_modes(archive: Path) -> Tuple[str, str]:
    with archive.open("rb") as source:
        magic = source.read(len(GZIP_MAGIC))
    if magic == GZIP_MAGIC:
        return "r:gz", "r|gz"
    return "r:", "r|"


def _safe_manifest_path(name: Any) -> str:
    if not isinstance(name, str):
        raise ValueError("manifest contains a non-string file path")
    relative = _safe_relative_path("bundle/" + name, "bundle")
    if relative is None or relative != name:
        raise ValueError("manifest contains an unsafe or non-canonical path: %s" % name)
    if relative == "manifest.json":
        raise ValueError("manifest.json must not declare itself")
    return relative


def _destination_path(workspace: Path, relative_path: str) -> Path:
    base = workspace.resolve()
    destination = base.joinpath(*PurePosixPath(relative_path).parts).resolve()
    try:
        destination.relative_to(base)
    except ValueError as error:
        raise ValueError("archive contains an unsafe path: %s" % relative_path) from error
    return destination


def _should_extract(relative_path: str) -> bool:
    return relative_path in RETAINED_FILES or any(
        relative_path == directory or relative_path.startswith(directory + "/")
        for directory in RETAINED_DIRECTORIES
    )


def _reject_duplicate_json_keys(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("manifest contains a duplicate JSON key: %s" % key)
        result[key] = value
    return result


def _parse_manifest(manifest_bytes: bytes) -> Dict[str, Any]:
    manifest = json.loads(
        manifest_bytes,
        object_pairs_hook=_reject_duplicate_json_keys,
    )
    if not isinstance(manifest, dict):
        raise ValueError("manifest.json must contain a JSON object")
    return manifest


def _validated_manifest_files(manifest: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    candidate = manifest.get("files")
    if not isinstance(candidate, dict):
        raise ValueError("manifest files field is missing or invalid")

    declared: Dict[str, Dict[str, Any]] = {}
    casefolded_paths: Dict[str, str] = {}
    for untrusted_path, untrusted_metadata in candidate.items():
        relative_path = _safe_manifest_path(untrusted_path)
        casefolded = relative_path.casefold()
        previous = casefolded_paths.get(casefolded)
        if previous is not None and previous != relative_path:
            raise ValueError(
                "manifest contains paths that collide on common filesystems: %s and %s"
                % (previous, relative_path)
            )
        casefolded_paths[casefolded] = relative_path
        if not isinstance(untrusted_metadata, dict):
            raise ValueError("manifest metadata is invalid for: %s" % relative_path)
        recorded_hash = untrusted_metadata.get("sha256")
        if not isinstance(recorded_hash, str) or not SHA256_PATTERN.fullmatch(
            recorded_hash
        ):
            raise ValueError("manifest hash is invalid for: %s" % relative_path)
        recorded_bytes = untrusted_metadata.get("bytes")
        if recorded_bytes is not None and (
            isinstance(recorded_bytes, bool)
            or not isinstance(recorded_bytes, int)
            or recorded_bytes < 0
        ):
            raise ValueError("manifest byte count is invalid for: %s" % relative_path)
        declared[relative_path] = untrusted_metadata

    if "schema.json" not in declared:
        raise ValueError("schema.json must be declared in manifest files")
    if "variants.parquet" not in declared:
        raise ValueError("variants.parquet must be declared in manifest files")
    return declared


def _archive_budget(
    member_count: int,
    expanded_bytes: int,
    member_size: int,
    archive_size: int,
) -> int:
    if member_count > MAX_ARCHIVE_MEMBERS:
        raise ValueError("archive contains too many entries")
    if member_size < 0 or member_size > MAX_ARCHIVE_MEMBER_BYTES:
        raise ValueError("archive member exceeds the supported size limit")
    updated_bytes = expanded_bytes + member_size
    if updated_bytes > MAX_ARCHIVE_EXPANDED_BYTES:
        raise ValueError("archive exceeds the supported expansion limit")
    compression_limit = max(
        MIN_COMPRESSION_RATIO_BYTES,
        archive_size * MAX_ARCHIVE_COMPRESSION_RATIO,
    )
    if updated_bytes > compression_limit:
        raise ValueError("archive exceeds the supported compression ratio")
    return updated_bytes


def _read_manifest(archive: Path) -> Tuple[str, bytes, Dict[str, Any]]:
    archive_size = archive.stat().st_size
    manifest_mode, _stream_mode = _archive_read_modes(archive)
    with tarfile.open(str(archive), mode=manifest_mode) as bundle:
        root_name = None
        member_count = 0
        expanded_bytes = 0
        for member in bundle:
            member_count += 1
            expanded_bytes = _archive_budget(
                member_count,
                expanded_bytes,
                member.size,
                archive_size,
            )
            path = PurePosixPath(member.name)
            if not path.parts:
                continue
            if root_name is None:
                root_name = path.parts[0]
            relative_path = _safe_relative_path(member.name, root_name)
            if relative_path == "manifest.json":
                if not member.isfile():
                    raise ValueError("manifest.json is not a regular file")
                if member.size > MAX_MANIFEST_BYTES:
                    raise ValueError("manifest.json is unexpectedly large")
                source = bundle.extractfile(member)
                if source is None:
                    raise ValueError("manifest.json could not be read")
                manifest_bytes = source.read()
                if len(manifest_bytes) != member.size:
                    raise ValueError("manifest.json is truncated")
                manifest = _parse_manifest(manifest_bytes)
                return root_name, manifest_bytes, manifest
    raise ValueError("manifest.json was not found")


def _manifest_identity(manifest_bytes: bytes) -> str:
    return hashlib.sha256(manifest_bytes).hexdigest()[:20]


def _supports_schema_version(schema_version: Any) -> bool:
    if not isinstance(schema_version, str):
        return False
    match = SCHEMA_VERSION_PATTERN.fullmatch(schema_version)
    return match is not None and int(match.group(1)) == SUPPORTED_SCHEMA_MAJOR


def _archive_fingerprint(archive: Path) -> Dict[str, Any]:
    metadata = archive.stat()
    return {
        "path": str(archive),
        "size": metadata.st_size,
        "mtime_ns": metadata.st_mtime_ns,
        "device": metadata.st_dev,
        "inode": metadata.st_ino,
    }


def _workspace_matches_receipt(
    workspace: Path, receipt: Dict[str, Any]
) -> Tuple[bool, bool]:
    if receipt.get("version") != RECEIPT_VERSION:
        return False, False
    if not (workspace / "manifest.json").is_file():
        return False, False
    if not (workspace / "schema.json").is_file():
        return False, False
    if not (workspace / "variants.parquet").is_dir():
        return False, False

    manifest_bytes = (workspace / "manifest.json").read_bytes()
    if hashlib.sha256(manifest_bytes).hexdigest() != receipt.get("manifest_sha256"):
        return False, False
    manifest = _parse_manifest(manifest_bytes)
    declared = _validated_manifest_files(manifest)

    stored_entries = receipt.get("stored_entries")
    if not isinstance(stored_entries, dict):
        return False, False
    expected_paths = {
        relative_path for relative_path in declared if _should_extract(relative_path)
    }
    if set(stored_entries) != expected_paths:
        return False, False
    receipt_changed = False
    for relative_path, expected in stored_entries.items():
        if not isinstance(expected, dict):
            return False, False
        if _safe_manifest_path(relative_path) != relative_path:
            return False, False
        metadata = declared[relative_path]
        if expected.get("sha256") != metadata.get("sha256"):
            return False, False
        expected_kind = (
            "directory" if relative_path in RETAINED_DIRECTORIES else "file"
        )
        if expected.get("kind") != expected_kind:
            return False, False
        entry_path = workspace / relative_path
        current_snapshot = _workspace_entry_snapshot(entry_path, expected_kind)
        if current_snapshot == expected.get("snapshot"):
            continue
        actual_hash, actual_size = _hash_workspace_entry(
            entry_path,
            expected_kind,
        )
        if actual_hash != expected.get("sha256") or actual_size != expected.get(
            "bytes"
        ):
            return False, False
        verified_snapshot = _workspace_entry_snapshot(entry_path, expected_kind)
        if verified_snapshot != current_snapshot:
            return False, False
        expected["snapshot"] = verified_snapshot
        receipt_changed = True
    return True, receipt_changed


def _cached_workspace_report(
    archive: Path, workspace_root: Path, started: float
) -> Optional[WorkspaceReport]:
    if not workspace_root.is_dir():
        return None
    fingerprint = _archive_fingerprint(archive)
    for workspace in workspace_root.iterdir():
        if not workspace.is_dir() or ".partial-" in workspace.name:
            continue
        receipt_path = workspace / RECEIPT_FILENAME
        if not receipt_path.is_file():
            continue
        try:
            receipt = json.loads(receipt_path.read_text())
            if receipt.get("archive") != fingerprint:
                continue
            matches, receipt_changed = _workspace_matches_receipt(workspace, receipt)
            if not matches:
                continue
            if receipt_changed:
                temporary_receipt = receipt_path.with_name(receipt_path.name + ".tmp")
                try:
                    temporary_receipt.write_text(
                        json.dumps(receipt, indent=2, sort_keys=True) + "\n"
                    )
                    temporary_receipt.replace(receipt_path)
                finally:
                    temporary_receipt.unlink(missing_ok=True)
            report = receipt["report"]
            return WorkspaceReport(
                archive=str(archive),
                workspace=str(workspace),
                schema_version=report["schema_version"],
                genome_build=report["genome_build"],
                generated_at=report["generated_at"],
                extracted_files=report["extracted_files"],
                extracted_bytes=report["extracted_bytes"],
                skipped_files=report["skipped_files"],
                skipped_bytes=report["skipped_bytes"],
                validated_entries=report["validated_entries"],
                elapsed_seconds=round(time.monotonic() - started, 3),
                reused_workspace=True,
                validation_mode="cached",
                validated_at=receipt["validated_at"],
            )
        except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
            continue
    return None


def _ancestor_manifest_directories(
    relative_path: str, manifest_paths: Iterable[str]
) -> List[str]:
    return [
        candidate
        for candidate in manifest_paths
        if relative_path.startswith(candidate.rstrip("/") + "/")
    ]


def _hash_directory(path: Path) -> Tuple[str, int]:
    if path.is_symlink() or not path.is_dir():
        raise ValueError("workspace entry is not a regular directory: %s" % path)
    hasher = hashlib.sha256()
    total_bytes = 0
    members = sorted(path.rglob("*"))
    for member in members:
        if member.is_symlink():
            raise ValueError("workspace contains an unsupported link: %s" % member)
        if member.is_dir():
            continue
        if not member.is_file():
            raise ValueError("workspace contains a special file: %s" % member)
        hasher.update(member.relative_to(path).as_posix().encode("utf-8"))
        hasher.update(b"\0")
        with member.open("rb") as source:
            while True:
                chunk = source.read(CHUNK_SIZE)
                if not chunk:
                    break
                hasher.update(chunk)
                total_bytes += len(chunk)
    return hasher.hexdigest(), total_bytes


def _hash_file(path: Path) -> Tuple[str, int]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("workspace entry is not a regular file: %s" % path)
    hasher = hashlib.sha256()
    total_bytes = 0
    with path.open("rb") as source:
        while True:
            chunk = source.read(CHUNK_SIZE)
            if not chunk:
                break
            hasher.update(chunk)
            total_bytes += len(chunk)
    return hasher.hexdigest(), total_bytes


def _hash_workspace_entry(path: Path, kind: str) -> Tuple[str, int]:
    if kind == "directory":
        return _hash_directory(path)
    if kind == "file":
        return _hash_file(path)
    raise ValueError("receipt contains an unsupported workspace entry kind")


def _stat_snapshot(path: Path, kind: str, relative_path: str) -> Dict[str, Any]:
    metadata = path.stat()
    return {
        "path": relative_path,
        "kind": kind,
        "device": metadata.st_dev,
        "inode": metadata.st_ino,
        "size": metadata.st_size,
        "mtime_ns": metadata.st_mtime_ns,
        "ctime_ns": metadata.st_ctime_ns,
    }


def _workspace_entry_snapshot(path: Path, kind: str) -> Dict[str, Any]:
    if kind == "file":
        if path.is_symlink() or not path.is_file():
            raise ValueError("workspace entry is not a regular file: %s" % path)
        return _stat_snapshot(path, "file", ".")
    if kind != "directory":
        raise ValueError("receipt contains an unsupported workspace entry kind")
    if path.is_symlink() or not path.is_dir():
        raise ValueError("workspace entry is not a regular directory: %s" % path)

    entries = [_stat_snapshot(path, "directory", ".")]
    for member in sorted(path.rglob("*")):
        if member.is_symlink():
            raise ValueError("workspace contains an unsupported link: %s" % member)
        if member.is_dir():
            member_kind = "directory"
        elif member.is_file():
            member_kind = "file"
        else:
            raise ValueError("workspace contains a special file: %s" % member)
        entries.append(
            _stat_snapshot(
                member,
                member_kind,
                member.relative_to(path).as_posix(),
            )
        )
    return {"kind": "directory", "entries": entries}


def open_bundle(
    archive_path: str, workspace_root: Path, force_validate: bool = False
) -> WorkspaceReport:
    started = time.monotonic()
    archive = Path(archive_path).expanduser().resolve()
    if not archive.is_file():
        raise ValueError("archive does not exist: %s" % archive)

    if not force_validate:
        cached_report = _cached_workspace_report(archive, workspace_root, started)
        if cached_report is not None:
            return cached_report

    archive_fingerprint = _archive_fingerprint(archive)

    root_name, manifest_bytes, manifest = _read_manifest(archive)
    schema_version = manifest.get("schema_version")
    if not _supports_schema_version(schema_version):
        raise ValueError(
            "unsupported schema version: %r; Offline Explorer supports v1.x bundles"
            % schema_version
        )

    declared = _validated_manifest_files(manifest)

    workspace_root.mkdir(parents=True, exist_ok=True)
    final_workspace = workspace_root / _manifest_identity(manifest_bytes)
    temporary_workspace = Path(
        tempfile.mkdtemp(
            prefix=final_workspace.name + ".partial-", dir=str(workspace_root)
        )
    )
    validation_workspace = Path(
        tempfile.mkdtemp(
            prefix=final_workspace.name + ".validation-", dir=str(workspace_root)
        )
    )

    exact_hashes: Dict[str, str] = {}
    exact_sizes: Dict[str, int] = {}
    observed_directories = set()
    retained_entries = set()
    manifest_paths = tuple(declared.keys())
    extracted_files = 0
    extracted_bytes = 0
    skipped_files = 0
    skipped_bytes = 0
    validation_bytes = 0
    archive_member_count = 0
    archive_expanded_bytes = 0
    seen_entries: Dict[str, str] = {}
    manifest_seen = False

    try:
        _manifest_mode, stream_mode = _archive_read_modes(archive)
        with tarfile.open(str(archive), mode=stream_mode) as bundle:
            for member in bundle:
                archive_member_count += 1
                archive_expanded_bytes = _archive_budget(
                    archive_member_count,
                    archive_expanded_bytes,
                    member.size,
                    archive_fingerprint["size"],
                )
                relative_path = _safe_relative_path(member.name, root_name)
                if member.issym() or member.islnk():
                    raise ValueError("archive links are not supported: %s" % member.name)
                if relative_path is None:
                    if not member.isdir():
                        raise ValueError("archive root is not a directory")
                    continue
                collision_key = relative_path.casefold()
                previous = seen_entries.get(collision_key)
                if previous is not None:
                    raise ValueError(
                        "duplicate archive entry: %s conflicts with %s"
                        % (relative_path, previous)
                    )
                seen_entries[collision_key] = relative_path
                if member.isdir():
                    continue
                if not member.isfile():
                    raise ValueError(
                        "archive contains a non-regular entry: %s" % member.name
                    )

                source = bundle.extractfile(member)
                if source is None:
                    raise ValueError("archive member could not be read: %s" % member.name)

                if relative_path == "manifest.json":
                    if member.size > MAX_MANIFEST_BYTES:
                        raise ValueError("manifest.json is unexpectedly large")
                    current_manifest = source.read(MAX_MANIFEST_BYTES + 1)
                    if current_manifest != manifest_bytes or len(current_manifest) != member.size:
                        raise ValueError("manifest.json changed while the archive was read")
                    if extracted_bytes + member.size > MAX_EXTRACTED_BYTES:
                        raise ValueError("archive exceeds the supported extraction limit")
                    _destination_path(
                        temporary_workspace, "manifest.json"
                    ).write_bytes(manifest_bytes)
                    manifest_seen = True
                    extracted_files += 1
                    extracted_bytes += member.size
                    continue

                ancestors = _ancestor_manifest_directories(
                    relative_path, manifest_paths
                )
                if relative_path not in declared and not ancestors:
                    raise ValueError("undeclared archive entry: %s" % relative_path)
                observed_directories.update(ancestors)
                retained_ancestors = [
                    directory for directory in ancestors if _should_extract(directory)
                ]
                if relative_path in declared and _should_extract(relative_path):
                    retained_entries.add(relative_path)
                retained_entries.update(retained_ancestors)
                should_extract = bool(retained_ancestors) or (
                    relative_path in declared and _should_extract(relative_path)
                )
                if should_extract and extracted_bytes + member.size > MAX_EXTRACTED_BYTES:
                    raise ValueError("archive exceeds the supported extraction limit")

                if should_extract:
                    destination_path = _destination_path(
                        temporary_workspace, relative_path
                    )
                elif ancestors:
                    if validation_bytes + member.size > MAX_VALIDATION_BYTES:
                        raise ValueError(
                            "archive exceeds the supported validation workspace limit"
                        )
                    destination_path = _destination_path(
                        validation_workspace, relative_path
                    )
                    validation_bytes += member.size
                else:
                    destination_path = None

                destination = None
                if destination_path is not None:
                    destination_path.parent.mkdir(parents=True, exist_ok=True)
                    destination = destination_path.open("wb")

                file_hasher = hashlib.sha256()
                bytes_read = 0
                try:
                    while True:
                        chunk = source.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        file_hasher.update(chunk)
                        if destination is not None:
                            destination.write(chunk)
                        bytes_read += len(chunk)
                finally:
                    if destination is not None:
                        destination.close()
                if bytes_read != member.size:
                    raise ValueError("archive member is truncated: %s" % relative_path)

                exact_hashes[relative_path] = file_hasher.hexdigest()
                exact_sizes[relative_path] = bytes_read
                if should_extract:
                    extracted_files += 1
                    extracted_bytes += bytes_read
                else:
                    skipped_files += 1
                    skipped_bytes += bytes_read

        if not manifest_seen:
            raise ValueError("manifest.json was not found during archive validation")

        failures = []
        validated_entries: Dict[str, Tuple[str, int, str]] = {}
        for relative_path, metadata in declared.items():
            if relative_path in observed_directories:
                extracted_directory = _destination_path(
                    temporary_workspace, relative_path
                )
                validation_directory = _destination_path(
                    validation_workspace, relative_path
                )
                directory_path = (
                    extracted_directory
                    if extracted_directory.is_dir()
                    else validation_directory
                )
                actual_hash, actual_size = _hash_directory(directory_path)
            else:
                actual_hash = exact_hashes.get(relative_path)
                actual_size = exact_sizes.get(relative_path)

            if actual_hash is None:
                failures.append("missing declared entry: %s" % relative_path)
                continue
            if actual_hash != metadata.get("sha256"):
                failures.append("hash mismatch: %s" % relative_path)
            expected_size = metadata.get("bytes")
            if expected_size is not None and actual_size != expected_size:
                failures.append("byte count mismatch: %s" % relative_path)
            if actual_hash is not None and actual_size is not None:
                validated_entries[relative_path] = (
                    actual_hash,
                    actual_size,
                    "directory"
                    if relative_path in observed_directories
                    else "file",
                )

        if "schema.json" not in exact_hashes or "schema.json" in observed_directories:
            failures.append("missing required entry: schema.json")
        for relative_path in sorted(RETAINED_FILES.intersection(observed_directories)):
            failures.append("expected a regular file: %s" % relative_path)
        if "variants.parquet" not in observed_directories or not any(
            path.startswith("variants.parquet/") for path in exact_hashes
        ):
            failures.append("missing required directory: variants.parquet")
        if failures:
            raise ValueError("bundle validation failed:\n  - " + "\n  - ".join(failures))

        if _archive_fingerprint(archive) != archive_fingerprint:
            raise ValueError("archive changed during validation")

        shutil.rmtree(validation_workspace)
        validated_at = datetime.now(timezone.utc).isoformat()
        stored_entries = {}
        for relative_path in sorted(retained_entries):
            actual_hash, actual_size, kind = validated_entries[relative_path]
            stored_entries[relative_path] = {
                "sha256": actual_hash,
                "bytes": actual_size,
                "kind": kind,
                "snapshot": _workspace_entry_snapshot(
                    temporary_workspace / relative_path,
                    kind,
                ),
            }
        receipt = {
            "version": RECEIPT_VERSION,
            "validated_at": validated_at,
            "archive": archive_fingerprint,
            "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "stored_entries": stored_entries,
            "report": {
                "schema_version": str(schema_version),
                "genome_build": str(manifest.get("genome_build")),
                "generated_at": str(manifest.get("generated_at")),
                "extracted_files": extracted_files,
                "extracted_bytes": extracted_bytes,
                "skipped_files": skipped_files,
                "skipped_bytes": skipped_bytes,
                "validated_entries": len(declared),
            },
        }
        receipt_path = temporary_workspace / RECEIPT_FILENAME
        receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")

        if final_workspace.is_symlink() or final_workspace.is_file():
            final_workspace.unlink()
        elif final_workspace.is_dir():
            shutil.rmtree(final_workspace)
        temporary_workspace.replace(final_workspace)

        return WorkspaceReport(
            archive=str(archive),
            workspace=str(final_workspace),
            schema_version=str(schema_version),
            genome_build=str(manifest.get("genome_build")),
            generated_at=str(manifest.get("generated_at")),
            extracted_files=extracted_files,
            extracted_bytes=extracted_bytes,
            skipped_files=skipped_files,
            skipped_bytes=skipped_bytes,
            validated_entries=len(declared),
            elapsed_seconds=round(time.monotonic() - started, 3),
            reused_workspace=False,
            validation_mode="full",
            validated_at=validated_at,
        )
    except Exception:
        shutil.rmtree(temporary_workspace, ignore_errors=True)
        shutil.rmtree(validation_workspace, ignore_errors=True)
        raise


def _sql_path(path: Path) -> str:
    return str(path).replace("'", "''")


def _rows(cursor: Any, section: str) -> List[Dict[str, Any]]:
    columns = [description[0] for description in cursor.description]
    return [
        {"section": section, **dict(zip(columns, row))}
        for row in cursor.fetchall()
    ]


def _view_columns(connection: Any, view_name: str) -> set[str]:
    return {
        str(row[1])
        for row in connection.execute("PRAGMA table_info('%s')" % view_name).fetchall()
    }


def _bundle_context(workspace: Path) -> Dict[str, Any]:
    manifest: Dict[str, Any] = {}
    manifest_path = workspace / "manifest.json"
    if manifest_path.is_file():
        try:
            candidate = json.loads(manifest_path.read_text())
            if isinstance(candidate, dict):
                manifest = candidate
        except (OSError, ValueError, json.JSONDecodeError):
            manifest = {}

    schema_version = manifest.get("schema_version")
    schema_match = (
        SCHEMA_VERSION_PATTERN.fullmatch(schema_version)
        if isinstance(schema_version, str)
        else None
    )
    schema_minor = (
        (int(schema_match.group(1)), int(schema_match.group(2)))
        if schema_match is not None
        else None
    )

    omissions_recorded = False
    omissions_path = workspace / "omissions.json"
    if omissions_path.is_file():
        try:
            payload = json.loads(omissions_path.read_text())
            omissions = payload.get("omissions") if isinstance(payload, dict) else None
            omissions_recorded = isinstance(omissions, list) and bool(omissions)
        except (OSError, ValueError, json.JSONDecodeError):
            omissions_recorded = False

    return {
        "schema_version": schema_version if isinstance(schema_version, str) else None,
        "schema_minor": schema_minor,
        "omissions_recorded": omissions_recorded,
    }


def _answerability(
    state: str,
    query_kind: str,
    basis: str,
    reason: str,
    **details: Any,
) -> Dict[str, Any]:
    return {
        "state": state,
        "scope": query_kind,
        "basis": basis,
        "reason": reason,
        **details,
    }


def _column_expression(columns: set[str], name: str, value_type: str) -> str:
    if name in columns:
        return name
    return "CAST(NULL AS %s)" % value_type


def _coordinate_callability(
    connection: Any,
    available: set[str],
    chrom: str,
    pos: int,
) -> Optional[Dict[str, Any]]:
    sources = (
        (
            "callability",
            "callability.parquet",
            "pos = ?",
        ),
        (
            "callable_regions",
            "callable_regions.parquet",
            "start_pos <= ? AND end_pos >= ?",
        ),
    )
    for view_name, source_name, position_predicate in sources:
        if view_name not in available:
            continue
        columns = _view_columns(connection, view_name)
        required = {"chrom", "callable"}
        if view_name == "callability":
            required.add("pos")
        else:
            required.update({"start_pos", "end_pos"})
        if not required.issubset(columns):
            continue

        parameters: List[Any] = [chrom]
        parameters.extend([pos, pos] if view_name == "callable_regions" else [pos])
        cursor = connection.execute(
            """
            SELECT callable,
                   %s AS reference_observed,
                   %s AS call_confidence,
                   %s AS evidence_scope,
                   %s AS assay_scope
            FROM %s
            WHERE lower(replace(chrom, 'chr', '')) = lower(replace(?, 'chr', ''))
              AND %s
            LIMIT 25
            """
            % (
                _column_expression(columns, "reference_observed", "BOOLEAN"),
                _column_expression(columns, "call_confidence", "VARCHAR"),
                _column_expression(columns, "evidence_scope", "VARCHAR"),
                _column_expression(columns, "assay_scope", "VARCHAR"),
                view_name,
                position_predicate,
            ),
            parameters,
        )
        rows = _rows(cursor, "callability")
        if not rows:
            continue

        callable_values = {
            row["callable"] for row in rows if row.get("callable") is not None
        }
        evidence = {
            "source": source_name,
            "callable": next(iter(callable_values)) if len(callable_values) == 1 else None,
            "reference_observed": any(
                row.get("reference_observed") is True for row in rows
            ),
            "call_confidence": next(
                (
                    row.get("call_confidence")
                    for row in rows
                    if row.get("call_confidence") is not None
                ),
                None,
            ),
            "evidence_scope": next(
                (
                    row.get("evidence_scope")
                    for row in rows
                    if row.get("evidence_scope") is not None
                ),
                None,
            ),
            "assay_scope": next(
                (
                    row.get("assay_scope")
                    for row in rows
                    if row.get("assay_scope") is not None
                ),
                None,
            ),
        }
        if callable_values == {True}:
            return _answerability(
                "callable_no_matching_alternate",
                "coordinate",
                source_name,
                "callable_position_without_matching_variant",
                callability=evidence,
            )
        if callable_values == {False}:
            return _answerability(
                "not_callable",
                "coordinate",
                source_name,
                "position_not_reliably_callable",
                callability=evidence,
            )
        return _answerability(
            "insufficient_bundle_data",
            "coordinate",
            source_name,
            "callability_is_unknown_or_conflicting",
            callability=evidence,
        )
    return None


def _answerability_for_search(
    connection: Any,
    workspace: Path,
    available: set[str],
    query: str,
    query_kind: str,
    hits: List[Dict[str, Any]],
    coordinate: Optional[re.Match[str]],
) -> Dict[str, Any]:
    if hits:
        return _answerability(
            "recorded",
            query_kind,
            "bundle_records",
            "matching_bundle_records_found",
            sections=sorted({str(hit["section"]) for hit in hits}),
        )

    if query_kind == "term":
        from .topics import topic_for_query

        topic = topic_for_query(str(workspace), query)
        if topic is not None and isinstance(topic.get("answerability"), dict):
            return topic["answerability"]

    context = _bundle_context(workspace)
    if query_kind == "coordinate" and coordinate is not None:
        chrom = "chr" + coordinate.group("chrom").upper()
        callability = _coordinate_callability(
            connection,
            available,
            chrom,
            int(coordinate.group("pos")),
        )
        if callability is not None:
            return callability

        has_callability_source = bool(
            {"callability", "callable_regions"}.intersection(available)
        )
        if has_callability_source:
            return _answerability(
                "insufficient_bundle_data",
                query_kind,
                "callability",
                "no_site_level_callability_record",
                omissions_recorded=context["omissions_recorded"],
            )

        schema_minor = context["schema_minor"]
        if schema_minor is not None and schema_minor < (1, 1):
            return _answerability(
                "unsupported_bundle_version",
                query_kind,
                "schema_version",
                "site_callability_not_available_in_bundle_version",
                schema_version=context["schema_version"],
            )
        return _answerability(
            "analysis_not_included",
            query_kind,
            "manifest",
            "site_callability_not_included",
            schema_version=context["schema_version"],
        )

    reason = (
        "rsid_has_no_offline_coordinate_mapping"
        if query_kind == "rsid"
        else "no_matching_record_without_complete_coverage_evidence"
    )
    return _answerability(
        "insufficient_bundle_data",
        query_kind,
        "bundle_records",
        reason,
        omissions_recorded=context["omissions_recorded"],
    )


def _gwas_column(
    columns: set[str], *candidates: str, fallback: str = "CAST(NULL AS VARCHAR)"
) -> str:
    for candidate in candidates:
        if candidate in columns:
            return "gwas.%s" % candidate
    return fallback


def _gwas_coalesce(
    columns: set[str], candidates: Tuple[str, ...], fallback: str
) -> str:
    expressions = [
        "gwas.%s" % candidate for candidate in candidates if candidate in columns
    ]
    if not expressions:
        return fallback
    return "COALESCE(%s)" % ", ".join(expressions + [fallback])


def _gwas_projection(columns: set[str]) -> str:
    if "study_pmids" in columns:
        study_pmids = "gwas.study_pmids"
    elif "pubmed_id" in columns:
        study_pmids = (
            "CASE WHEN gwas.pubmed_id IS NULL THEN []::VARCHAR[] "
            "ELSE [CAST(gwas.pubmed_id AS VARCHAR)] END"
        )
    else:
        study_pmids = "[]::VARCHAR[]"

    return """
        gwas.variant_id,
        %s AS rsid,
        %s AS gene,
        %s AS chrom,
        %s AS pos,
        %s AS ref,
        %s AS alt,
        gwas.trait,
        gwas.effect_allele,
        gwas.effect_size,
        gwas.effect_type,
        gwas.p_value,
        %s AS source,
        %s AS study_pmids,
        %s AS study_accession,
        %s AS source_version,
        %s AS effect_allele_in_call
    """ % (
        _gwas_coalesce(columns, ("rsid",), "person_linked.rsid"),
        _gwas_coalesce(
            columns,
            ("gene", "gene_symbol", "mapped_gene", "reported_gene"),
            "person_linked.gene",
        ),
        _gwas_coalesce(columns, ("chrom", "variant_chrom"), "person_linked.chrom"),
        _gwas_coalesce(columns, ("pos", "variant_pos"), "person_linked.pos"),
        _gwas_coalesce(columns, ("ref",), "person_linked.ref"),
        _gwas_coalesce(columns, ("alt",), "person_linked.alt"),
        _gwas_column(columns, "source"),
        study_pmids,
        _gwas_column(columns, "study_accession"),
        _gwas_column(columns, "source_version", "catalog_version"),
        _gwas_column(
            columns,
            "effect_allele_in_call",
            fallback="CAST(NULL AS BOOLEAN)",
        ),
    )


def _variant_projection() -> str:
    return """
        variant_id,
        rsid,
        chrom,
        pos,
        ref,
        alt,
        genotype.gt AS genotype,
        genotype.zygosity AS zygosity,
        quality.call_confidence AS call_confidence,
        gene.symbol AS gene,
        consequence.hgvsp AS hgvsp,
        pathogenicity.clinvar_significance AS clinvar_significance,
        pathogenicity.clinvar_has_conflicts AS clinvar_has_conflicts,
        pathogenicity.clinvar_conflict_summary AS clinvar_conflict_summary,
        pathogenicity.clinvar_review_stars AS clinvar_review_stars,
        pathogenicity.clinvar_submitters_count AS clinvar_submitters_count,
        pathogenicity.clinvar_id AS clinvar_id,
        clinical_grade
    """


def variants_for_region(
    workspace_path: str,
    chrom: str,
    start: int,
    end: int,
    page: int = 1,
    page_size: int = 25,
) -> Dict[str, Any]:
    """Return one stable, bounded page of person-specific variant rows."""
    if not chrom or start < 1 or end < start:
        raise ValueError("region browser locus is invalid")
    if page < 1 or page_size < 1 or page_size > 100:
        raise ValueError("region browser page is invalid")

    workspace = Path(workspace_path).resolve()
    variants = workspace / "variants.parquet"
    if not variants.is_dir():
        raise ValueError("workspace does not contain variants.parquet")

    connection = duckdb.connect()
    try:
        connection.execute("PRAGMA threads=2")
        variants_path = _sql_path(variants)
        connection.execute(
            "CREATE VIEW variants AS SELECT * FROM read_parquet("
            "'%s/**/*.parquet', hive_partitioning=true)" % variants_path
        )
        predicate = (
            "lower(replace(chrom, 'chr', '')) = "
            "lower(replace(?, 'chr', '')) AND pos BETWEEN ? AND ?"
        )
        parameters: List[Any] = [chrom, start, end]
        total = int(
            connection.execute(
                "SELECT count(*)::BIGINT FROM variants WHERE " + predicate,
                parameters,
            ).fetchone()[0]
        )
        page_count = max(1, math.ceil(total / page_size))
        if total and page > page_count:
            raise ValueError("region browser page is outside the selected locus")
        offset = (page - 1) * page_size
        cursor = connection.execute(
            "SELECT %s FROM variants WHERE %s "
            "ORDER BY pos, variant_id LIMIT ? OFFSET ?"
            % (_variant_projection(), predicate),
            [*parameters, page_size, offset],
        )
        return {
            "chrom": chrom,
            "start": start,
            "end": end,
            "page": page,
            "page_size": page_size,
            "page_count": page_count,
            "total": total,
            "hits": _rows(cursor, "variants"),
        }
    finally:
        connection.close()


def _trait_variant_projection() -> str:
    return """
        variant_id,
        rsid,
        chrom,
        pos,
        ref,
        alt,
        list_transform(
            genotype.gt,
            allele_index -> CASE
                WHEN allele_index = 0 THEN ref
                WHEN allele_index = 1 THEN alt
                ELSE '?'
            END
        ) AS called_alleles,
        genotype.zygosity AS zygosity,
        quality.call_confidence AS call_confidence,
        gene.symbol AS gene,
        trait_associations.traits AS recorded_traits,
        trait_associations.study_pmids AS study_pmids
    """


def search_workspace(workspace_path: str, query: str) -> SearchResult:
    started = time.monotonic()
    workspace = Path(workspace_path).resolve()
    variants = workspace / "variants.parquet"
    if not variants.is_dir():
        raise ValueError("workspace does not contain variants.parquet")

    connection = duckdb.connect()
    connection.execute(
        "CREATE VIEW variants AS SELECT * FROM read_parquet("
        "'%s/**/*.parquet', hive_partitioning=true)" % _sql_path(variants)
    )
    has_trait_associations = True
    try:
        connection.execute(
            "SELECT trait_associations.is_gwas_hit, "
            "trait_associations.traits FROM variants LIMIT 0"
        )
    except duckdb.Error:
        has_trait_associations = False

    table_files = {
        "clinical_findings": workspace / "clinical_findings.parquet",
        "clinical_evidence": workspace / "clinical_evidence.parquet",
        "pharmacogenomics": workspace / "pharmacogenomics.parquet",
        "prs": workspace / "prs.parquet",
        "gwas_associations": workspace / "gwas_associations.parquet",
        "gene_index": workspace / "gene_index.parquet",
        "callability": workspace / "callability.parquet",
        "callable_regions": workspace / "callable_regions.parquet",
    }
    available = set()
    for table, path in table_files.items():
        if path.is_file():
            connection.execute(
                "CREATE VIEW %s AS SELECT * FROM read_parquet('%s')"
                % (table, _sql_path(path))
            )
            available.add(table)

    has_clinical_findings = False
    has_clinical_evidence = False
    if "clinical_findings" in available:
        findings_projection = clinical_findings_projection(
            _view_columns(connection, "clinical_findings")
        )
        if findings_projection is not None:
            connection.execute(
                "CREATE VIEW searchable_clinical_findings AS "
                "SELECT %s FROM clinical_findings AS source" % findings_projection
            )
            has_clinical_findings = True
    if has_clinical_findings and "clinical_evidence" in available:
        evidence_projection = clinical_evidence_projection(
            _view_columns(connection, "clinical_evidence")
        )
        if evidence_projection is not None:
            connection.execute(
                "CREATE VIEW searchable_clinical_evidence AS "
                "SELECT %s FROM clinical_evidence AS source" % evidence_projection
            )
            has_clinical_evidence = True

    normalized_query = query.strip()
    if not normalized_query:
        raise ValueError("search query cannot be empty")

    hits: List[Dict[str, Any]] = []
    coordinate = COORDINATE_PATTERN.fullmatch(normalized_query)
    if RSID_PATTERN.fullmatch(normalized_query):
        query_kind = "rsid"
        cursor = connection.execute(
            "SELECT %s FROM variants WHERE lower(rsid) = lower(?) LIMIT 25"
            % _variant_projection(),
            [normalized_query],
        )
        hits.extend(_rows(cursor, "variants"))
    elif coordinate:
        query_kind = "coordinate"
        chrom = "chr" + coordinate.group("chrom").upper()
        parameters: List[Any] = [chrom, int(coordinate.group("pos"))]
        predicate = "chrom = ? AND pos = ?"
        if coordinate.group("ref") and coordinate.group("alt"):
            predicate += " AND ref = ? AND alt = ?"
            parameters.extend(
                [coordinate.group("ref").upper(), coordinate.group("alt").upper()]
            )
        cursor = connection.execute(
            "SELECT %s FROM variants WHERE %s LIMIT 25"
            % (_variant_projection(), predicate),
            parameters,
        )
        hits.extend(_rows(cursor, "variants"))
    else:
        query_kind = "term"
        cursor = connection.execute(
            "SELECT %s FROM variants WHERE upper(gene.symbol) = upper(?) LIMIT 25"
            % _variant_projection(),
            [normalized_query],
        )
        hits.extend(_rows(cursor, "variants"))

        if "gene_index" in available:
            cursor = connection.execute(
                """
                SELECT gene_symbol, chrom, start_pos, end_pos,
                       variant_count, actionable_count
                FROM gene_index
                WHERE upper(gene_symbol) = upper(?)
                LIMIT 25
                """,
                [normalized_query],
            )
            hits.extend(_rows(cursor, "genes"))

        if "pharmacogenomics" in available:
            cursor = connection.execute(
                """
                SELECT gene_symbol, diplotype, phenotype, activity_score,
                       copy_number, cpic_level, affected_drugs, guideline_url
                FROM pharmacogenomics
                WHERE upper(gene_symbol) = upper(?)
                   OR EXISTS (
                       SELECT 1
                       FROM UNNEST(affected_drugs) AS drug(value)
                       WHERE lower(value) LIKE '%' || lower(?) || '%'
                   )
                LIMIT 25
                """,
                [normalized_query, normalized_query],
            )
            hits.extend(_rows(cursor, "pharmacogenomics"))

        if "prs" in available:
            cursor = connection.execute(
                """
                SELECT trait, score_value, percentile, reference_population,
                       training_source, training_date
                FROM prs
                WHERE lower(trait) LIKE '%' || lower(?) || '%'
                LIMIT 25
                """,
                [normalized_query],
            )
            hits.extend(_rows(cursor, "polygenic_scores"))

        if has_clinical_findings:
            evidence_projection = ", NULL AS evidence"
            source_predicate = ""
            source_parameters: List[Any] = []
            if has_clinical_evidence:
                evidence_projection = """,
                    (
                        SELECT list(
                            struct_pack(
                                evidence_id := evidence.evidence_id,
                                source := evidence.source,
                                source_record_id := evidence.source_record_id,
                                source_version := evidence.source_version,
                                assertion := evidence.assertion,
                                review_status := evidence.review_status,
                                retrieved_at := CAST(evidence.retrieved_at AS VARCHAR)
                            )
                            ORDER BY evidence.evidence_id
                        )
                        FROM searchable_clinical_evidence AS evidence
                        WHERE list_contains(findings.evidence_ids, evidence.evidence_id)
                    ) AS evidence
                """
                source_predicate = """
                    OR EXISTS (
                        SELECT 1
                        FROM searchable_clinical_evidence AS evidence
                        WHERE list_contains(findings.evidence_ids, evidence.evidence_id)
                          AND lower(evidence.source) LIKE '%' || lower(?) || '%'
                    )
                """
                source_parameters.append(normalized_query)

            list_all = normalized_query.lower() in {
                "clinical",
                "clinical finding",
                "clinical findings",
            }
            term_predicate = ""
            parameters: List[Any] = []
            if not list_all:
                term_predicate = f"""
                    AND (
                        lower(findings.condition) LIKE '%' || lower(?) || '%'
                        OR upper(COALESCE(findings.gene_symbol, '')) = upper(?)
                        OR lower(COALESCE(findings.classification, '')) LIKE '%' || lower(?) || '%'
                        OR lower(findings.claim_type) LIKE '%' || lower(?) || '%'
                        OR lower(COALESCE(findings.variant_id, '')) = lower(?)
                        {source_predicate}
                    )
                """
                parameters = [normalized_query] * 5 + source_parameters

            cursor = connection.execute(
                """
                SELECT findings.finding_id,
                       findings.condition,
                       findings.claim_type,
                       findings.classification,
                       findings.clinical_grade,
                       findings.variant_id,
                       COALESCE(findings.gene_symbol, variants.gene.symbol) AS gene_symbol,
                       variants.rsid,
                       CASE
                           WHEN variants.variant_id IS NULL THEN NULL
                           ELSE list_transform(
                               variants.genotype.gt,
                               allele_index -> CASE
                                   WHEN allele_index = 0 THEN variants.ref
                                   WHEN allele_index = 1 THEN variants.alt
                                   ELSE '?'
                               END
                           )
                       END AS called_alleles,
                       COALESCE(
                           variants.quality.call_confidence,
                           findings.call_confidence
                       ) AS call_confidence,
                       COALESCE(
                           variants.pathogenicity.clinvar_significance,
                           findings.clinvar_significance
                       ) AS clinvar_significance,
                       COALESCE(
                           variants.pathogenicity.clinvar_has_conflicts,
                           findings.clinvar_has_conflicts
                       ) AS clinvar_has_conflicts,
                       COALESCE(
                           variants.pathogenicity.clinvar_conflict_summary,
                           findings.clinvar_conflict_summary
                       ) AS clinvar_conflict_summary,
                       COALESCE(
                           variants.pathogenicity.clinvar_review_stars,
                           findings.clinvar_review_stars
                       ) AS clinvar_review_stars,
                       COALESCE(
                           variants.pathogenicity.clinvar_submitters_count,
                           findings.clinvar_submitters_count
                       ) AS clinvar_submitters_count,
                       COALESCE(
                           variants.pathogenicity.clinvar_id,
                           findings.clinvar_id
                       ) AS clinvar_id,
                       findings.evidence_ids
                       %s
                FROM searchable_clinical_findings AS findings
                LEFT JOIN variants
                  ON variants.variant_id = findings.variant_id
                WHERE findings.clinical_grade = true
                %s
                ORDER BY findings.condition, findings.finding_id
                LIMIT 25
                """ % (evidence_projection, term_predicate),
                parameters,
            )
            hits.extend(_rows(cursor, "clinical_findings"))

        if has_trait_associations:
            try:
                cursor = connection.execute(
                    """
                    SELECT %s,
                           list_slice(
                               list_filter(
                                   trait_associations.traits,
                                   trait -> lower(trait) LIKE '%%' || lower(?) || '%%'
                               ),
                               1,
                               3
                           ) AS matched_traits
                    FROM variants
                    WHERE trait_associations.is_gwas_hit
                      AND EXISTS (
                          SELECT 1
                          FROM UNNEST(trait_associations.traits) AS annotation(value)
                          WHERE lower(value) LIKE '%%' || lower(?) || '%%'
                      )
                    ORDER BY chrom, pos
                    LIMIT 25
                    """ % _trait_variant_projection(),
                    [normalized_query, normalized_query],
                )
            except duckdb.Error:
                has_trait_associations = False
            else:
                hits.extend(_rows(cursor, "trait_variants"))

        if "gwas_associations" in available and has_trait_associations:
            gwas_columns = _view_columns(connection, "gwas_associations")
            join_predicate = "gwas.variant_id = person_linked.variant_id"
            if "rsid" in gwas_columns:
                join_predicate += """
                    OR (
                        gwas.rsid IS NOT NULL
                        AND gwas.rsid = person_linked.rsid
                    )
                """
            term_columns = ["trait"] + [
                column
                for column in ("mapped_trait", "reported_trait")
                if column in gwas_columns
            ]
            term_predicate = " OR ".join(
                "lower(COALESCE(CAST(gwas.%s AS VARCHAR), '')) "
                "LIKE '%%' || lower(?) || '%%'" % column
                for column in term_columns
            )
            cursor = connection.execute(
                """
                WITH person_linked AS (
                    SELECT DISTINCT variant_id, rsid, chrom, pos, ref, alt,
                                    gene.symbol AS gene
                    FROM variants
                    WHERE trait_associations.is_gwas_hit
                      AND EXISTS (
                          SELECT 1
                          FROM UNNEST(trait_associations.traits) AS annotation(value)
                          WHERE lower(value) LIKE '%%' || lower(?) || '%%'
                      )
                )
                SELECT DISTINCT %s
                FROM gwas_associations AS gwas
                JOIN person_linked
                  ON (%s)
                WHERE %s
                ORDER BY rsid, trait
                LIMIT 25
                """ % (
                    _gwas_projection(gwas_columns),
                    join_predicate,
                    term_predicate,
                ),
                [normalized_query] * (1 + len(term_columns)),
            )
            hits.extend(_rows(cursor, "gwas"))

    answerability = _answerability_for_search(
        connection,
        workspace,
        available,
        normalized_query,
        query_kind,
        hits,
        coordinate,
    )
    from .saved_results import saved_result_id

    for hit in hits:
        hit["_record_key"] = saved_result_id(hit)
    connection.close()
    return SearchResult(
        query=normalized_query,
        query_kind=query_kind,
        answerability=answerability,
        hits=hits,
        elapsed_seconds=round(time.monotonic() - started, 3),
    )


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value
