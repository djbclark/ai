from pathlib import Path

from ai.config import default_config_path, load_config


def test_default_config_path_uses_xdg_config_home(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    assert default_config_path() == tmp_path / "ai" / "services.yaml"


def test_load_config_reads_xdg_ai_directory(monkeypatch, tmp_path):
    config_path = tmp_path / "ai" / "services.yaml"
    config_path.parent.mkdir()
    config_path.write_text("analysis:\n  min_remaining_percent: 55\n", encoding="utf-8")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    config = load_config()

    assert config["analysis"]["min_remaining_percent"] == 55


def test_relative_xdg_config_home_is_ignored(monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", "relative/path")

    assert default_config_path() == Path.home() / ".config" / "ai" / "services.yaml"
