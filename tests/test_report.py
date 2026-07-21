from ai.models import AccountUsage
from ai.report import _sorted_accounts


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
