from __future__ import annotations

import json
import os
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlsplit

from .bundle_library import BundleLibrary
from .core import (
    WorkspaceReport,
    json_ready,
    open_bundle,
    search_workspace,
)
from .genome_map import genome_map_for_workspace
from .region_browser import region_browser_for_workspace
from .saved_results import SavedResultsStore
from .topics import topics_for_workspace
from .web import PAGE


MAX_REQUEST_BYTES = 256 * 1024
MAX_QUERY_CHARACTERS = 200
ArchiveChooser = Callable[[], Optional[str]]


class LocalExplorerServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        report: Optional[WorkspaceReport],
        port: int,
        chooser: Optional[ArchiveChooser] = None,
        workspace_root: Optional[Path] = None,
        force_validate: bool = False,
    ):
        super().__init__(("127.0.0.1", port), LocalExplorerHandler)
        self.report = report
        self.chooser = chooser
        self.workspace_root = workspace_root
        self.force_validate = force_validate
        self.library = (
            BundleLibrary(workspace_root.parent / "bundle-library.json")
            if workspace_root is not None
            else None
        )
        self.saved_results = (
            SavedResultsStore(workspace_root.parent / "saved-results.json")
            if workspace_root is not None
            else None
        )
        self.state_lock = threading.Lock()
        self.map_lock = threading.Lock()
        self.genome_map_cache: Dict[str, Dict[str, Any]] = {}
        self.state_status = "ready" if report is not None else "waiting"
        self.state_error = ""
        self.archive_name = Path(report.archive).name if report is not None else ""
        self.active_bundle_id = ""
        self.active_nickname = ""
        self.topics = []
        if report is not None and self.library is not None:
            entry = self.library.register(report)
            self.active_bundle_id = entry.bundle_id
            self.active_nickname = entry.nickname
            self.topics = topics_for_workspace(report.workspace)
        self.token = secrets.token_urlsafe(24)
        self.desktop_token = secrets.token_urlsafe(32)
        self.nonce = secrets.token_urlsafe(18)
        self.expected_host = "127.0.0.1:%d" % self.server_port
        self.origin = "http://%s" % self.expected_host
        self.base_path = "/%s" % self.token

    @property
    def url(self) -> str:
        return self.origin + self.base_path + "/"

    def status_payload(self) -> Dict[str, Any]:
        with self.state_lock:
            status = self.state_status
            error = self.state_error
            archive_name = self.archive_name
            report = self.report
            active_bundle_id = self.active_bundle_id
            active_nickname = self.active_nickname
            topics = self.topics

        payload: Dict[str, Any] = {
            "status": status,
            "archive_name": archive_name,
            "bundles": self.library.public_entries() if self.library else [],
            "topics": topics,
        }
        if error:
            payload["error"] = error
        if status == "ready" and report is not None:
            saved_count = (
                len(self.saved_results.entries(active_bundle_id))
                if self.saved_results is not None and active_bundle_id
                else 0
            )
            payload.update(
                {
                    "schema_version": report.schema_version,
                    "genome_build": report.genome_build,
                    "generated_at": report.generated_at,
                    "validated_entries": report.validated_entries,
                    "stored_files": report.extracted_files,
                    "stored_bytes": report.extracted_bytes,
                    "validation_seconds": report.elapsed_seconds,
                    "validation_mode": report.validation_mode,
                    "validated_at": report.validated_at,
                    "active_bundle_id": active_bundle_id,
                    "active_nickname": active_nickname,
                    "saved_count": saved_count,
                }
            )
        return payload

    def ready_report(self) -> Optional[WorkspaceReport]:
        with self.state_lock:
            if self.state_status != "ready":
                return None
            return self.report

    def genome_map_payload(self) -> Dict[str, Any]:
        report = self.ready_report()
        if report is None:
            raise ValueError("choose and verify a bundle first")
        with self.map_lock:
            cached = self.genome_map_cache.get(report.workspace)
            if cached is None:
                cached = genome_map_for_workspace(
                    report.workspace,
                    report.genome_build,
                )
                self.genome_map_cache[report.workspace] = cached
            return cached

    def region_browser_payload(
        self,
        *,
        query: Optional[str] = None,
        chrom: Optional[str] = None,
        start: Optional[int] = None,
        end: Optional[int] = None,
        page: int = 1,
    ) -> Dict[str, Any]:
        report = self.ready_report()
        if report is None:
            raise ValueError("choose and verify a bundle first")
        return region_browser_for_workspace(
            report.workspace,
            report.genome_build,
            query=query,
            chrom=chrom,
            start=start,
            end=end,
            page=page,
        )

    def begin_selection(self) -> bool:
        with self.state_lock:
            if self.chooser is None or self.state_status in {"choosing", "validating"}:
                return False
            self.state_status = "choosing"
            self.state_error = ""
            self.archive_name = ""
            self.report = None
            self.active_bundle_id = ""
            self.active_nickname = ""
            self.topics = []
        threading.Thread(target=self._select_and_open, daemon=True).start()
        return True

    def begin_open_path(self, archive: str) -> bool:
        path = Path(archive).expanduser()
        if not archive.lower().endswith(".genome.tar.gz") or not path.is_file():
            raise ValueError("choose a file ending in .genome.tar.gz")
        with self.state_lock:
            if self.state_status in {"choosing", "validating"}:
                return False
            self.state_status = "validating"
            self.state_error = ""
            self.archive_name = path.name
            self.report = None
            self.active_bundle_id = ""
            self.active_nickname = ""
            self.topics = []
        threading.Thread(
            target=self._open_path,
            args=(str(path),),
            daemon=True,
        ).start()
        return True

    def show_library(self) -> bool:
        with self.state_lock:
            if self.state_status in {"choosing", "validating"}:
                return False
            self.report = None
            self.state_status = "waiting"
            self.state_error = ""
            self.archive_name = ""
            self.active_bundle_id = ""
            self.active_nickname = ""
            self.topics = []
        return True

    def begin_open(self, bundle_id: str) -> bool:
        if self.library is None:
            return False
        entry = self.library.find(bundle_id)
        if entry is None:
            return False
        with self.state_lock:
            if self.state_status in {"choosing", "validating"}:
                return False
            self.report = None
            self.state_status = "validating"
            self.state_error = ""
            self.archive_name = entry.file_name
            self.active_bundle_id = ""
            self.active_nickname = ""
            self.topics = []
        threading.Thread(
            target=self._open_saved_bundle,
            args=(bundle_id,),
            daemon=True,
        ).start()
        return True

    def rename_bundle(self, bundle_id: str, nickname: str) -> None:
        if self.library is None:
            raise ValueError("local bundle library is unavailable")
        entry = self.library.rename(bundle_id, nickname)
        with self.state_lock:
            if self.active_bundle_id == bundle_id:
                self.active_nickname = entry.nickname

    def _selected_bundle_id(self) -> str:
        with self.state_lock:
            if self.state_status != "ready" or not self.active_bundle_id:
                raise ValueError("choose and verify a bundle first")
            return self.active_bundle_id

    def saved_payload(self) -> Dict[str, Any]:
        if self.saved_results is None:
            raise ValueError("saved results are unavailable")
        bundle_id = self._selected_bundle_id()
        return {
            "bundle_id": bundle_id,
            "records": self.saved_results.entries(bundle_id),
        }

    def save_record(self, query: str, record: Dict[str, Any]) -> Dict[str, Any]:
        if self.saved_results is None:
            raise ValueError("saved results are unavailable")
        bundle_id = self._selected_bundle_id()
        self.saved_results.add(bundle_id, query, record)
        return self.saved_payload()

    def remove_saved_record(self, saved_id: str) -> Dict[str, Any]:
        if self.saved_results is None:
            raise ValueError("saved results are unavailable")
        bundle_id = self._selected_bundle_id()
        self.saved_results.remove(bundle_id, saved_id)
        return self.saved_payload()

    def export_saved_records(self, format_name: str) -> Dict[str, str]:
        if self.saved_results is None or self.library is None:
            raise ValueError("saved results are unavailable")
        bundle_id = self._selected_bundle_id()
        entry = self.library.find(bundle_id)
        if entry is None:
            raise ValueError("bundle was not found")
        return self.saved_results.export(
            bundle_id,
            {
                "bundle_id": entry.bundle_id,
                "nickname": entry.nickname,
                "schema_version": entry.schema_version,
                "genome_build": entry.genome_build,
                "generated_at": entry.generated_at,
            },
            format_name,
        )

    def _accept_report(self, report: WorkspaceReport) -> None:
        bundle_id = ""
        nickname = ""
        topics = topics_for_workspace(report.workspace)
        if self.library is not None:
            entry = self.library.register(report)
            bundle_id = entry.bundle_id
            nickname = entry.nickname
        with self.state_lock:
            self.report = report
            self.state_status = "ready"
            self.state_error = ""
            self.active_bundle_id = bundle_id
            self.active_nickname = nickname
            self.topics = topics

    def _select_and_open(self) -> None:
        try:
            archive = self.chooser() if self.chooser is not None else None
            if archive is None:
                with self.state_lock:
                    self.state_status = "waiting"
                return
            with self.state_lock:
                self.state_status = "validating"
                self.archive_name = Path(archive).name
            if self.workspace_root is None:
                raise RuntimeError("local workspace is unavailable")
            report = open_bundle(
                archive,
                self.workspace_root,
                force_validate=self.force_validate,
            )
            self._accept_report(report)
        except Exception as error:
            with self.state_lock:
                self.report = None
                self.state_status = "failed"
                self.state_error = str(error)
                self.active_bundle_id = ""
                self.active_nickname = ""
                self.topics = []

    def _open_path(self, archive: str) -> None:
        try:
            if self.workspace_root is None:
                raise RuntimeError("local workspace is unavailable")
            report = open_bundle(
                archive,
                self.workspace_root,
                force_validate=self.force_validate,
            )
            self._accept_report(report)
        except Exception as error:
            with self.state_lock:
                self.report = None
                self.state_status = "failed"
                self.state_error = str(error)
                self.active_bundle_id = ""
                self.active_nickname = ""
                self.topics = []

    def _open_saved_bundle(self, bundle_id: str) -> None:
        try:
            if self.library is None or self.workspace_root is None:
                raise RuntimeError("local bundle library is unavailable")
            entry = self.library.find(bundle_id)
            if entry is None:
                raise ValueError("bundle was not found")
            if not Path(entry.archive).is_file():
                raise ValueError("the source bundle is no longer available at its saved location")
            report = open_bundle(
                entry.archive,
                self.workspace_root,
                force_validate=self.force_validate,
            )
            self._accept_report(report)
        except Exception as error:
            with self.state_lock:
                self.report = None
                self.state_status = "failed"
                self.state_error = str(error)
                self.active_bundle_id = ""
                self.active_nickname = ""
                self.topics = []


