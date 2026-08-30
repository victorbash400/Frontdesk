import importlib.util
import json
from pathlib import Path


def test_backend_package_contains_only_runtime_source() -> None:
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("stage_backend", root / "infra/stage_backend.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    package = module.stage_backend(root)
    manifest = json.loads((package / "build-manifest.json").read_text())
    names = {entry["path"] for entry in manifest["files"]}
    assert "Dockerfile" in names
    assert "backend/requirements.txt" in names
    assert "backend/app/main.py" in names
    assert "backend/meetings/agent_session.py" in names
    for name in names:
        assert name in {"Dockerfile", "backend/requirements.txt"} or (
            name.endswith(".py") and name.split("/")[1] in module.RUNTIME_DIRECTORIES
        )
    assert manifest["total_bytes"] < 5_000_000
