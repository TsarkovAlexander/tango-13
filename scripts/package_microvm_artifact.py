from __future__ import annotations

import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


INCLUDED_PATHS = ("pyproject.toml", "README.md", "app", "sandbox_executor")


def create_artifact(repo_root: Path, output_path: Path) -> Path:
    repo_root = repo_root.resolve()
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with ZipFile(output_path, "w", compression=ZIP_DEFLATED) as archive:
        archive.write(repo_root / "Dockerfile.microvm", "Dockerfile")
        for relative_path in INCLUDED_PATHS:
            source = repo_root / relative_path
            if source.is_file():
                archive.write(source, relative_path)
                continue
            for path in sorted(source.rglob("*")):
                if _should_skip(path):
                    continue
                archive.write(path, path.relative_to(repo_root).as_posix())

    return output_path


def _should_skip(path: Path) -> bool:
    return (
        path.is_dir()
        or "__pycache__" in path.parts
        or path.suffix in {".pyc", ".pyo"}
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Package the Lambda MicroVM build artifact.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root containing Dockerfile.microvm, app/, and sandbox_executor/.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("dist/tango-microvm.zip"),
        help="Zip artifact path to create.",
    )
    args = parser.parse_args()

    artifact = create_artifact(args.repo_root, args.output)
    print(artifact)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
