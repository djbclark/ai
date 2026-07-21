"""Orchestrate all collectors into a Snapshot."""

from __future__ import annotations

from typing import Any

from ai.models import AccountUsage, CrossCheck, QuotaWindow, Snapshot, utcnow

from .codexbar import collect_codexbar
from .cswap import collect_cswap
from .tokscale import collect_tokscale


def run_collectors(config: dict[str, Any] | None = None) -> Snapshot:
    config = config or {}
    collectors_cfg = config.get("collectors") or {}
    snapshot = Snapshot(collected_at=utcnow())

    # cswap — Claude multi-account
    if _enabled(collectors_cfg, "cswap"):
        try:
            snapshot.accounts.extend(collect_cswap())
        except Exception as exc:  # noqa: BLE001
            snapshot.collector_errors.append(f"cswap: {exc}")

    # codexbar — live quotas across many providers
    if _enabled(collectors_cfg, "codexbar"):
        try:
            providers = (collectors_cfg.get("codexbar") or {}).get("providers", "enabled")
            snapshot.accounts.extend(collect_codexbar(providers=providers))
        except Exception as exc:  # noqa: BLE001
            snapshot.collector_errors.append(f"codexbar: {exc}")

    # tokscale — independent live view used for cross-checking and source selection
    if _enabled(collectors_cfg, "tokscale"):
        try:
            snapshot.accounts.extend(collect_tokscale())
        except Exception as exc:  # noqa: BLE001
            snapshot.collector_errors.append(f"tokscale: {exc}")

    snapshot.accounts, snapshot.cross_checks = _select_and_cross_check(
        snapshot.accounts,
        cswap_authoritative=_enabled(collectors_cfg, "cswap"),
    )
    return snapshot


def _enabled(collectors_cfg: dict[str, Any], name: str) -> bool:
    section = collectors_cfg.get(name)
    if section is None:
        return True
    if isinstance(section, bool):
        return section
    if isinstance(section, dict):
        return bool(section.get("enabled", True))
    return True


_PROVIDER_ALIASES = {
    "chatgpt": "codex",
    "openai-codex": "codex",
    "github-copilot": "copilot",
    "grok-build": "grok",
    "supergrok": "grok",
    "opencodego": "opencode-go",
}


def _canonical_provider(provider: str) -> str:
    key = provider.lower().replace(" ", "-")
    return _PROVIDER_ALIASES.get(key, key)


_CROSS_CHECK_PROVIDERS = {"codex", "copilot", "grok"}


def _select_and_cross_check(
    accounts: list[AccountUsage],
    *,
    cswap_authoritative: bool,
) -> tuple[list[AccountUsage], list[CrossCheck]]:
    """Select report rows while retaining overlapping data as cross-checks.

    cswap owns Claude because it knows about every configured Claude Code slot.
    For other providers, CodexBar is selected when live and tokscale is selected
    otherwise. Overlapping measurements are compared before either copy is hidden.
    """

    for account in accounts:
        account.provider = _canonical_provider(account.provider)

    providers = sorted({account.provider for account in accounts})
    selected: list[AccountUsage] = []
    checks: list[CrossCheck] = []
    for provider in providers:
        rows = [account for account in accounts if account.provider == provider]

        if provider == "claude" and cswap_authoritative:
            cswap_rows = [account for account in rows if account.source == "cswap"]
            codexbar_rows = [account for account in rows if account.source == "codexbar"]
            selected.extend(cswap_rows)
            checks.extend(_claude_cross_checks(cswap_rows, codexbar_rows))
            continue

        codexbar_rows = [account for account in rows if account.source == "codexbar"]
        tokscale_rows = [account for account in rows if account.source == "tokscale"]
        other_rows = [account for account in rows if account.source not in ("codexbar", "tokscale")]
        codexbar_live = [account for account in codexbar_rows if _has_live_data(account)]
        tokscale_live = [account for account in tokscale_rows if _has_live_data(account)]

        if codexbar_live:
            selected.extend(codexbar_live)
        elif tokscale_live:
            selected.extend(tokscale_live)
        elif codexbar_rows:
            selected.extend(codexbar_rows)
        else:
            selected.extend(tokscale_rows)
        selected.extend(other_rows)

        if provider in _CROSS_CHECK_PROVIDERS:
            checks.append(_provider_cross_check(provider, codexbar_rows, tokscale_rows))

    return selected, checks


