"""Resolve the data directory across dev and Docker installs."""
from pathlib import Path


def data_dir() -> Path:
    """Return the data/ directory, checking multiple locations."""
    cwd = Path.cwd() / "data"
    if cwd.is_dir():
        return cwd
    pkg = Path(__file__).resolve().parent.parent.parent / "data"
    if pkg.is_dir():
        return pkg
    return cwd
