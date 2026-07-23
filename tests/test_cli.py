from ai import cli
from ai.models import CrossCheck, Snapshot, utcnow


def test_alerts_only_includes_cross_check_warnings(monkeypatch, capsys):
    snapshot = Snapshot(
        collected_at=utcnow(),
        cross_checks=[
            CrossCheck(
                provider="copilot",
                account="user@example.com",
                status="warning",
                sources=["CodexBar", "tokscale"],
                message="The quota percentages disagree.",
            )
        ],
    )
    monkeypatch.setattr(cli, "run_collectors", lambda _config: snapshot)

    assert cli.main(["--alerts-only", "--no-color"]) == 0
    output = capsys.readouterr().out
    assert "[cross-check warning] GitHub Copilot" in output
    assert "user@example.com" in output
    assert "percentages disagree" in output


def test_json_alerts_only_includes_structured_cross_check_warnings(monkeypatch, capsys):
    snapshot = Snapshot(
        collected_at=utcnow(),
        cross_checks=[
            CrossCheck(
                provider="codex",
                account=None,
                status="warning",
                sources=["CodexBar", "tokscale"],
                message="One tool failed.",
            )
        ],
    )
    monkeypatch.setattr(cli, "run_collectors", lambda _config: snapshot)

    assert cli.main(["--json", "--alerts-only"]) == 0
    output = capsys.readouterr().out
    assert '"cross_check_warnings"' in output
    assert '"One tool failed."' in output


def test_show_config_path_exits_without_collecting(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    def fail_if_called(_config):
        raise AssertionError("collectors should not run")

    monkeypatch.setattr(cli, "run_collectors", fail_if_called)

    assert cli.main(["--show-config-path"]) == 0
    out = capsys.readouterr().out
    assert f"services: {tmp_path / 'ai' / 'services.yaml'}" in out
    assert f"settings: {tmp_path / 'ai' / 'config.toml'}" in out


def test_cli_timeout_flag_sets_force(monkeypatch):
    captured = {}

    def fake_collectors(config):
        captured["timeouts"] = dict(config.get("timeouts") or {})
        return Snapshot(collected_at=utcnow())

    monkeypatch.setattr(cli, "run_collectors", fake_collectors)
    monkeypatch.setattr(cli, "analyze_use_or_lose", lambda *_a, **_k: [])
    assert cli.main(["--timeout", "12", "--json", "--alerts-only"]) == 0
    assert captured["timeouts"]["force"] == 12.0
    assert captured["timeouts"]["default"] == 12.0

    assert cli.main(["-t45", "--json", "--alerts-only"]) == 0
    assert captured["timeouts"]["force"] == 45.0


def test_generate_config_creates_files_and_refuses_overwrite(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert cli.main(["--generate-config"]) == 0
    out = capsys.readouterr()
    assert "created:" in out.out
    assert (tmp_path / "ai" / "config.toml").is_file()
    assert (tmp_path / "ai" / "services.yaml").is_file()

    assert cli.main(["--generate-config"]) == 1
    err = capsys.readouterr().err
    assert "exists (not overwritten)" in err
    assert "already exist" in err or "left unchanged" in err