def _consolidate_accounts(
    accounts: list[AccountUsage],
    *,
    cswap_authoritative: bool,
) -> list[AccountUsage]:
    """Compatibility wrapper for callers that only need selected rows."""
    selected, _ = _select_and_cross_check(accounts, cswap_authoritative=cswap_authoritative)
    return selected


def _has_live_data(account: AccountUsage) -> bool:
    return not account.error and (
        bool(account.windows) or account.balance_usd is not None or account.credits_remaining is not None
    )


def _claude_cross_checks(cswap_rows: list[AccountUsage], codexbar_rows: list[AccountUsage]) -> list[CrossCheck]:
    checks: list[CrossCheck] = []
    live_codexbar = [row for row in codexbar_rows if _has_live_data(row)]
    codexbar_errors = [row.error for row in codexbar_rows if row.error]

    if not cswap_rows:
        return [
            CrossCheck(
                provider="claude",
                account=None,
                status="warning",
                sources=["cswap", "CodexBar"],
                message=(
                    "cswap returned no Claude Code account rows, so Claude cannot "
                    "be reported from its canonical multi-account source."
                ),
            )
        ]

    matched_codexbar_ids: set[int] = set()
    for cswap_row in cswap_rows:
        match = next(
            (
                row
                for row in live_codexbar
                if row.account and cswap_row.account and row.account.lower() == cswap_row.account.lower()
            ),
            None,
        )
        if match is not None:
            matched_codexbar_ids.add(id(match))
            checks.append(_compare_live_rows(cswap_row, match))
            continue

        if cswap_row.error and live_codexbar:
            checks.append(
                CrossCheck(
                    provider="claude",
                    account=cswap_row.account,
                    status="warning",
                    sources=["cswap", "CodexBar"],
                    message=(
                        f"cswap could not read canonical usage for Claude Code account "
                        f"{cswap_row.account}, while CodexBar reported Claude data for "
                        "a different or unidentified account. Do not substitute that "
                        "CodexBar measurement for this account."
                    ),
                )
            )
        else:
            reason = (
                f"CodexBar also failed: {codexbar_errors[0]}"
                if codexbar_errors
                else "CodexBar did not report this Claude Code account."
            )
            checks.append(
                CrossCheck(
                    provider="claude",
                    account=cswap_row.account,
                    status="unavailable",
                    sources=["cswap", "CodexBar"],
                    message=(f"No independent Claude quota cross-check is available for {cswap_row.account}. {reason}"),
                )
            )

    for row in live_codexbar:
        if id(row) not in matched_codexbar_ids:
            checks.append(
                CrossCheck(
                    provider="claude",
                    account=row.account,
                    status="warning",
                    sources=["cswap", "CodexBar"],
                    message=(
                        f"CodexBar reported Claude account {row.account or 'unknown'}, "
                        "but it did not match either canonical cswap account."
                    ),
                )
            )
    return checks


