"""Regression tests for cswap's canonical schema-v1 Claude data."""

from ai.collectors.cswap import _account_from_item


def test_pct_is_parsed_as_used_percentage():
    account = _account_from_item(
        {
            "number": 2,
            "email": "work-account@example.org",
            "active": True,
            "usageStatus": "ok",
            "usageFetchedAt": "2026-07-21T22:00:00Z",
            "usageAgeSeconds": 12.5,
            "usage": {
                "fiveHour": {"pct": 25, "resetsAt": "2099-01-01T00:00:00Z"},
                "sevenDay": {"pct": 16, "resetsAt": "2099-01-02T00:00:00Z"},
            },
        },
        2,
    )
    assert account.account == "work-account@example.org"
    assert [window.label for window in account.windows] == [
        "Claude Code 5-hour",
        "Claude Code weekly",
    ]
    assert account.windows[0].used_percent == 25
    assert account.windows[0].remaining() == 75
    assert account.windows[1].remaining() == 84


def test_distinct_cswap_emails_remain_distinct_accounts():
    gmail = _account_from_item(
        {
            "number": 3,
            "email": "personal-account@example.com",
            "usageStatus": "no_credentials",
            "usage": None,
        },
        2,
    )
    mit = _account_from_item(
        {
            "number": 2,
            "email": "work-account@example.org",
            "usageStatus": "keychain_unavailable",
            "usage": None,
        },
        2,
    )
    assert gmail.account != mit.account
    assert "no readable credentials" in gmail.error
    assert "Keychain" in mit.error


def test_scoped_model_limit_has_semantic_name():
    account = _account_from_item(
        {
            "number": 2,
            "email": "work-account@example.org",
            "usageStatus": "ok",
            "usage": {
                "scoped": [
                    {
                        "name": "Claude Opus",
                        "pct": 40,
                        "resetsAt": "2099-01-02T00:00:00Z",
                    }
                ]
            },
        },
        2,
    )
    assert account.windows[0].label == "Claude Code weekly — Claude Opus"
