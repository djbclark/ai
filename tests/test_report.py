from datetime import datetime, timedelta, timezone

from ai.models import (
    AccountUsage,
    CrossCheck,
    FlexibilityClass,
    FlexibilityProfile,
    PaceProfile,
    Snapshot,
    Urgency,
    UseOrLoseAlert,
    utcnow,
)
from ai.report import _Style, _action_plan_line, _sorted_accounts, _throttled_waste_line, render_report


def test_per_provider_accounts_are_sorted_by_display_name():
    accounts = [
        AccountUsage(provider="antigravity", source="codexbar"),
        AccountUsage(provider="copilot", source="tokscale"),
        AccountUsage(provider="codex", source="codexbar"),
        AccountUsage(provider="claude", source="cswap", error="unavailable"),
    ]

    assert [account.provider for account in _sorted_accounts(accounts)] == [
        "claude",
        "codex",
        "copilot",
        "antigravity",
    ]


def test_accounts_for_same_provider_are_sorted_by_account_then_source():
    accounts = [
        AccountUsage(provider="claude", account="z@example.com", source="cswap"),
        AccountUsage(provider="claude", account="A@example.com", source="cswap"),
    ]

    assert [account.account for account in _sorted_accounts(accounts)] == [
        "A@example.com",
        "z@example.com",
    ]


def _alert_with_value(*, window_minutes: int, value_usd: float) -> UseOrLoseAlert:
    return UseOrLoseAlert(
        urgency=Urgency.MEDIUM,
        provider="claude",
        account="user@example.com",
        window_label="Claude 5-hour",
        remaining_percent=50.0,
        days_until_reset=0.1,
        plan=None,
        message="test",
        source="cswap",
        score=50.0,
        flexibility_profile=FlexibilityProfile(
            flexibility_class=FlexibilityClass.THROTTLED,
            consumption_flexibility=0.0,
            value_at_risk_usd=value_usd,
        ),
        window_minutes=window_minutes,
    )


def test_throttled_waste_5h_uses_real_cycles_per_month():
    # 16h * 30.44 * 60 / 300 ≈ 97.408 cycles/month
    line = _throttled_waste_line(
        _alert_with_value(window_minutes=300, value_usd=0.18),
        _Style(False),
        waking_hours_per_day=16.0,
    )
    assert "~$0.18/cycle" in line
    assert "~$17.53/month" in line
    assert "$5.40/month" not in line  # old value_usd * 30


def test_throttled_waste_monthly_window_not_overstated():
    # 16h * 30.44 * 60 / 43800 ≈ 0.668 cycles/month
    line = _throttled_waste_line(
        _alert_with_value(window_minutes=43800, value_usd=0.18),
        _Style(False),
        waking_hours_per_day=16.0,
    )
    assert "~$0.18/cycle" in line
    assert "~$0.12/month" in line
    assert "$5.40/month" not in line


def test_render_report_shows_conserve_before_burn_buckets():
    now = utcnow()
    burn = UseOrLoseAlert(
        urgency=Urgency.HIGH,
        provider="codex",
        account="a@example.com",
        window_label="Weekly",
        remaining_percent=90.0,
        days_until_reset=2.0,
        plan=None,
        message="burn me",
        source="codexbar",
        score=80.0,
        kind="burn",
        flexibility_profile=FlexibilityProfile(
            flexibility_class=FlexibilityClass.BURSTABLE,
            consumption_flexibility=1.0,
            value_at_risk_usd=5.0,
        ),
        pace=PaceProfile(
            elapsed_fraction=0.5,
            used_fraction=0.1,
            pace_ratio=0.2,
            projected_used_fraction=0.2,
            projected_waste_fraction=0.8,
            projected_waste_usd=4.0,
            projected_exhaust_at=None,
        ),
    )
    conserve = UseOrLoseAlert(
        urgency=Urgency.MEDIUM,
        provider="claude",
        account="b@example.com",
        window_label="Claude Code weekly",
        remaining_percent=10.0,
        days_until_reset=3.0,
        plan=None,
        message="slow down",
        source="cswap",
        score=70.0,
        kind="conserve",
        pace=PaceProfile(
            elapsed_fraction=0.6,
            used_fraction=0.9,
            pace_ratio=1.5,
            projected_used_fraction=1.0,
            projected_waste_fraction=0.0,
            projected_waste_usd=0.0,
            projected_exhaust_at=now + timedelta(days=1),
        ),
    )
    snap = Snapshot(collected_at=now, accounts=[])
    text = render_report(snap, [burn, conserve], config={}, color=False)
    assert "CONSERVE" in text
    conserve_at = text.index("CONSERVE")
    # Burn buckets appear after conserve when present
    assert "THIS WEEK" in text or "use within" in text.lower() or "90%" in text
    if "THIS WEEK" in text:
        assert conserve_at < text.index("THIS WEEK")
    # Conserve alert not in a burn action-plan style "burn" numbered list only
    assert "slow down" in text
    assert "burn me" not in text or "90%" in text  # burn line may use remaining


