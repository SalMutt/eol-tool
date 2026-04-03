from pathlib import Path

from eol_tool.paths import get_data_dir, get_overrides_csv


def test_get_data_dir_returns_path():
    result = get_data_dir()
    assert isinstance(result, Path)


def test_get_data_dir_respects_env_var(tmp_path, monkeypatch):
    monkeypatch.setenv("EOL_TOOL_DATA_DIR", str(tmp_path))
    assert get_data_dir() == tmp_path


def test_get_overrides_csv_returns_csv_path():
    result = get_overrides_csv()
    assert isinstance(result, Path)
    assert result.name == "manual_overrides.csv"
