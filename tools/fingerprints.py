"""Detect whether recorded verification still matches the implementation."""
import hashlib
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


def source_hash():
    paths = []
    for folder in ("healthcare_quality", "tests", "tools"):
        paths.extend(p for p in (ROOT/folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix in {".py",".json",".html",".css",".js"})
    paths.extend(ROOT/name for name in ("requirements.txt","requirements-dev.txt","pytest.ini"))
    paths.extend((ROOT/".github/workflows").glob("*.yml"))
    paths.extend((ROOT/".github/workflows").glob("*.yaml"))
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(str(path.relative_to(ROOT)).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()