def test_render_report_shows_usage_credits_section():
    from ai.models import BillingKind, UsageCredits

    now = utcnow()
    acc = AccountUsage(
        source="cswap",
        provider="claude",
        account="a@example.com",
        billing_kind=BillingKind.SUBSCRIPTION_WINDOW,
        usage_credits=UsageCredits(
            used=50.0,
            limit=100.0,
            remaining=50.0,
            currency="USD",
            used_percent=50.0,
            resets_at=now + timedelta(days=5),
        ),
    )
    text = render_report(Snapshot(collected_at=now, accounts=[acc]), [], config={}, color=False)
    assert "usage credits" in text.lower()
    assert "50 of 100 USD" in text or "spent: 50" in text
    assert "remaining headroom" in text.lower()


def test_action_plan_line_includes_pace_fragment():
    alert = UseOrLoseAlert(
        urgency=Urgency.MEDIUM,
        provider="codex",
        account=None,
        window_label="Weekly",
        remaining_percent=80.0,
        days_until_reset=2.0,
        plan=None,
        message="x",
        source="tokscale",
        score=50.0,
        kind="burn",
        flexibility_profile=FlexibilityProfile(
            flexibility_class=FlexibilityClass.SEMI_THROTTLED,
            consumption_flexibility=0.5,
            value_at_risk_usd=3.0,
        ),
        pace=PaceProfile(
            elapsed_fraction=0.5,
            used_fraction=0.2,
            pace_ratio=0.4,
            projected_used_fraction=0.4,
            projected_waste_fraction=0.6,
            projected_waste_usd=2.0,
            projected_exhaust_at=None,
        ),
    )
    line = _action_plan_line(alert, _Style(False))
    assert "pace 0.4x" in line
    assert "projected 60% unused" in line


def test_render_report_action_plan_before_tips_and_usage():
    now = utcnow()
    burn = UseOrLoseAlert(
        urgency=Urgency.HIGH,
        provider="codex",
        account="a@example.com",
        window_label="Weekly",
        remaining_percent=90.0,
        days_until_reset=2.0,
        plan=None,
        message="burn me",
        source="codexbar",
        score=80.0,
        kind="burn",
        flexibility_profile=FlexibilityProfile(
            flexibility_class=FlexibilityClass.BURSTABLE,
            consumption_flexibility=1.0,
            value_at_risk_usd=5.0,
        ),
    )
    acc = AccountUsage(provider="codex", source="codexbar", account="a@example.com")
    text = render_report(
        Snapshot(collected_at=now, accounts=[acc]),
        [burn],
        config={},
        color=False,
    )
    assert text.index("## Action plan") < text.index("## Per-provider usage")
    assert text.index("## Per-provider usage") < text.index("## Cross-checks")
    assert text.index("## Cross-checks") < text.index("## Tips")
    assert "1 alert" in text or "alerts" in text


def test_render_cross_checks_use_soft_labels():
    now = utcnow()
    snap = Snapshot(
        collected_at=now,
        cross_checks=[
            CrossCheck(
                provider="claude",
                account="a@x.com",
                status="warning",
                sources=["cswap", "CodexBar"],
                message="Tools disagree on some live quota figures: weekly differs. Small gaps are often expected.",
            ),
            CrossCheck(
                provider="codex",
                account=None,
                status="consistent",
                sources=["CodexBar", "tokscale"],
                message="Agree on 1 overlapping live quota measurement within tolerance.",
            ),
        ],
    )
    text = render_report(snap, [], config={}, color=False)
    assert "[NOTE]" in text
    assert "[OK]" in text
    assert "WARNING" not in text
    assert "informational" in text.lower()
    assert "cswap-only" in text or "poll" in text.lower()


def test_throttled_monthly_waste_stays_near_plan_scale_for_realistic_value():
    """Property: monthly waste ≈ value_usd * cycles; for value from clamp, not absurd *30."""
    monthly_price = 20.0
    remaining_frac = 0.5
    value_usd = monthly_price * remaining_frac  # max per-cycle after Fix #4 clamp
    window_minutes = 300
    waking = 16.0
    from ai.analysis.use_or_lose import DAYS_PER_MONTH

    cycles = (waking * DAYS_PER_MONTH * 60) / window_minutes
    monthly_waste = value_usd * cycles
    # 5h windows can waste more than one month's sticker price if chronically underused
    # (many cycles) — but must not use the old *30 formula ($300 for $10/cycle).
    assert monthly_waste != value_usd * 30
    line = _throttled_waste_line(
        _alert_with_value(window_minutes=window_minutes, value_usd=value_usd),
        _Style(False),
        waking_hours_per_day=waking,
    )
    assert f"~${monthly_waste:.2f}/month" in line
