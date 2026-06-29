from pathlib import Path
from zipfile import ZipFile

from scripts.package_microvm_artifact import create_artifact


def test_create_artifact_includes_microvm_build_inputs(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "Dockerfile.microvm").write_text("FROM python:3.12-slim\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname = 'tango-13'\n", encoding="utf-8")
    (repo / "README.md").write_text("# tango-13\n", encoding="utf-8")
    (repo / "app").mkdir()
    (repo / "app" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "app" / "main.py").write_text("app = None\n", encoding="utf-8")
    (repo / "sandbox_executor").mkdir()
    (repo / "sandbox_executor" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "sandbox_executor" / "server.py").write_text("app = None\n", encoding="utf-8")
    (repo / "sandbox_executor" / "__pycache__").mkdir()
    (repo / "sandbox_executor" / "__pycache__" / "server.pyc").write_bytes(b"ignored")

    artifact = create_artifact(repo, tmp_path / "microvm.zip")

    with ZipFile(artifact) as archive:
        names = set(archive.namelist())

    assert "Dockerfile" in names
    assert "Dockerfile.microvm" not in names
    assert "pyproject.toml" in names
    assert "README.md" in names
    assert "app/main.py" in names
    assert "sandbox_executor/server.py" in names
    assert "sandbox_executor/__pycache__/server.pyc" not in names