def _provider_cross_check(
    provider: str,
    codexbar_rows: list[AccountUsage],
    tokscale_rows: list[AccountUsage],
) -> CrossCheck:
    codexbar_live = next((row for row in codexbar_rows if _has_live_data(row)), None)
    tokscale_live = next((row for row in tokscale_rows if _has_live_data(row)), None)
    selected_live = codexbar_live or tokscale_live
    account = selected_live.account if selected_live is not None else None

    if codexbar_live and tokscale_live:
        return _compare_live_rows(codexbar_live, tokscale_live)
    if codexbar_live and any(row.error for row in tokscale_rows):
        error = next(row.error for row in tokscale_rows if row.error)
        return CrossCheck(
            provider=provider,
            account=account,
            status="warning",
            sources=["CodexBar", "tokscale"],
            message=f"CodexBar returned live data, but tokscale failed: {error}",
        )
    if tokscale_live and any(row.error for row in codexbar_rows):
        error = next(row.error for row in codexbar_rows if row.error)
        return CrossCheck(
            provider=provider,
            account=account,
            status="warning",
            sources=["CodexBar", "tokscale"],
            message=f"tokscale returned live data, but CodexBar failed: {error}",
        )

    available = "CodexBar" if codexbar_live else "tokscale" if tokscale_live else "neither tool"
    provider_name = _provider_display_name(provider)
    return CrossCheck(
        provider=provider,
        account=account,
        status="unavailable",
        sources=["CodexBar", "tokscale"],
        message=(f"A two-tool cross-check is unavailable; live {provider_name} data was reported by {available}."),
    )


def _compare_live_rows(left: AccountUsage, right: AccountUsage) -> CrossCheck:
    issues: list[str] = []
    matched_right: set[int] = set()
    matched_count = 0

    if left.account and right.account and left.account.lower() != right.account.lower():
        issues.append(f"account identifiers differ ({left.account} versus {right.account})")

    for left_window in left.windows:
        right_window = _matching_window(left_window, right.windows, matched_right)
        if right_window is None:
            if _has_usable_capacity(left_window):
                issues.append(f"{left.source} alone reported {left_window.label}")
            continue
        matched_right.add(id(right_window))
        matched_count += 1
        left_remaining = left_window.remaining()
        right_remaining = right_window.remaining()
        if left_remaining is not None and right_remaining is not None and abs(left_remaining - right_remaining) > 3.0:
            issues.append(
                f"{left_window.label} differs by {abs(left_remaining - right_remaining):.1f} percentage points"
            )
        if left_window.resets_at and right_window.resets_at:
            seconds = abs((left_window.resets_at - right_window.resets_at).total_seconds())
            if seconds > 900:
                issues.append(f"{left_window.label} reset times differ by {seconds / 60:.0f} minutes")

    for right_window in right.windows:
        if id(right_window) not in matched_right and _has_usable_capacity(right_window):
            issues.append(f"{right.source} alone reported {right_window.label}")

    sources = [_source_name(left.source), _source_name(right.source)]
    account = left.account or right.account
    if issues:
        return CrossCheck(
            provider=left.provider,
            account=account,
            status="warning",
            sources=sources,
            message="Possible reporting inconsistency: " + "; ".join(issues) + ".",
        )
    return CrossCheck(
        provider=left.provider,
        account=account,
        status="consistent",
        sources=sources,
        message=(
            f"The tools agree on {matched_count} overlapping live quota "
            f"measurement{'s' if matched_count != 1 else ''} within tolerance."
        ),
    )


def _matching_window(
    target: QuotaWindow,
    candidates: list[QuotaWindow],
    already_matched: set[int],
) -> QuotaWindow | None:
    unmatched = [candidate for candidate in candidates if id(candidate) not in already_matched]
    exact_label = next(
        (candidate for candidate in unmatched if candidate.label.lower() == target.label.lower()),
        None,
    )
    if exact_label is not None:
        return exact_label
    if target.resets_at is None:
        return None
    return next(
        (
            candidate
            for candidate in unmatched
            if candidate.resets_at is not None and abs((candidate.resets_at - target.resets_at).total_seconds()) <= 900
        ),
        None,
    )


def _has_usable_capacity(window: QuotaWindow) -> bool:
    remaining = window.remaining()
    return remaining is not None and remaining > 0


def _source_name(source: str) -> str:
    return {"codexbar": "CodexBar", "tokscale": "tokscale", "cswap": "cswap"}.get(source, source)


def _provider_display_name(provider: str) -> str:
    return {
        "claude": "Claude Code",
        "codex": "Codex",
        "copilot": "GitHub Copilot",
        "grok": "Grok",
        "opencode-go": "OpenCode Go",
    }.get(provider, provider.replace("-", " ").title())
