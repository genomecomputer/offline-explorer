from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .core import WorkspaceReport, json_ready, open_bundle, search_workspace
from .server import serve, serve_desktop, serve_launcher


BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"
CLEAR = "\033[2J\033[H"


@dataclass
class PrototypeState:
    archive: str
    status: str = "not opened"
    report: Optional[WorkspaceReport] = None
    last_query: str = ""
    last_kind: str = ""
    last_elapsed: float = 0.0
    hits: Optional[List[dict]] = None
    answerability: Optional[dict] = None
    error: str = ""


def _format_bytes(value: int) -> str:
    units = ["B", "KiB", "MiB", "GiB"]
    amount = float(value)
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            return "%.1f %s" % (amount, unit)
        amount /= 1024
    return "%d B" % value


def _render(state: PrototypeState) -> None:
    print(CLEAR, end="")
    print(BOLD + "Selective reader prototype" + RESET)
    print(DIM + "Fully validates the archive, but stores only JSON and Parquet." + RESET)
    print()
    print(BOLD + "archive: " + RESET + state.archive)
    print(BOLD + "status: " + RESET + state.status)
    if state.report:
        report = state.report
        print(BOLD + "workspace: " + RESET + report.workspace)
        print(BOLD + "schema: " + RESET + report.schema_version)
        print(BOLD + "genome build: " + RESET + report.genome_build)
        print(BOLD + "validation mode: " + RESET + report.validation_mode)
        print(BOLD + "validated: " + RESET + "%d manifest entries" % report.validated_entries)
        print(BOLD + "stored: " + RESET + "%d files, %s" % (
            report.extracted_files, _format_bytes(report.extracted_bytes)
        ))
        print(BOLD + "streamed only: " + RESET + "%d files, %s" % (
            report.skipped_files, _format_bytes(report.skipped_bytes)
        ))
        print(BOLD + "open time: " + RESET + "%.3f s" % report.elapsed_seconds)
    if state.last_query:
        print()
        print(BOLD + "last query: " + RESET + state.last_query)
        print(BOLD + "query kind: " + RESET + state.last_kind)
        if state.answerability:
            print(
                BOLD
                + "answerability: "
                + RESET
                + str(state.answerability.get("state", "unknown"))
            )
        print(BOLD + "query time: " + RESET + "%.3f s" % state.last_elapsed)
        print(BOLD + "matches: " + RESET + str(len(state.hits or [])))
        for hit in (state.hits or [])[:5]:
            print("  " + json.dumps(json_ready(hit), sort_keys=True))
    if state.error:
        print()
        print(BOLD + "error: " + RESET + state.error)
    print()
    print(BOLD + "[o]" + RESET + DIM + " open and validate  " + RESET, end="")
    print(BOLD + "[s]" + RESET + DIM + " search  " + RESET, end="")
    print(BOLD + "[q]" + RESET + DIM + " quit" + RESET)


def _workspace_root(app_mode: bool = False) -> Path:
    if app_mode and sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Offline Explorer" / "workspaces"
    return Path.cwd() / ".offline-explorer" / "workspaces"


