"""Parse codexbar-shaped JSON without calling the binary."""

from __future__ import annotations

from ai.collectors.codexbar import _from_row, _normalize_providers
from ai.models import BillingKind


def test_parse_copilot_style():
    row = {
        "provider": "copilot",
        "source": "api",
        "account": "example-user (Individual)",
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
            "accountEmail": "example-user (Individual)",
        },
    }
    acc = _from_row(row)
    assert acc.provider == "copilot"
    assert acc.billing_kind == BillingKind.SUBSCRIPTION_WINDOW
    assert len(acc.windows) == 2
    assert acc.windows[0].remaining_percent == 100
    assert acc.windows[0].label == "GitHub Copilot completions"
    assert acc.windows[1].label == "GitHub Copilot chat messages"
    assert all("secondary" not in window.label.lower() for window in acc.windows)


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


def test_parse_named_extra_rate_windows_without_generic_duplicates():
    row = {
        "provider": "antigravity",
        "source": "app",
        "usage": {
            "extraRateWindows": [
                {
                    "title": "Gemini weekly",
                    "window": {
                        "usedPercent": 0,
                        "resetsAt": "2026-08-01T00:00:00Z",
                        "windowMinutes": 10080,
                    },
                },
                {
                    "title": "Claude/GPT weekly",
                    "window": {
                        "usedPercent": 75,
                        "resetsAt": "2026-07-25T00:00:00Z",
                        "windowMinutes": 10080,
                    },
                },
            ],
            # These are duplicate projections of the named windows above.
            "primary": {
                "usedPercent": 0,
                "resetsAt": "2026-08-01T00:00:00Z",
                "windowMinutes": 10080,
            },
            "secondary": {
                "usedPercent": 75,
                "resetsAt": "2026-07-25T00:00:00Z",
                "windowMinutes": 10080,
            },
        },
    }
    acc = _from_row(row)
    assert [window.label for window in acc.windows] == [
        "Gemini weekly",
        "Claude/GPT weekly",
    ]


def test_unknown_duration_is_not_guessed_from_reset_time():
    acc = _from_row(
        {
            "provider": "grok",
            "usage": {
                "primary": {
                    "usedPercent": 25,
                    "resetsAt": "2099-01-01T00:00:00Z",
                }
            },
        }
    )
    assert acc.windows[0].label == "Grok usage limit"


def test_zero_of_zero_is_not_reported_as_fully_unused():
    acc = _from_row(
        {
            "provider": "warp",
            "usage": {
                "primary": {
                    "usedPercent": 0,
                    "resetDescription": "0/0 credits",
                    "resetsAt": "2099-01-01T00:00:00Z",
                }
            },
        }
    )
    assert acc.windows[0].label == "Warp credits"
    assert acc.windows[0].remaining() == 0


def test_provider_selection_defaults_to_enabled_and_splits_csv():
    assert _normalize_providers("enabled") == [None]
    assert _normalize_providers("codex,copilot") == ["codex", "copilot"]


def test_openai_api_usage_is_payg_not_prepaid():
    # "openai" is in PREPAID_HINTS, but an explicit openAIAPIUsage blob means this
    # account is billed pay-as-you-go, not a prepaid balance that rolls over.
    acc = _from_row(
        {
            "provider": "openai",
            "usage": {"openAIAPIUsage": {"usedPercent": 12}},
        }
    )
    assert acc.billing_kind == BillingKind.PAYG_API


def test_prepaid_hint_provider_with_real_window_is_subscription_window():
    # A PREPAID_HINTS provider (e.g. "together") that reports a genuine rate-limit
    # window with a real reset time must still be flagged as use-or-lose eligible,
    # not silently treated as a non-urgent prepaid balance.
    acc = _from_row(
        {
            "provider": "together",
            "usage": {
                "primary": {
                    "usedPercent": 5,
                    "resetsAt": "2026-08-01T00:00:00Z",
                    "windowMinutes": 10080,
                }
            },
        }
    )
    assert acc.billing_kind == BillingKind.SUBSCRIPTION_WINDOW
    assert acc.windows[0].remaining() == 95


def test_dollar_rate_in_description_is_not_mistaken_for_a_balance():
    acc = _from_row(
        {
            "provider": "glama",
            "usage": {
                "primary": {
                    "usedPercent": 10,
                    "resetDescription": "Overage billed at $0.002/1K tokens, no fixed reset",
                }
            },
        }
    )
    assert acc.balance_usd is None


def test_unmapped_provider_windowminutes_bucketing_boundaries():
    weekly = _from_row({"provider": "codex", "usage": {"primary": {"usedPercent": 10, "windowMinutes": 500}}})
    assert weekly.windows[0].label == "Codex weekly quota"

    monthly = _from_row({"provider": "codex", "usage": {"primary": {"usedPercent": 10, "windowMinutes": 44640}}})
    assert monthly.windows[0].label == "Codex monthly quota"
