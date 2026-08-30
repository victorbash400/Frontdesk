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
    assert "package.json" not in names
    assert "extension/package.json" not in names
    node_dependencies = json.loads((package / "infra/browser-runtime/package.json").read_text())["dependencies"]
    assert set(node_dependencies) == {"@playwright/mcp"}
    for name in names:
        assert name in module.BUILD_FILES or (
            name.endswith(".py") and name.split("/")[1] in module.RUNTIME_DIRECTORIES
        )
    assert manifest["total_bytes"] < 5_000_000
