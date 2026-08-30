"""Build an allowlisted Cloud Build source directory without local user data."""

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIRECTORIES = ("app", "agents", "tools", "meetings")


def stage_backend(root: Path = ROOT) -> Path:
    destination = Path(tempfile.mkdtemp(prefix="front-desk-backend-build-"))
    shutil.copy2(root / "Dockerfile", destination / "Dockerfile")
    (destination / "backend").mkdir()
    shutil.copy2(root / "backend/requirements.txt", destination / "backend/requirements.txt")
    for directory in RUNTIME_DIRECTORIES:
        for source in sorted((root / "backend" / directory).rglob("*.py")):
            if "__pycache__" in source.parts or source.is_symlink():
                continue
            target = destination / source.relative_to(root)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    files = sorted(path for path in destination.rglob("*") if path.is_file())
    manifest = {
        "files": [{
            "path": str(path.relative_to(destination)),
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        } for path in files],
        "total_bytes": sum(path.stat().st_size for path in files),
    }
    (destination / "build-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(stage_backend())
