"""Detect monthly/weekly subscription allotments that will expire unused."""

from __future__ import annotations

from typing import Any

from ai.models import (
    WINDOW_5H_MAX_MINUTES,
    AccountUsage,
    BillingKind,
    QuotaWindow,
    Snapshot,
    Urgency,
    UseOrLoseAlert,
    provider_display_name,
    utcnow,
)

# Windows shorter than this are rate-limits, not "monthly plan waste"
SHORT_WINDOW_LABELS = {"5-hour", "5h", "session", "hourly"}


def analyze_use_or_lose(
    snapshot: Snapshot,
    config: dict[str, Any] | None = None,
) -> list[UseOrLoseAlert]:
    cfg = (config or {}).get("analysis") or {}
    min_remaining = float(cfg.get("min_remaining_percent", 40))
    max_days = float(cfg.get("max_days_until_reset", 14))
    urgent_remaining = float(cfg.get("urgent_remaining_percent", 70))
    urgent_days = float(cfg.get("urgent_days_until_reset", 7))
    plans = (config or {}).get("plans") or {}

    now = utcnow()
    alerts: list[UseOrLoseAlert] = []
    seen: set[tuple[str, str, str]] = set()

    for account in snapshot.accounts:
        if account.error and not account.windows:
            continue
        if account.billing_kind == BillingKind.PAYG_API:
            continue
        if account.billing_kind == BillingKind.PREPAID_BALANCE:
            # Prepaid usually rolls; only note large idle balances as INFO
            if account.balance_usd is not None and account.balance_usd >= 10:
                alerts.append(
                    UseOrLoseAlert(
                        urgency=Urgency.INFO,
                        provider=account.provider,
                        account=account.account,
                        window_label="prepaid balance",
                        remaining_percent=100.0,
                        days_until_reset=None,
                        plan=account.plan,
                        message=(
                            f"{account.provider}: ${account.balance_usd:.2f} prepaid "
                            "balance (usually does not expire — spend when useful, "
                            "not urgent like subscription windows)."
                        ),
                        source=account.source,
                        score=5.0,
                    )
                )
            continue

        plan_meta = _plan_meta(account.provider, plans)
        for window in account.windows:
            if _is_short_window(window):
                continue

            remaining = window.remaining()
            if remaining is None:
                continue
            days = window.days_until_reset(now)

            # Use-or-lose recommendations require a future, known deadline.
            if days is None or days <= 0:
                continue

            # Skip fully used windows
            if remaining < min_remaining:
                continue
            if days > max_days:
                continue

            key = (
                account.provider.lower(),
                (account.account or "").lower(),
                f"{window.label.lower()}|{window.resets_at.isoformat() if window.resets_at else ''}",
            )
            if key in seen:
                continue
            seen.add(key)

            urgency, score = _score(
                remaining=remaining,
                days=days,
                urgent_remaining=urgent_remaining,
                urgent_days=urgent_days,
                min_remaining=min_remaining,
                label=window.label,
                max_days=max_days,
            )
            if urgency == Urgency.NONE:
                continue

            message = _message(
                account=account,
                window_label=window.label,
                remaining=remaining,
                days=days,
                plan_notes=plan_meta.get("notes"),
            )
            alerts.append(
                UseOrLoseAlert(
                    urgency=urgency,
                    provider=account.provider,
                    account=account.account,
                    window_label=window.label,
                    remaining_percent=remaining,
                    days_until_reset=days,
                    plan=account.plan or plan_meta.get("name"),
                    message=message,
                    source=account.source,
                    score=score,
                )
            )
    alerts.sort(key=lambda a: (-a.score, a.provider.casefold(), a.window_label.casefold()))
    return alerts


def _is_short_window(window: QuotaWindow) -> bool:
    if window.window_minutes is not None and window.window_minutes <= WINDOW_5H_MAX_MINUTES:
        return True
    low = window.label.lower().strip()
    if low in SHORT_WINDOW_LABELS:
        return True
    if "5-hour" in low or "5 hour" in low or "5h" in low:
        return True
    return False


def _looks_monthly(label: str) -> bool:
    low = label.lower()
    return "month" in low or "billing" in low


def _plan_meta(provider: str, plans: dict[str, Any]) -> dict[str, Any]:
    key = provider.lower().replace(" ", "-")
    # By the time an account reaches here, runner.py's _canonical_provider has already
    # rewritten raw collector slugs (chatgpt, grok-build, github-copilot, ...) to their
    # canonical provider name. This maps canonical provider -> plans.yaml config key,
    # for the providers whose config key differs from the canonical provider name.
    aliases = {
        "antigravity": "gemini",
        "opencode-go": "opencode",
    }
    lookup = aliases.get(key, key)
    meta = plans.get(lookup) or plans.get(provider) or {}
    return meta if isinstance(meta, dict) else {}


def _score(
    *,
    remaining: float,
    days: float | None,
    urgent_remaining: float,
    urgent_days: float,
    min_remaining: float,
    label: str,
    max_days: float,
) -> tuple[Urgency, float]:
    # Base score from remaining fraction that would be wasted
    score = remaining

    # Time pressure
    if days is not None:
        if days <= 1:
            score += 40
        elif days <= 3:
            score += 30
        elif days <= 7:
            score += 20
        elif days <= 14:
            score += 10
        else:
            score += 2
    else:
        score += 5  # unknown reset — still interesting if high remaining

    # Longer-lived quotas are generally more important than short refill windows.
    if _looks_monthly(label):
        score += 15
    elif "week" in label.lower() or "7" in label.lower():
        score += 8

    if remaining >= urgent_remaining and days is not None and days <= urgent_days:
        urgency = Urgency.CRITICAL if days <= 3 or remaining >= 90 else Urgency.HIGH
    elif remaining >= min_remaining and days is not None and days <= max_days:
        urgency = Urgency.MEDIUM if remaining >= 50 else Urgency.LOW
    else:
        urgency = Urgency.NONE

    return urgency, score


def _message(
    *,
    account: AccountUsage,
    window_label: str,
    remaining: float,
    days: float | None,
    plan_notes: Any,
) -> str:
    who = account.account or "default"
    plan = account.plan or "subscription"
    time_part = f"resets in {days:.1f} day(s)" if days is not None else "reset time unknown"
    note = f" {plan_notes}" if plan_notes else ""
    return (
        f"Use {provider_display_name(account.provider)} ({who}, {plan}) soon: "
        f"{remaining:.0f}% of the {window_label} remains and {time_part}."
        f"{note}"
    )
