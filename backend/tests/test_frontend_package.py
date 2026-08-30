import importlib.util
from pathlib import Path


def test_frontend_package_excludes_private_and_generated_files() -> None:
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("stage_frontend", root / "infra/stage_frontend.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    staged = module.stage_frontend(root)
    files = [path.relative_to(staged) for path in staged.rglob("*") if path.is_file()]
    assert Path("Dockerfile") in files
    assert Path("app/extension/page.tsx") in files
    assert Path("extension/manifest.json") in files
    assert Path("public/reception-svgrepo-com.svg") in files
    assert all(not any(part in {"backend", "native", "node_modules", "dist", ".next"} for part in path.parts) for path in files)
    assert all(not any(part.startswith(".") for part in path.parts) for path in files)
    assert sum((staged / path).stat().st_size for path in files) < 10_000_000
