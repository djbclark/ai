"""Unit tests for use-or-lose analysis (no live CLI required)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ai_usage.analysis.use_or_lose import analyze_use_or_lose
from ai_usage.models import (
    AccountUsage,
    BillingKind,
    QuotaWindow,
    Snapshot,
    Urgency,
)


def _now() -> datetime:
    return datetime(2026, 7, 21, 12, 0, tzinfo=timezone.utc)


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
            "plans": {"codex": {"monthly_usd": 20, "name": "Codex Plus"}},
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
