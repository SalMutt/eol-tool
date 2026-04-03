import os
from pathlib import Path


def get_data_dir() -> Path:
    env = os.environ.get("EOL_TOOL_DATA_DIR")
    if env:
        return Path(env)

    # Try relative to this file (works in editable installs and direct runs)
    candidates = [
        Path(__file__).resolve().parent.parent / "data",
        Path(__file__).resolve().parent.parent.parent / "data",
        Path.cwd() / "data",
        Path("/app/data"),
    ]
    for c in candidates:
        if c.is_dir():
            return c

    # Fallback to cwd/data even if it doesn't exist yet
    return Path.cwd() / "data"


def get_overrides_csv() -> Path:
    return get_data_dir() / "manual_overrides.csv"
