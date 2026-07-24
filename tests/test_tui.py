"""Tests for Textual report builders and CLI TUI gate."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

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

    monkeypatch.setattr("ai.tui.sys.platform", "darwin")
    assert should_use_tui(as_json=True, stream=TTY()) is False
    assert should_use_tui(alerts_only=True, stream=TTY()) is False
    assert should_use_tui(no_tui=True, stream=TTY()) is False


def test_should_use_tui_false_when_not_tty(monkeypatch):
    class Pipe:
        def isatty(self) -> bool:
            return False

    monkeypatch.setattr("ai.tui.sys.platform", "darwin")
    assert should_use_tui(stream=Pipe()) is False


def test_should_use_tui_false_on_windows(monkeypatch):
    class TTY:
        def isatty(self) -> bool:
            return True

    monkeypatch.setattr("ai.tui.sys.platform", "win32")
    assert should_use_tui(stream=TTY()) is False


def test_should_use_tui_true_on_tty_when_textual_present(monkeypatch):
    class TTY:
        def isatty(self) -> bool:
            return True

    monkeypatch.setattr("ai.tui.sys.platform", "darwin")
    if not textual_available():
        return
    assert should_use_tui(stream=TTY()) is True


def test_usage_app_builds_sections_and_css_exists():
    from ai.tui.app import _CSS_PATH, UsageApp

    assert Path(_CSS_PATH).is_file()
    app = UsageApp(_snap_with_account(), [_burn_alert()], brief=True)
    assert any(section.kind == "plan-glance" for section in app._sections)
    assert "providers" not in {section.kind for section in app._sections}
    assert app._sections[-1].kind == "plan-glance"


def test_usage_app_auto_exits_after_paint():
    import asyncio

    from ai.tui.app import UsageApp

    app = UsageApp(_snap_with_account(), [_burn_alert()], brief=True)

    async def _run() -> None:
        async with app.run_test(size=(80, 40)) as pilot:
            await pilot.pause()
            # on_mount schedules exit after refresh; allow it to complete.
            await pilot.pause()

    asyncio.run(_run())
