from ai.models import AccountUsage, FlexibilityClass, FlexibilityProfile, Urgency, UseOrLoseAlert
from ai.report import _Style, _sorted_accounts, _throttled_waste_line


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