class LocalExplorerHandler(BaseHTTPRequestHandler):
    server: LocalExplorerServer

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _request_is_local(self) -> bool:
        return self.headers.get("Host") == self.server.expected_host

    def _send_headers(self, status: int, content_type: str, length: int) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; "
            "script-src 'nonce-%s'; style-src 'nonce-%s'; "
            "connect-src 'self'; img-src data:; "
            "base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
            % (self.server.nonce, self.server.nonce),
        )
        self.end_headers()

    def _send_bytes(self, status: int, content_type: str, body: bytes) -> None:
        self._send_headers(status, content_type, len(body))
        self.wfile.write(body)

    def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(json_ready(payload), separators=(",", ":")).encode("utf-8")
        self._send_bytes(status, "application/json; charset=utf-8", body)

    def _reject(self, status: int = 404) -> None:
        self._send_json(status, {"error": "not found"})

    def _read_json_body(self) -> Dict[str, Any]:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ValueError("invalid request length")
        if content_length < 1 or content_length > MAX_REQUEST_BYTES:
            raise ValueError("invalid request length")
        payload = json.loads(self.rfile.read(content_length))
        if not isinstance(payload, dict):
            raise ValueError("request body must be an object")
        return payload

    def do_GET(self) -> None:
        if not self._request_is_local():
            self._reject(403)
            return
        path = urlsplit(self.path).path.rstrip("/")
        if path == self.server.base_path:
            page = (
                PAGE.replace("__BASE_PATH__", self.server.base_path)
                .replace("__NONCE__", self.server.nonce)
                .encode("utf-8")
            )
            self._send_bytes(200, "text/html; charset=utf-8", page)
            return
        if path == self.server.base_path + "/api/status":
            self._send_json(200, self.server.status_payload())
            return
        if path == self.server.base_path + "/api/saved":
            try:
                self._send_json(200, self.server.saved_payload())
            except ValueError as error:
                self._send_json(409, {"error": str(error)})
            return
        if path == self.server.base_path + "/api/genome-map":
            try:
                self._send_json(200, self.server.genome_map_payload())
            except ValueError as error:
                self._send_json(409, {"error": str(error)})
            except Exception:
                self._send_json(500, {"error": "coverage summary could not be prepared"})
            return
        self._reject()

    def do_POST(self) -> None:
        if not self._request_is_local():
            self._reject(403)
            return
        if self.headers.get("Origin") != self.server.origin:
            self._reject(403)
            return
        path = urlsplit(self.path).path.rstrip("/")
        if path == self.server.base_path + "/api/desktop/open":
            supplied_token = self.headers.get("X-Offline-Explorer-Desktop", "")
            if not secrets.compare_digest(supplied_token, self.server.desktop_token):
                self._reject(403)
                return
            try:
                payload = self._read_json_body()
                archive = payload.get("archive")
                if not isinstance(archive, str):
                    raise ValueError("bundle selection is invalid")
                started = self.server.begin_open_path(archive)
                if not started:
                    raise ValueError("another bundle is already opening")
                self._send_json(202, self.server.status_payload())
            except (ValueError, json.JSONDecodeError) as error:
                self._send_json(400, {"error": str(error)})
            return
        if path == self.server.base_path + "/api/shutdown":
            self._send_json(200, {"status": "stopped"})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        if path == self.server.base_path + "/api/select":
            started = self.server.begin_selection()
            self._send_json(
                202 if started else 409,
                self.server.status_payload(),
            )
            return
        if path == self.server.base_path + "/api/library/show":
            shown = self.server.show_library()
            self._send_json(
                200 if shown else 409,
                self.server.status_payload(),
            )
            return
        if path == self.server.base_path + "/api/library/open":
            try:
                payload = self._read_json_body()
                bundle_id = payload.get("bundle_id")
                if not isinstance(bundle_id, str) or not bundle_id:
                    raise ValueError("bundle selection is invalid")
                started = self.server.begin_open(bundle_id)
                if not started:
                    raise ValueError("bundle could not be opened")
                self._send_json(202, self.server.status_payload())
            except (ValueError, json.JSONDecodeError) as error:
                self._send_json(400, {"error": str(error)})
            return
        if path == self.server.base_path + "/api/library/rename":
            try:
                payload = self._read_json_body()
                bundle_id = payload.get("bundle_id")
                nickname = payload.get("nickname")
                if not isinstance(bundle_id, str) or not isinstance(nickname, str):
                    raise ValueError("nickname request is invalid")
                self.server.rename_bundle(bundle_id, nickname)
                self._send_json(200, self.server.status_payload())
            except (ValueError, json.JSONDecodeError) as error:
                self._send_json(400, {"error": str(error)})
            return
        if path == self.server.base_path + "/api/saved/add":
            try:
                payload = self._read_json_body()
                query = payload.get("query")
                record = payload.get("record")
                if not isinstance(query, str) or not isinstance(record, dict):
                    raise ValueError("saved result request is invalid")
                self._send_json(200, self.server.save_record(query, record))
            except (ValueError, json.JSONDecodeError) as error:
                self._send_json(400, {"error": str(error)})
            return
        if path == self.server.base_path + "/api/saved/remove":
            try:
                payload = self._read_json_body()
                saved_id = payload.get("saved_id")
                if not isinstance(saved_id, str) or not saved_id:
                    raise ValueError("saved result request is invalid")
                self._send_json(200, self.server.remove_saved_record(saved_id))
            except (ValueError, json.JSONDecodeError) as error:
                self._send_json(400, {"error": str(error)})
            return
        if path == self.server.base_path + "/api/saved/export":
            supplied_token = self.headers.get("X-Offline-Explorer-Desktop", "")
            if not secrets.compare_digest(supplied_token, self.server.desktop_token):
                self._reject(403)
                return
            try:
                payload = self._read_json_body()
                format_name = payload.get("format")
                if not isinstance(format_name, str):
                    raise ValueError("export format is invalid")
                self._send_json(
                    200,
                    self.server.export_saved_records(format_name),
                )
            except (ValueError, json.JSONDecodeError) as error:
                self._send_json(400, {"error": str(error)})
            return
        if path == self.server.base_path + "/api/region-browser":
            try:
                payload = self._read_json_body()
                query = payload.get("query")
                chrom = payload.get("chrom")
                start = payload.get("start")
                end = payload.get("end")
                page = payload.get("page", 1)
                if not isinstance(page, int) or isinstance(page, bool) or page < 1:
                    raise ValueError("region browser page is invalid")
                if query is not None:
                    if (
                        not isinstance(query, str)
                        or len(query) > MAX_QUERY_CHARACTERS
                        or any(value is not None for value in (chrom, start, end))
                    ):
                        raise ValueError("region browser query is invalid")
                    result = self.server.region_browser_payload(
                        query=query,
                        page=page,
                    )
                else:
                    integers = (start, end)
                    if (
                        not isinstance(chrom, str)
                        or not all(
                            isinstance(value, int) and not isinstance(value, bool)
                            for value in integers
                        )
                    ):
                        raise ValueError("region browser request is invalid")
                    result = self.server.region_browser_payload(
                        chrom=chrom,
                        start=start,
                        end=end,
                        page=page,
                    )
                self._send_json(200, result)
            except (ValueError, json.JSONDecodeError) as error:
                self._send_json(400, {"error": str(error)})
            except Exception:
                self._send_json(500, {"error": "region browser could not be loaded"})
            return
        if path != self.server.base_path + "/api/search":
            self._reject()
            return

        report = self.server.ready_report()
        if report is None:
            self._send_json(409, {"error": "choose and verify a bundle first"})
            return
        try:
            payload = self._read_json_body()
            query = payload.get("query", "")
            if not isinstance(query, str) or len(query) > MAX_QUERY_CHARACTERS:
                raise ValueError("search query is invalid")
            result = search_workspace(report.workspace, query)
            self._send_json(200, result.to_dict())
        except ValueError as error:
            self._send_json(400, {"error": str(error)})
        except Exception:
            self._send_json(500, {"error": "search could not be completed"})


