"""Stage only frontend and extension build inputs, never local data or secrets."""

import shutil
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILES = (
    "package.json", "pnpm-lock.yaml", "pnpm-workspace.yaml", "next.config.ts",
    "tsconfig.json", "auth.ts",
)
DIRECTORIES = ("app", "public", "types", "patches", "extension")
EXCLUDED = {"node_modules", "dist", ".next", "__pycache__", "downloads"}


def stage_frontend(root: Path = ROOT) -> Path:
    target = Path(tempfile.mkdtemp(prefix="front-desk-frontend-build-"))
    for name in FILES:
        shutil.copy2(root / name, target / name)
    for name in DIRECTORIES:
        source = root / name
        if not source.exists():
            continue
        for path in source.rglob("*"):
            relative = path.relative_to(root)
            if not path.is_file() or path.is_symlink():
                continue
            if any(part in EXCLUDED or part.startswith(".") for part in relative.parts):
                continue
            if path.suffix in {".map", ".tsbuildinfo", ".zip"}:
                continue
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
    shutil.copy2(root / "infra/Dockerfile.frontend", target / "Dockerfile")
    return target


if __name__ == "__main__":
    print(stage_frontend())
