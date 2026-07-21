"""Parse codexbar-shaped JSON without calling the binary."""

from __future__ import annotations

from ai_usage.collectors.codexbar import _from_row
from ai_usage.models import BillingKind


def test_parse_copilot_style():
    row = {
        "provider": "copilot",
        "source": "api",
        "account": "djbclark (Individual)",
        "usage": {
            "primary": {
                "usedPercent": 0,
                "resetsAt": "2026-08-01T00:00:00Z",
                "windowMinutes": 44640,
            },
            "secondary": {
                "usedPercent": 18.6,
                "resetsAt": "2026-08-01T00:00:00Z",
                "windowMinutes": 44640,
            },
            "loginMethod": "Individual",
            "accountEmail": "djbclark (Individual)",
        },
    }
    acc = _from_row(row)
    assert acc.provider == "copilot"
    assert acc.billing_kind == BillingKind.SUBSCRIPTION_WINDOW
    assert len(acc.windows) == 2
    assert acc.windows[0].remaining_percent == 100
    # windowMinutes 44640 → Monthly relabel (Primary keeps short name)
    assert acc.windows[0].label == "Monthly"
    assert acc.windows[1].label == "Monthly (secondary)"


def test_parse_error_row():
    row = {
        "provider": "claude",
        "source": "auto",
        "error": {"kind": "provider", "message": "No Claude session key"},
    }
    acc = _from_row(row)
    assert acc.error
    assert "Claude" in acc.error or "session" in acc.error


def test_parse_openrouter_prepaid():
    row = {
        "provider": "openrouter",
        "source": "api",
        "usage": {
            "loginMethod": "Balance: $18.90",
            "openRouterUsage": {
                "balance": 18.903002,
                "totalCredits": 20,
                "totalUsage": 1.096998,
                "usedPercent": 5.48,
            },
        },
    }
    acc = _from_row(row)
    assert acc.billing_kind == BillingKind.PREPAID_BALANCE
    assert acc.balance_usd is not None
    assert acc.balance_usd > 18