def _run_server(
    server: LocalExplorerServer,
    open_browser: bool,
    desktop_backend: bool = False,
) -> None:
    if desktop_backend:
        print(
            "OFFLINE_EXPLORER_READY "
            + json.dumps(
                {
                    "url": server.url,
                    "desktop_token": server.desktop_token,
                },
                separators=(",", ":"),
            ),
            flush=True,
        )
    else:
        print("Offline Explorer ready: %s" % server.url, flush=True)
        print("Press Ctrl-C to stop.", flush=True)
    if open_browser:
        threading.Timer(0.2, webbrowser.open, args=(server.url,)).start()
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            server.server_close()
        except KeyboardInterrupt:
            pass


def _shutdown_when_parent_pipe_closes(
    server: LocalExplorerServer,
    parent_liveness_fd: int,
) -> None:
    try:
        while os.read(parent_liveness_fd, 1):
            pass
    except OSError:
        pass
    finally:
        try:
            os.close(parent_liveness_fd)
        except OSError:
            pass
        server.shutdown()


def serve(
    report: WorkspaceReport,
    workspace_root: Path,
    port: int,
    open_browser: bool,
) -> None:
    _run_server(
        LocalExplorerServer(report, port, workspace_root=workspace_root),
        open_browser,
    )


def serve_launcher(
    chooser: ArchiveChooser,
    workspace_root: Path,
    force_validate: bool,
    port: int,
    open_browser: bool,
) -> None:
    server = LocalExplorerServer(
        None,
        port,
        chooser=chooser,
        workspace_root=workspace_root,
        force_validate=force_validate,
    )
    _run_server(server, open_browser)


def serve_desktop(
    workspace_root: Path,
    force_validate: bool,
    port: int,
    parent_liveness_fd: int,
) -> None:
    os.fstat(parent_liveness_fd)
    server = LocalExplorerServer(
        None,
        port,
        workspace_root=workspace_root,
        force_validate=force_validate,
    )
    threading.Thread(
        target=_shutdown_when_parent_pipe_closes,
        args=(server, parent_liveness_fd),
        daemon=True,
    ).start()
    _run_server(server, open_browser=False, desktop_backend=True)
