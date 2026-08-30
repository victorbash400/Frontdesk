import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory


def test_agent_engine_package_excludes_backend_records_and_browser_dependencies() -> None:
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("deploy_agent_engine", root / "infra/deploy_agent_engine.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with TemporaryDirectory(prefix="front-desk-agent-package-test-") as directory:
        package = Path(directory)
        assert module.stage_runtime(package) == ["agent_runtime"]
        files = sorted(path for path in package.rglob("*") if path.is_file())
        assert {str(path.relative_to(package)) for path in files} == {
            "agent_runtime/__init__.py", "agent_runtime/agent.py", "agent_runtime/relay.py", "requirements.txt",
        }
        assert sum(path.stat().st_size for path in files) < 50_000
