"""Build build/lambda.zip, the deployment package for the collector Lambda.

Run from the repo root:  uv run scripts/build_lambda.py

The zip holds the db_delay_tracker package plus the "lambda" dependency group
from pyproject.toml, at the exact versions pinned in uv.lock. The Lambda runs
on Linux arm64, so dependencies are downloaded as manylinux aarch64 wheels, not
the Windows ones installed in your .venv.

The zip is byte-for-byte reproducible (sorted entries, fixed timestamps), so
Terraform only redeploys the function when the code or dependencies change.
"""

from __future__ import annotations

import shutil
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
PACKAGE_DIR = BUILD / "package"
ZIP_PATH = BUILD / "lambda.zip"

PYTHON_VERSION = "3.13"  # must match the runtime in infra/lambda.tf
PLATFORM = "aarch64-manylinux2014"  # must match architectures in infra/lambda.tf
FIXED_TIMESTAMP = (1980, 1, 1, 0, 0, 0)  # earliest time a zip can store


def run(*args: str) -> str:
    return subprocess.run(args, cwd=ROOT, check=True, capture_output=True, text=True).stdout


def main() -> None:
    if BUILD.exists():
        shutil.rmtree(BUILD)
    PACKAGE_DIR.mkdir(parents=True)

    requirements = run(
        "uv", "export", "--only-group", "lambda", "--no-hashes", "--no-emit-project", "--frozen"
    )
    requirements_file = BUILD / "requirements.txt"
    requirements_file.write_text(requirements, encoding="utf-8")

    run(
        "uv", "pip", "install",
        "--target", str(PACKAGE_DIR),
        "--python-platform", PLATFORM,
        "--python-version", PYTHON_VERSION,
        "--only-binary", ":all:",
        "-r", str(requirements_file),
    )

    shutil.copytree(
        ROOT / "src" / "db_delay_tracker",
        PACKAGE_DIR / "db_delay_tracker",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )

    files = sorted(p for p in PACKAGE_DIR.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            info = zipfile.ZipInfo(path.relative_to(PACKAGE_DIR).as_posix(), FIXED_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, path.read_bytes())

    size_mb = ZIP_PATH.stat().st_size / 1_000_000
    print(f"{ZIP_PATH.relative_to(ROOT)}: {len(files)} files, {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
