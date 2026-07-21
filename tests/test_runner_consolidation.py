from ai.collectors.runner import _consolidate_accounts, _select_and_cross_check
from ai.models import AccountUsage, BillingKind, QuotaWindow


def _account(source: str, provider: str, *, error: str | None = None) -> AccountUsage:
    return AccountUsage(
        source=source,
        provider=provider,
        billing_kind=BillingKind.SUBSCRIPTION_WINDOW,
        windows=[] if error else [QuotaWindow(label="quota", used_percent=10)],
        error=error,
    )


def test_cswap_is_only_claude_authority_when_enabled():
    accounts = _consolidate_accounts(
        [
            _account("cswap", "claude"),
            _account("codexbar", "claude"),
        ],
        cswap_authoritative=True,
    )
    assert [(account.source, account.provider) for account in accounts] == [("cswap", "claude")]


def test_tokscale_is_removed_when_codexbar_has_live_provider_data():
    accounts = _consolidate_accounts(
        [
            _account("codexbar", "codex"),
            _account("tokscale", "codex"),
            _account("codexbar", "grok"),
            _account("tokscale", "grok-build"),
        ],
        cswap_authoritative=True,
    )
    assert [account.source for account in accounts] == ["codexbar", "codexbar"]


def test_tokscale_remains_as_fallback_after_codexbar_error():
    accounts, checks = _select_and_cross_check(
        [
            _account("codexbar", "copilot", error="failed"),
            _account("tokscale", "copilot"),
        ],
        cswap_authoritative=True,
    )
    assert [account.source for account in accounts] == ["tokscale"]
    assert checks[0].status == "warning"
    assert "CodexBar failed" in checks[0].message


def test_cross_check_reports_consistent_duplicate_measurements():
    codexbar = _account("codexbar", "codex")
    tokscale = _account("tokscale", "codex")
    codexbar.windows[0].label = "Codex weekly quota"
    tokscale.windows[0].label = "Codex weekly quota"
    accounts, checks = _select_and_cross_check([codexbar, tokscale], cswap_authoritative=True)
    assert [account.source for account in accounts] == ["codexbar"]
    assert checks[0].status == "consistent"


def test_cross_check_warns_when_percentages_disagree():
    codexbar = _account("codexbar", "codex")
    tokscale = _account("tokscale", "codex")
    codexbar.windows[0].label = "Codex weekly quota"
    tokscale.windows[0].label = "Codex weekly quota"
    tokscale.windows[0].used_percent = 30
    accounts, checks = _select_and_cross_check([codexbar, tokscale], cswap_authoritative=True)
    assert [account.source for account in accounts] == ["codexbar"]
    assert checks[0].status == "warning"
    assert "percentage points" in checks[0].message


def test_claude_cross_check_matches_accounts_case_insensitively():
    cswap_row = _account("cswap", "claude")
    cswap_row.account = "User@Example.com"
    cswap_row.windows[0].label = "Claude Code weekly"
    codexbar_row = _account("codexbar", "claude")
    codexbar_row.account = "user@example.com"
    codexbar_row.windows[0].label = "Claude Code weekly"
    codexbar_row.windows[0].used_percent = 50

    accounts, checks = _select_and_cross_check([cswap_row, codexbar_row], cswap_authoritative=True)

    assert [account.source for account in accounts] == ["cswap"]
    assert checks[0].status == "warning"
    assert "percentage points" in checks[0].message


def test_claude_gets_cross_checked_when_cswap_disabled():
    codexbar_row = _account("codexbar", "claude")
    tokscale_row = _account("tokscale", "claude")
    codexbar_row.windows[0].used_percent = 5
    tokscale_row.windows[0].used_percent = 90

    accounts, checks = _select_and_cross_check([codexbar_row, tokscale_row], cswap_authoritative=False)

    assert [account.source for account in accounts] == ["codexbar"]
    assert checks
    assert checks[0].status == "warning"
