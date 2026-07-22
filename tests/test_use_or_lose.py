"""Unit tests for use-or-lose analysis (no live CLI required)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ai.analysis.use_or_lose import (
    _classify_flexibility,
    _compute_value_at_risk,
    _redistribute_weights,
    _score_multi_dimension,
    analyze_use_or_lose,
)
from ai.models import (
    AccountUsage,
    BillingKind,
    FlexibilityClass,
    FlexibilityProfile,
    QuotaWindow,
    Snapshot,
    Urgency,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def test_flags_nearly_unused_weekly_window():
    snap = Snapshot(
        collected_at=_now(),
        accounts=[
            AccountUsage(
                source="codexbar",
                provider="codex",
                account="user@example.com",
                plan="plus",
                billing_kind=BillingKind.SUBSCRIPTION_WINDOW,
                windows=[
                    QuotaWindow(
                        label="Weekly",
                        used_percent=0,
                        remaining_percent=100,
                        resets_at=_now() + timedelta(days=3),
                        window_minutes=10080,
                    )
                ],
            )
        ],
    )
    alerts = analyze_use_or_lose(
        snap,
        {
            "analysis": {
                "min_remaining_percent": 40,
                "max_days_until_reset": 14,
                "urgent_remaining_percent": 70,
                "urgent_days_until_reset": 7,
            },
            "plans": {"codex": {"name": "Codex Plus"}},
        },
    )
    assert alerts
    assert alerts[0].provider == "codex"
    assert alerts[0].remaining_percent == 100
    assert alerts[0].urgency in (Urgency.CRITICAL, Urgency.HIGH)


def test_ignores_short_5h_window():
    snap = Snapshot(
        collected_at=_now(),
        accounts=[
            AccountUsage(
                source="codexbar",
                provider="claude",
                billing_kind=BillingKind.SUBSCRIPTION_WINDOW,
                windows=[
                    QuotaWindow(
                        label="5-hour",
                        used_percent=0,
                        remaining_percent=100,
                        resets_at=_now() + timedelta(hours=4),
                    )
                ],
            )
        ],
    )
    alerts = analyze_use_or_lose(snap, {"analysis": {"min_remaining_percent": 40}})
    assert not any(a.window_label == "5-hour" for a in alerts)


def test_prepaid_is_info_only():
    snap = Snapshot(
        collected_at=_now(),
        accounts=[
            AccountUsage(
                source="codexbar",
                provider="openrouter",
                billing_kind=BillingKind.PREPAID_BALANCE,
                balance_usd=18.90,
            )
        ],
    )
    alerts = analyze_use_or_lose(snap, {})
    assert len(alerts) == 1
    assert alerts[0].urgency == Urgency.INFO


def test_well_used_window_not_flagged():
    snap = Snapshot(
        collected_at=_now(),
        accounts=[
            AccountUsage(
                source="codexbar",
                provider="grok",
                billing_kind=BillingKind.SUBSCRIPTION_WINDOW,
                windows=[
                    QuotaWindow(
                        label="Weekly",
                        used_percent=90,
                        remaining_percent=10,
                        resets_at=_now() + timedelta(days=2),
                    )
                ],
            )
        ],
    )
    alerts = analyze_use_or_lose(snap, {"analysis": {"min_remaining_percent": 40}})
    assert alerts == []


def test_max_days_override_allows_later_window():
    snap = Snapshot(
        collected_at=_now(),
        accounts=[
            AccountUsage(
                source="codexbar",
                provider="copilot",
                billing_kind=BillingKind.SUBSCRIPTION_WINDOW,
                windows=[
                    QuotaWindow(
                        label="GitHub Copilot completions",
                        used_percent=0,
                        remaining_percent=100,
                        resets_at=_now() + timedelta(days=20),
                    )
                ],
            )
        ],
    )
    alerts = analyze_use_or_lose(
        snap,
        {
            "analysis": {
                "min_remaining_percent": 40,
                "max_days_until_reset": 30,
                "urgent_remaining_percent": 101,
            }
        },
    )
    assert len(alerts) == 1


def test_expired_window_is_not_actionable():
    snap = Snapshot(
        collected_at=_now(),
        accounts=[
            AccountUsage(
                source="codexbar",
                provider="codex",
                billing_kind=BillingKind.SUBSCRIPTION_WINDOW,
                windows=[
                    QuotaWindow(
                        label="Codex weekly quota",
                        used_percent=0,
                        remaining_percent=100,
                        resets_at=_now() - timedelta(minutes=1),
                        window_minutes=10080,
                    )
                ],
            )
        ],
    )
    assert analyze_use_or_lose(snap, {}) == []


def test_alert_has_no_dollar_value_estimate():
    snap = Snapshot(
        collected_at=_now(),
        accounts=[
            AccountUsage(
                source="codexbar",
                provider="codex",
                billing_kind=BillingKind.SUBSCRIPTION_WINDOW,
                windows=[
                    QuotaWindow(
                        label="Codex weekly quota",
                        used_percent=0,
                        remaining_percent=100,
                        resets_at=_now() + timedelta(days=2),
                        window_minutes=10080,
                    )
                ],
            )
        ],
    )
    alert = analyze_use_or_lose(
        snap,
        {"plans": {"codex": {"name": "Codex Plus", "monthly_usd": 20}}},
    )[0]
    assert "monthly_usd" not in alert.to_dict()
    assert "$" not in alert.message


# --- Phase 2: multi-dimensional scoring tests ---


def test_redistribute_weights_sums_to_one():
    for flex in (0.0, 0.25, 0.5, 0.75, 1.0):
        w = _redistribute_weights(flex)
        assert abs(sum(w) - 1.0) < 0.001, f"flex={flex}: sum={sum(w)}"


def test_redistribute_weights_extremes():
    w0 = _redistribute_weights(0.0)
    assert w0 == (0.35, 0.30, 0.35)
    w1 = _redistribute_weights(1.0)
    assert w1 == (0.50, 0.00, 0.50)


def test_redistribute_weights_midpoint():
    w = _redistribute_weights(0.5)
    assert w[0] == 0.425
    assert w[1] == 0.15
    assert w[2] == 0.425


def test_classify_flexibility_throttled():
    cls, score = _classify_flexibility(
        window_minutes=300, provider="claude", config={"consumption_flexibility_defaults": {"5h": 0.0}}
    )
    assert cls == FlexibilityClass.THROTTLED
    assert score == 0.0


def test_classify_flexibility_semi():
    cls, score = _classify_flexibility(
        window_minutes=10080,
        provider="codex",
        config={"consumption_flexibility_defaults": {"weekly": 0.7}},
    )
    assert cls == FlexibilityClass.SEMI_THROTTLED
    assert score == 0.7


def test_classify_flexibility_burstable():
    cls, score = _classify_flexibility(
        window_minutes=20000,
        provider="opencode-go",
        config={"consumption_flexibility_defaults": {"monthly": 1.0}},
    )
    assert cls == FlexibilityClass.BURSTABLE
    assert score == 1.0


def test_classify_flexibility_provider_override():
    cfg = {"provider_overrides": {"claude": {"5h": {"flexibility": 0.0}}}}
    cls, score = _classify_flexibility(window_minutes=300, provider="claude", config=cfg)
    assert cls == FlexibilityClass.THROTTLED
    assert score == 0.0


def test_compute_value_at_risk_monthly():
    val = _compute_value_at_risk(
        remaining=100.0,
        window_minutes=10080,
        monthly_price=20.0,
        waking_hours_per_day=16,
    )
    expected = (100.0 / 100.0) * (20.0 / (16 * 30.44 * 60 / 10080))
    assert abs(val - expected) < 0.01


def test_compute_value_at_risk_5h():
    val = _compute_value_at_risk(
        remaining=80.0,
        window_minutes=300,
        monthly_price=20.0,
        waking_hours_per_day=16,
    )
    expected = 0.80 * (20.0 / (16 * 30.44 * 60 / 300))
    assert abs(val - expected) < 0.01


def test_score_multi_dim_burstable_imminent_is_critical():
    profile = FlexibilityProfile(
        flexibility_class=FlexibilityClass.BURSTABLE,
        consumption_flexibility=1.0,
        value_at_risk_usd=16.0,
    )
    urgency, score = _score_multi_dimension(profile=profile, remaining=80.0, days=0.01)
    assert urgency == Urgency.CRITICAL
    assert score >= 100


def test_score_multi_dim_burstable_far_out_is_low():
    profile = FlexibilityProfile(
        flexibility_class=FlexibilityClass.BURSTABLE,
        consumption_flexibility=1.0,
        value_at_risk_usd=4.0,
    )
    urgency, score = _score_multi_dimension(profile=profile, remaining=50.0, days=20)
    assert urgency in (Urgency.INFO, Urgency.NONE, Urgency.LOW)
    assert score < 30


def test_score_multi_dim_throttled_past_start_elevated():
    now = datetime.now(timezone.utc)
    profile = FlexibilityProfile(
        flexibility_class=FlexibilityClass.THROTTLED,
        consumption_flexibility=0.0,
        value_at_risk_usd=2.0,
        earliest_start_calendar=now - timedelta(hours=1),
    )
    urgency, score = _score_multi_dimension(profile=profile, remaining=40.0, days=0.5)
    assert urgency in (Urgency.HIGH, Urgency.MEDIUM)


def test_score_multi_dim_zero_remaining_is_none():
    profile = FlexibilityProfile(
        flexibility_class=FlexibilityClass.BURSTABLE,
        consumption_flexibility=1.0,
        value_at_risk_usd=10.0,
    )
    urgency, score = _score_multi_dimension(profile=profile, remaining=0.5, days=2.0)
    assert urgency == Urgency.NONE


def test_multi_dim_includes_throttled_5h():
    snap = Snapshot(
        collected_at=_now(),
        accounts=[
            AccountUsage(
                source="codexbar",
                provider="claude",
                billing_kind=BillingKind.SUBSCRIPTION_WINDOW,
                windows=[
                    QuotaWindow(
                        label="Claude 5-hour",
                        used_percent=0,
                        remaining_percent=100,
                        resets_at=_now() + timedelta(hours=2),
                        window_minutes=300,
                    )
                ],
            )
        ],
    )
    alerts = analyze_use_or_lose(
        snap,
        {
            "analysis": {
                "use_multi_dim_scoring": True,
                "min_value_at_risk_usd": 0.0,
                "min_value_fraction": 0.0,
            },
            "plans": {"claude": {"monthly_price": 20}},
        },
    )
    assert len(alerts) >= 1
    assert any("5-hour" in a.window_label for a in alerts)


def test_multi_dim_filters_tiny_value():
    snap = Snapshot(
        collected_at=_now(),
        accounts=[
            AccountUsage(
                source="codexbar",
                provider="claude",
                billing_kind=BillingKind.SUBSCRIPTION_WINDOW,
                windows=[
                    QuotaWindow(
                        label="Claude 5-hour",
                        used_percent=0,
                        remaining_percent=50,
                        resets_at=_now() + timedelta(hours=2),
                        window_minutes=300,
                    )
                ],
            )
        ],
    )
    alerts = analyze_use_or_lose(
        snap,
        {
            "analysis": {
                "use_multi_dim_scoring": True,
                "min_value_at_risk_usd": 10.0,
            },
            "plans": {"claude": {"monthly_price": 20}},
        },
    )
    # 5h window value is ~$0.11, below $10 threshold
    assert not any("5-hour" in a.window_label for a in alerts)
