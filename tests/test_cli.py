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
    assert capsys.readouterr().out.strip() == str(tmp_path / "ai" / "services.yaml")
