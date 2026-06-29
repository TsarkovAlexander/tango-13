from pathlib import Path
from zipfile import ZipFile


def test_create_lambda_broker_artifact_includes_handler_and_dependencies(tmp_path: Path) -> None:
    from scripts.package_lambda_broker import create_artifact

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app").mkdir()
    (repo / "app" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "app" / "settings.py").write_text("class Settings: pass\n", encoding="utf-8")
    (repo / "sandbox_executor").mkdir()
    (repo / "sandbox_executor" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "sandbox_executor" / "lambda_broker.py").write_text("handler = None\n", encoding="utf-8")
    (repo / "sandbox_executor" / "__pycache__").mkdir()
    (repo / "sandbox_executor" / "__pycache__" / "lambda_broker.pyc").write_bytes(b"ignored")

    dependencies = tmp_path / "deps"
    dependencies.mkdir()
    (dependencies / "mangum").mkdir()
    (dependencies / "mangum" / "__init__.py").write_text("class Mangum: pass\n", encoding="utf-8")
    (dependencies / "app").mkdir()
    (dependencies / "app" / "settings.py").write_text("stale = True\n", encoding="utf-8")
    (dependencies / "mangum" / "__pycache__").mkdir()
    (dependencies / "mangum" / "__pycache__" / "__init__.pyc").write_bytes(b"ignored")

    artifact = create_artifact(repo, tmp_path / "broker.zip", dependencies_path=dependencies)

    with ZipFile(artifact) as archive:
        names = set(archive.namelist())
        app_settings = archive.read("app/settings.py")

    assert "app/settings.py" in names
    assert "sandbox_executor/lambda_broker.py" in names
    assert "mangum/__init__.py" in names
    assert app_settings == b"class Settings: pass\n"
    assert "sandbox_executor/__pycache__/lambda_broker.pyc" not in names
    assert "mangum/__pycache__/__init__.pyc" not in names