def _show_macos_error(message: str) -> None:
    script = """
on run argv
  display alert "Offline Explorer" message (item 1 of argv) as critical buttons {"OK"} default button "OK"
end run
"""
    subprocess.run(
        ["/usr/bin/osascript", "-e", script, message],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _choose_macos_archive() -> Optional[str]:
    script = """
set selectedFile to choose file with prompt "Choose a .genome.tar.gz bundle"
return POSIX path of selectedFile
"""
    while True:
        result = subprocess.run(
            ["/usr/bin/osascript", "-e", script],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return None
        archive = result.stdout.strip()
        if archive.endswith(".genome.tar.gz") and Path(archive).is_file():
            return archive
        _show_macos_error("Choose a file ending in .genome.tar.gz.")


def _choose_archive() -> Optional[str]:
    if sys.platform == "darwin":
        return _choose_macos_archive()
    raise RuntimeError("Open a bundle by passing its path to Offline Explorer.")


def run_tui(archive: str, force_validate: bool) -> None:
    state = PrototypeState(archive=archive)
    while True:
        _render(state)
        action = input("> ").strip().lower()
        if action == "q":
            return
        if action == "o":
            state.error = ""
            state.status = "opening"
            _render(state)
            try:
                state.report = open_bundle(
                    archive, _workspace_root(), force_validate=force_validate
                )
                state.status = "validated and ready"
            except Exception as error:
                state.status = "failed"
                state.error = str(error)
        elif action == "s":
            if not state.report:
                state.error = "open the bundle first"
                continue
            query = input("search: ").strip()
            try:
                result = search_workspace(state.report.workspace, query)
                state.last_query = result.query
                state.last_kind = result.query_kind
                state.last_elapsed = result.elapsed_seconds
                state.hits = result.hits
                state.answerability = result.answerability
                state.error = ""
            except Exception as error:
                state.error = str(error)


def run_batch(archive: str, queries: List[str], force_validate: bool) -> None:
    report = open_bundle(
        archive, _workspace_root(), force_validate=force_validate
    )
    payload = {
        "report": report.to_dict(),
        "searches": [
            search_workspace(report.workspace, query).to_dict() for query in queries
        ],
    }
    print(json.dumps(json_ready(payload), indent=2, sort_keys=True))


def run_server(
    archive: str,
    port: int,
    open_browser: bool,
    force_validate: bool,
    workspace_root: Optional[Path] = None,
) -> None:
    print("Opening the bundle...", flush=True)
    selected_workspace_root = workspace_root or _workspace_root()
    report = open_bundle(
        archive,
        selected_workspace_root,
        force_validate=force_validate,
    )
    serve(
        report,
        workspace_root=selected_workspace_root,
        port=port,
        open_browser=open_browser,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Throwaway selective `.genome` reader prototype"
    )
    parser.add_argument(
        "archive",
        nargs="?",
        help="path to a .genome.tar.gz archive; omit it to choose a file",
    )
    parser.add_argument(
        "--batch",
        action="append",
        default=[],
        metavar="QUERY",
        help="open the archive and run a deterministic query without the TUI",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="open the bundle and serve the local browser interface",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="local port for --serve; defaults to a random available port",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="do not automatically open the browser with --serve",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="force full archive and manifest validation instead of using a receipt",
    )
    parser.add_argument(
        "--desktop-backend",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--workspace-root",
        type=Path,
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()
    if args.desktop_backend:
        if args.archive is not None or args.batch or args.serve:
            parser.error("--desktop-backend cannot be combined with archive commands")
        if args.workspace_root is None:
            parser.error("--desktop-backend requires --workspace-root")
        serve_desktop(
            workspace_root=args.workspace_root.expanduser().resolve(),
            force_validate=args.verify,
            port=args.port,
        )
        return
    if args.batch and args.archive is None:
        parser.error("--batch requires an archive path")
    app_mode = args.archive is None
    if args.batch and args.serve:
        parser.error("--batch and --serve cannot be combined")
    if app_mode:
        try:
            serve_launcher(
                chooser=_choose_archive,
                workspace_root=_workspace_root(app_mode=True),
                force_validate=args.verify,
                port=args.port,
                open_browser=not args.no_browser,
            )
        except Exception as error:
            if sys.platform == "darwin":
                _show_macos_error(str(error))
                return
            raise
        return

    archive = os.path.abspath(os.path.expanduser(args.archive))
    if args.batch:
        run_batch(archive, args.batch, force_validate=args.verify)
    elif args.serve:
        run_server(
            archive,
            args.port,
            open_browser=not args.no_browser,
            force_validate=args.verify,
        )
    else:
        run_tui(archive, force_validate=args.verify)


if __name__ == "__main__":
    main()
