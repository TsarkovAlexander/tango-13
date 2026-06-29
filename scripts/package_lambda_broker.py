from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


INCLUDED_PATHS = ("app", "sandbox_executor")
LAMBDA_DEPENDENCIES = (
    "boto3",
    "botocore[crt]",
    "fastapi",
    "httpx",
    "mangum",
    "pydantic-settings",
    "temporalio",
    "uvicorn",
)


def create_artifact(
    repo_root: Path,
    output_path: Path,
    *,
    dependencies_path: Path | None = None,
) -> Path:
    repo_root = repo_root.resolve()
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if dependencies_path is None:
        with tempfile.TemporaryDirectory() as temp_dir:
            dependency_dir = Path(temp_dir) / "python"
            _install_dependencies(repo_root, dependency_dir)
            _write_artifact(repo_root, output_path, dependency_dir)
    else:
        _write_artifact(repo_root, output_path, dependencies_path.resolve())

    return output_path


def _install_dependencies(repo_root: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--platform",
            "manylinux2014_aarch64",
            "--implementation",
            "cp",
            "--python-version",
            "3.12",
            "--only-binary=:all:",
            "--target",
            str(target),
            *LAMBDA_DEPENDENCIES,
        ],
        check=True,
        cwd=repo_root,
    )


def _write_artifact(repo_root: Path, output_path: Path, dependencies_path: Path) -> None:
    with ZipFile(output_path, "w", compression=ZIP_DEFLATED) as archive:
        _write_tree(archive, dependencies_path, dependencies_path, skip_top_level=set(INCLUDED_PATHS))
        for relative_path in INCLUDED_PATHS:
            source = repo_root / relative_path
            _write_tree(archive, source, repo_root)


def _write_tree(
    archive: ZipFile,
    source: Path,
    root: Path,
    *,
    skip_top_level: set[str] | None = None,
) -> None:
    for path in sorted(source.rglob("*")):
        if _should_skip(path):
            continue
        relative_path = path.relative_to(root)
        if skip_top_level is not None and relative_path.parts[0] in skip_top_level:
            continue
        archive.write(path, relative_path.as_posix())


def _should_skip(path: Path) -> bool:
    return path.is_dir() or "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Package the Lambda broker function artifact.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root containing app/ and sandbox_executor/.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("dist/tango-broker-lambda.zip"),
        help="Zip artifact path to create.",
    )
    parser.add_argument(
        "--dependencies-path",
        type=Path,
        default=None,
        help="Optional prebuilt Lambda dependency directory.",
    )
    args = parser.parse_args()

    artifact = create_artifact(
        args.repo_root,
        args.output,
        dependencies_path=args.dependencies_path,
    )
    print(artifact)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
