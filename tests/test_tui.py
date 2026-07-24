"""Tests for styled report builders and CLI display gate."""

from __future__ import annotations

from datetime import timedelta

from ai.models import (
    AccountUsage,
    BillingKind,
    QuotaWindow,
    Snapshot,
    Urgency,
    UseOrLoseAlert,
    utcnow,
)
from ai.tui import should_use_tui, textual_available
from ai.tui.builders import alert_headline, build_report_sections


def _snap_with_account() -> Snapshot:
    return Snapshot(
        collected_at=utcnow(),
        accounts=[
            AccountUsage(
                source="codexbar",
                provider="codex",
                billing_kind=BillingKind.SUBSCRIPTION_WINDOW,
                windows=[
                    QuotaWindow(
                        label="Codex weekly quota",
                        used_percent=10,
                        remaining_percent=90,
                        resets_at=utcnow() + timedelta(days=3),
                        window_minutes=10080,
                    )
                ],
            )
        ],
    )


def _burn_alert() -> UseOrLoseAlert:
    return UseOrLoseAlert(
        urgency=Urgency.HIGH,
        provider="codex",
        account="user@example.com",
        window_label="Codex weekly quota",
        remaining_percent=90.0,
        days_until_reset=3.0,
        plan=None,
        message="burn it",
        source="codexbar",
        score=80.0,
        kind="burn",
    )


def test_build_report_sections_includes_plan_and_providers():
    sections = build_report_sections(_snap_with_account(), [_burn_alert()], brief=False)
    kinds = [s.kind for s in sections]
    assert "header" in kinds
    assert "plan" in kinds
    assert "plan-glance" in kinds
    assert "providers" in kinds
    assert "tips" in kinds
    assert kinds[-1] == "plan-glance"
    plan = next(s for s in sections if s.kind == "plan")
    assert any("Codex" in line for line in plan.lines)


def test_build_report_sections_brief_omits_providers():
    sections = build_report_sections(_snap_with_account(), [_burn_alert()], brief=True)
    kinds = [s.kind for s in sections]
    assert "providers" not in kinds
    assert "plan" not in kinds
    assert "plan-glance" in kinds
    assert "header" in kinds
    assert kinds[-1] == "plan-glance"


def test_build_report_sections_includes_collector_errors():
    snap = _snap_with_account()
    snap.collector_errors.append("tokscale: timeout")
    sections = build_report_sections(snap, [], brief=True)
    errors = next(s for s in sections if s.kind == "errors")
    assert any("tokscale" in line for line in errors.lines)


def test_alert_headline_contains_provider_and_percent():
    line = alert_headline(_burn_alert())
    assert "Codex" in line
    assert "90%" in line


def test_should_use_tui_false_for_json_and_no_tui(monkeypatch):
    class TTY:
        def isatty(self) -> bool:
            return True

    assert should_use_tui(as_json=True, stream=TTY()) is False
    assert should_use_tui(alerts_only=True, stream=TTY()) is False
    assert should_use_tui(no_tui=True, stream=TTY()) is False


def test_should_use_tui_false_when_not_tty():
    class Pipe:
        def isatty(self) -> bool:
            return False

    assert should_use_tui(stream=Pipe()) is False


def test_should_use_tui_true_on_tty_when_rich_present():
    class TTY:
        def isatty(self) -> bool:
            return True

    if not textual_available():
        return
    assert should_use_tui(stream=TTY()) is True


def test_run_usage_app_prints_full_report_including_glance(capsys):
    from ai.tui.app import run_usage_app

    run_usage_app(_snap_with_account(), [_burn_alert()], brief=False)
    out = capsys.readouterr().out
    assert "AI USAGE" in out
    assert "Per-provider usage" in out
    assert "Action plan — at a glance" in out
    assert out.index("Per-provider") < out.index("at a glance")


def test_run_usage_app_brief_still_ends_on_glance(capsys):
    from ai.tui.app import run_usage_app

    run_usage_app(_snap_with_account(), [_burn_alert()], brief=True)
    out = capsys.readouterr().out
    assert "at a glance" in out
    assert "Per-provider usage" not in out
