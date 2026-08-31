from __future__ import annotations

import importlib.metadata
import shutil
import sys
import sysconfig
from pathlib import Path


def distribution_license(distribution_name: str, suffix: str) -> Path:
    distribution = importlib.metadata.distribution(distribution_name)
    for relative_path in distribution.files or []:
        normalized = str(relative_path).replace("\\", "/").lower()
        if normalized.endswith(suffix.lower()):
            path = Path(distribution.locate_file(relative_path))
            if path.is_file():
                return path
    raise FileNotFoundError(
        "Could not find %s in the installed %s distribution."
        % (suffix, distribution_name)
    )


def python_license() -> Path:
    candidates = [
        Path(sysconfig.get_path("stdlib")) / "LICENSE.txt",
        Path(sys.base_prefix) / "LICENSE.txt",
        Path(sys.base_prefix) / "LICENSE",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("Could not find the Python runtime license.")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: collect-engine-licenses.py OUTPUT_DIRECTORY")
    output_directory = Path(sys.argv[1]).resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    licenses = {
        "DUCKDB-LICENSE.txt": distribution_license("duckdb", "licenses/license"),
        "PYINSTALLER-LICENSE.txt": distribution_license(
            "pyinstaller", "licenses/copying.txt"
        ),
        "PYTHON-LICENSE.txt": python_license(),
    }
    for output_name, source in licenses.items():
        shutil.copyfile(source, output_directory / output_name)


if __name__ == "__main__":
    main()
